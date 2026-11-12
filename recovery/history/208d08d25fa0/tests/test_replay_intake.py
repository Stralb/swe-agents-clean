"""Synthetic source fixtures; never run CodeQL or contact the real cluster."""
from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.repro_store import EvidenceStore, EvidenceError
from src.repro_store.replay_intake import prepare_s5pair, STUDY_ID
from src.repro_store.importers import import_archive, register_runs
from src.repro_store.research import ResearchIndex


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class ReplaySourceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.src = self.root / "source"
        self.src.mkdir()
        self.files = {}
        self.base = b"frozen repository snapshot tar (synthetic)"
        self.add("input/base.tar.gz", self.base)
        self.add("results/_base.sarif", b'{"runs":[],"version":"2.1.0"}')
        self.add("input/README.txt", b"Synthetic blind replay\n")
        self.add("input/BASE_SHA256.txt", ("base_commit=" + "f"*40 + "\narchive_sha256=" + sha(self.base) + "\n").encode())
        self.add("results/BLINDED_CODEQL_FINDINGS.csv", b"run_id,rule,file,line\n")
        rows = []
        summaries = []
        for n in range(1, 3):
            rid = f"G{n:03}"
            patch = f"--- a/x{n}\n+++ b/x{n}\n@@ -1 +1 @@\n-a\n+b\n".encode()
            report = f"RUN_ID: {rid}\nTests not independently verified.\n".encode()
            self.add(f"input/patches/{rid}.patch", patch)
            self.add(f"input/reports/{rid}.txt", report)
            self.add(f"results/runs/{rid}/results.sarif", ('{"run_id":"'+rid+'"}').encode())
            rows.append([rid, sha(patch), sha(report), len(patch), "PASS", "PASS"])
            summaries.append([rid, "PASS", "NO", str(100 + n)])
        mhead = ["run_id", "patch_sha256", "report_sha256", "patch_bytes", "patch_apply_check", "report_run_id_check"]
        shead = ["run_id", "patch_apply", "target_present", "head_findings_all"]
        import io
        buf = io.StringIO(newline="")
        cw = csv.writer(buf)
        cw.writerow(mhead)
        cw.writerows(rows)
        self.add("input/BLINDED_MANIFEST.csv", buf.getvalue().encode())
        buf = io.StringIO(newline="")
        cw = csv.writer(buf)
        cw.writerow(shead)
        cw.writerows(summaries)
        self.add("results/BLINDED_CODEQL_SUMMARY.csv", buf.getvalue().encode())
        self.add("results/STEP4_QC.json", json.dumps({"status":"PASS","runs_expected":2,
            "runs_summarized":2,"base_archive_sha256":sha(self.base)}).encode())

    def add(self, name, raw):
        p = self.src / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
        self.files[name] = raw

    def test_full_capture_and_run_register(self):
        out = self.root / "derived"
        r=prepare_s5pair(self.src,out)
        self.assertEqual(r["run_count"],2)
        self.assertEqual(r["missing_source_files"],0)
        self.assertEqual(r["stored_source_members"],len(self.files))
        audit=json.loads((out/"INGEST_AUDIT.json").read_text())
        self.assertEqual(audit["missing_prompts"],2)
        self.assertFalse(audit["full_functional_test_validation"])
        self.assertEqual(audit["source_file_hashes"]["input/patches/G001.patch"],sha(self.files["input/patches/G001.patch"]))
        self.assertTrue(all((self.src/k).read_bytes()==v for k,v in self.files.items()))
        vault=EvidenceStore.create(self.root/"vault")
        p=out/"S5PAIR001_STEP4_BLINDED_SOURCE_EVIDENCE_DERIVED.zip"
        imp=import_archive(vault,p,origin_uri="synthetic://replay",origin_revision="sha256:"+r["archive_sha256"])
        self.assertEqual(imp["members"],len(self.files))
        cross=out/"RUN_CROSSWALK_BLINDED.json"
        mapped=register_runs(vault,cross,origin_uri="synthetic://crosswalk",origin_revision="source-test")
        self.assertEqual(mapped["runs"],2)
        with vault._open(readonly=True) as cx:
            runs=cx.execute("SELECT run_id,arm,case_id,model,analysis_status FROM experiment_runs ORDER BY run_id").fetchall()
            self.assertEqual(runs,[("G001","BLINDED_UNMAPPED",None,None,"unverified"),
                                   ("G002","BLINDED_UNMAPPED",None,None,"unverified")])
            psha=cx.execute("SELECT artifact_sha256 FROM reviewer_experiment_assets WHERE run_id='G001' AND evidence_role='generated_patch'").fetchone()[0]
            gaps=cx.execute("SELECT count(*) FROM evidence_gaps WHERE missing_role='prompt'").fetchone()[0]
        self.assertEqual(vault.bytes_for_digest(psha),self.files["input/patches/G001.patch"])
        self.assertEqual(gaps,2)
        self.assertEqual(ResearchIndex(vault).verify()["status"],"PASS")

    def test_patch_mutation_detected_without_output(self):
        self.add("input/patches/G001.patch",b"replaced patch")
        with self.assertRaisesRegex(EvidenceError,"Generated patch/report bytes differ"):
            prepare_s5pair(self.src,self.root/"derived")
        self.assertFalse((self.root/"derived").exists())

    def test_report_mutation_detected(self):
        self.add("input/reports/G001.txt",b"RUN_ID: G001\nchanged")
        with self.assertRaisesRegex(EvidenceError,"Generated patch/report bytes differ"):
            prepare_s5pair(self.src,self.root/"derived")

    def test_missing_scan_strict_or_explicit_partial(self):
        (self.src/"results/runs/G002/results.sarif").unlink()
        with self.assertRaisesRegex(EvidenceError,"Required replay artifact missing"):
            prepare_s5pair(self.src,self.root/"no")
        r=prepare_s5pair(self.src,self.root/"partial",allow_missing_scans=True)
        self.assertEqual(r["missing_source_files"],1)
        data=json.loads((self.root/"partial"/"RUN_CROSSWALK_BLINDED.json").read_text())
        self.assertNotIn("scanner_after",data["runs"][1]["files"])
        self.assertEqual(data["runs"][1]["arm"],"BLINDED_UNMAPPED")

    def test_missing_base_requires_explicit_opt_in(self):
        (self.src/"input/base.tar.gz").unlink()
        with self.assertRaises(EvidenceError):
            prepare_s5pair(self.src,self.root/"fail")
        r=prepare_s5pair(self.src,self.root/"partial",allow_missing_base=True)
        self.assertEqual(r["missing_source_files"],1)

    def test_invalid_base_hash_detected(self):
        self.add("input/base.tar.gz",b"different base")
        with self.assertRaisesRegex(EvidenceError,"Frozen base archive SHA"):
            prepare_s5pair(self.src,self.root/"derived")

    def test_duplicate_runs_rejected(self):
        raw=self.files["input/BLINDED_MANIFEST.csv"]
        self.add("input/BLINDED_MANIFEST.csv",raw+raw.decode().splitlines()[1].encode()+b"\n")
        with self.assertRaisesRegex(EvidenceError,"duplicate blinded run"):
            prepare_s5pair(self.src,self.root/"derived")

    def test_symlink_scanner_rejected_even_partial(self):
        p=self.src/"results/runs/G002/results.sarif"
        p.unlink()
        p.symlink_to(self.src/"results/runs/G001/results.sarif")
        with self.assertRaises(EvidenceError):
            prepare_s5pair(self.src,self.root/"derived",allow_missing_scans=True)

    def test_output_inside_source_refused(self):
        with self.assertRaisesRegex(EvidenceError,"outside"):
            prepare_s5pair(self.src,self.src/"output")

    def test_existing_output_refused(self):
        p=self.root/"exists"
        p.mkdir()
        with self.assertRaisesRegex(EvidenceError,"NEW"):
            prepare_s5pair(self.src,p)

if __name__=="__main__":
    unittest.main()
