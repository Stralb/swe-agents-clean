"""Offline fixture tests: no original data or remote credentials required."""
from __future__ import annotations
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from openpyxl import Workbook
from src.repro_store import EvidenceError, EvidenceStore
from src.repro_store.research import ResearchIndex
from src.repro_store.importers import import_archive, import_workbook, register_runs, import_csv_explicit

class ResearchIntakeTest(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.vault=EvidenceStore.create(self.root/"store",inline_limit=10000)
        self.index=ResearchIndex(self.vault)

    def workbook(self):
        wb=Workbook()
        s=wb.active
        s.title="Issue_PR_Master_122"
        s.append(["Case ID","Instruction Specificity","Upstream Pattern","Issue Title"])
        s.append([154,"Problem only","Feature / capability addition","Test title"])
        s.append([415,"Explicit instruction","Bug fix",'=IF(1=1,"x","y")'])
        s=wb.create_sheet("Step3_Attribution")
        s.append(["Producing Change ID","Case ID","First-pass Attribution","Final Attribution","Attribution Reason"])
        s.append(["PC-001",154,"Direct","Side-effect","QC correction"])
        s=wb.create_sheet("Risk_Assessment")
        s.append(["Case ID","First-pass Risk Label","Final Risk Label"])
        s.append([154,"Benign ambiguous","Benign ordinary"])
        path=self.root/"master.xlsx"
        wb.save(path)
        return path

    def test_workbook_captures_labels_and_original(self):
        path=self.workbook()
        initial=path.read_bytes()
        r=import_workbook(self.vault,path,origin_uri="upload://master",origin_revision="sha-2026")
        self.assertEqual(r["indexed_rows"],7)
        self.assertEqual(path.read_bytes(),initial)
        case=self.index.case(154)
        label={a["label"]:a["value"] for a in case["annotations"]}
        self.assertEqual(label["instruction_specificity"],"Problem only")
        self.assertEqual(label["risk_first_pass"],"Benign ambiguous")
        self.assertEqual(label["risk_final"],"Benign ordinary")
        self.assertEqual(self.index.verify()["status"],"PASS")
        sha=hashlib.sha256(initial).hexdigest()
        self.assertEqual(self.vault.bytes_for_digest(sha),initial)

    def test_workbook_cross_unit_edges(self):
        wb=self.workbook()
        import_workbook(self.vault,wb,origin_uri="u",origin_revision="r")
        case=self.index.case(154)
        rel=case["related_units"]
        self.assertTrue(any(x["from_id"]=="PC-001" and x["relation"]=="change_in_workflow" for x in rel))

    def test_csv_explicit_key_and_relationship(self):
        csv=self.root/"pairs.csv"
        csv.write_text("positive_case_id,control_case_id,match_tier\n154,147,B\n166,157,A\n",encoding="utf-8")
        result=import_csv_explicit(self.vault,csv,origin_uri="wits://c2",origin_revision="sha-abc",
                                  stage="C2",unit_type="control_pair",
                                  key_columns=["positive_case_id","control_case_id"],
                                  related_columns=[("positive_case_id","workflow","positive_side"),
                                                   ("control_case_id","workflow","control_side")])
        self.assertEqual(result["rows"],2)
        case=self.index.case(154)
        self.assertTrue(any(x["from_id"]=="154|147" and x["to_id"]=="154" for x in case["related_units"]))
        self.assertTrue(import_csv_explicit(self.vault,csv,origin_uri="wits://c2",origin_revision="sha-abc",
                     stage="C2",unit_type="control_pair",key_columns=["positive_case_id","control_case_id"],
                     related_columns=[("positive_case_id","workflow","positive_side"),
                                      ("control_case_id","workflow","control_side")])["already_imported"])

    def test_workbook_idempotent(self):
        p=self.workbook()
        x=import_workbook(self.vault,p,origin_uri="u",origin_revision="r")
        y=import_workbook(self.vault,p,origin_uri="u",origin_revision="r")
        self.assertEqual(x["batch_id"],y["batch_id"])
        self.assertTrue(y["already_imported"])
        self.assertEqual(self.index.summary()["counts"]["research_batches"],1)

    def test_formula_preserved_no_calculation(self):
        p=self.workbook()
        import_workbook(self.vault,p,origin_uri="u",origin_revision="r")
        cells=self.index.case(415)["records"][0]["payload"]["cells_by_1based_column"]
        self.assertEqual(cells["4"]["formula"], '=IF(1=1,"x","y")')

    def archive(self):
        p=self.root/"runs.zip"
        with zipfile.ZipFile(p,"w",zipfile.ZIP_DEFLATED) as z:
            z.writestr("G001/PROMPT.txt", "Implement target task\n")
            z.writestr("G001/out.patch", "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-a\n+b\n")
            z.writestr("G001/after.sarif", '{"version":"2.1.0","runs":[]}')
            z.writestr("G002/out.patch", "+failed\n")
        return p

    def test_archive_and_runs_are_real_bytes(self):
        p=self.archive();raw=p.read_bytes();sha=hashlib.sha256(raw).hexdigest()
        r=import_archive(self.vault,p,origin_uri="cluster://frozen/runs.zip",origin_revision="version-1")
        self.assertEqual(r["members"],4)
        with self.vault._open(readonly=True) as cx:
            digest=cx.execute("SELECT member_sha256 FROM archive_members WHERE member_path='G001/out.patch'").fetchone()[0]
        self.assertEqual(self.vault.bytes_for_digest(digest).splitlines()[0],b"--- a/f.py")
        self.assertEqual(self.vault.bytes_for_digest(sha),raw)
        self.assertEqual(self.index.verify()["status"],"PASS")
        mapping={"schema_version":1,"source_archive_sha256":sha,"study_id":"T1-synthetic",
                 "protocol_revision":"v1","runs":[
                   {"run_id":"G001","case_id":"154","arm":"Context+","model":"test","seed":1,
                    "files":{"prompt":"G001/PROMPT.txt","generated_patch":"G001/out.patch","scanner_after":"G001/after.sarif"}},
                   {"run_id":"G002","case_id":"154","arm":"Context-","model":"test","seed":2,
                    "files":{"generated_patch":"G002/out.patch"}}]}
        manifest=self.root/"map.json";manifest.write_text(json.dumps(mapping))
        result=register_runs(self.vault,manifest,origin_uri="local://mapping",origin_revision="test")
        self.assertEqual(result["runs"],2)
        self.assertEqual(result["run_asset_links"],4)
        with self.vault._open(readonly=True) as cx:
            result=cx.execute("SELECT run_id,arm,analysis_status FROM experiment_runs ORDER BY run_id").fetchall()
            missing=cx.execute("SELECT missing_role FROM evidence_gaps ORDER BY missing_role").fetchall()
        self.assertEqual(result,[("G001","Context+","unverified"),("G002","Context-","unverified")])
        self.assertEqual([r[0] for r in missing],["prompt","scanner_after"])

    def test_archive_repeated_safe(self):
        p=self.archive()
        x=import_archive(self.vault,p,origin_uri="u",origin_revision="r")
        y=import_archive(self.vault,p,origin_uri="u",origin_revision="r")
        self.assertEqual(x["batch_id"],y["batch_id"])
        self.assertTrue(y["already_imported"])

    def test_bad_archive_paths_rejected(self):
        for illegal in ("../secret.txt", "./../secret.txt", "/rootfile", "project/.env", "x/private.pem"):
            p=self.root/"unsafe.zip"
            with zipfile.ZipFile(p,"w") as z:z.writestr(illegal,"bad")
            with self.assertRaises(EvidenceError, msg=illegal):
                import_archive(self.vault,p,origin_uri="u",origin_revision="r")
        self.assertEqual(self.index.summary()["counts"]["research_batches"],0)

    def test_duplicate_archive_paths_rejected(self):
        p=self.root/"duplicate.zip"
        with zipfile.ZipFile(p,"w") as z:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                z.writestr("same.patch","a");z.writestr("same.patch","b")
        with self.assertRaises(EvidenceError):
            import_archive(self.vault,p,origin_uri="u",origin_revision="r")

    def test_missing_declared_run_member_is_error(self):
        p=self.archive();sha=hashlib.sha256(p.read_bytes()).hexdigest()
        import_archive(self.vault,p,origin_uri="u",origin_revision="r")
        manifest=self.root/"bad.json"
        manifest.write_text(json.dumps({"schema_version":1,"source_archive_sha256":sha,
          "study_id":"pilot","protocol_revision":"v1","runs":[
          {"run_id":"X1","arm":"P+","files":{"generated_patch":"missing.patch"}}]}))
        with self.assertRaises(EvidenceError):
            register_runs(self.vault,manifest,origin_uri="u",origin_revision="r")
        self.assertEqual(self.index.summary()["counts"]["experiment_runs"],0)

    def test_run_id_crosswalk_not_guessed(self):
        p=self.archive()
        import_archive(self.vault,p,origin_uri="u",origin_revision="r")
        self.assertEqual(self.index.summary()["counts"]["experiment_runs"],0)

    def test_updates_forbidden(self):
        p=self.workbook();import_workbook(self.vault,p,origin_uri="u",origin_revision="r")
        with sqlite3.connect(self.vault.db_path) as cx:
            with self.assertRaises(sqlite3.IntegrityError):
                cx.execute("UPDATE research_annotations SET label_json='null'")

if __name__=="__main__":unittest.main()
