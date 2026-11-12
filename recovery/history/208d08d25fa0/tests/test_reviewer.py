"""Review queries should retrieve original evidence without inventing labels."""
from __future__ import annotations
import hashlib, json, tempfile, unittest, zipfile
from pathlib import Path
from openpyxl import Workbook
from src.repro_store import EvidenceStore
from src.repro_store.importers import import_workbook, import_archive, register_runs
from src.repro_store.reviewer import ReviewerView


class ReviewerTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.store=EvidenceStore.create(self.root/"store")
        self.view=ReviewerView(self.store)
        wb=Workbook()
        ws=wb.active
        ws.title="Issue_PR_Master_122"
        ws.append(["Case ID","Instruction Specificity","Upstream Pattern"])
        ws.append([154,"Problem-only","Feature"]) 
        ws=wb.create_sheet("Step1_Canonical_Findings")
        ws.append(["Canonical Finding ID","Case ID","Finding Family"])
        ws.append(["CF-0002",154,"CodeQL warning"]) 
        ws=wb.create_sheet("Step2_Finding_Changes")
        ws.append(["Producing Change ID","Case ID","Canonical Finding ID","Finding-Producing Change"])
        ws.append(["PC-0001",154,"CF-0002","Changed a regex"])
        self.path=self.root/"source.xlsx"
        wb.save(self.path)
        import_workbook(self.store,self.path,origin_uri="wits://122",origin_revision="source-hash:"+hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_case_graph_joins_finding_and_change_without_guessing(self):
        case=self.view.case_dossier(154)
        self.assertEqual(case["case_id"],"154")
        types={x["unit_type"] for x in case["units"]}
        self.assertEqual(types,{"workflow","finding","producing_change"})
        rels={x["relation"] for x in case["edges"]}
        self.assertTrue({"finding_in_workflow","change_in_workflow","produced_finding"}.issubset(rels))
        labels={a["label"]:a["value"] for u in case["units"] for a in u["source_recorded_labels"]}
        self.assertEqual(labels["instruction_specificity"],"Problem-only")
        self.assertEqual(labels["producing_change_description"],"Changed a regex")
        self.assertEqual(case["explicit_runs"],[])

    def test_run_dossier_requires_real_mapping(self):
        self.assertEqual(self.view.run_dossier("BLINDED","G001")["status"],"NO_EXPLICIT_RUN_MAPPING_IN_LOCAL_CATALOG")
        p=self.root/"source.zip"
        patch=b"--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+new\n"
        with zipfile.ZipFile(p,"w") as z:z.writestr("patches/G001.patch",patch)
        archive=import_archive(self.store,p,origin_uri="wits://sample.zip",origin_revision="frozen:v1")
        m={"schema_version":1,"source_archive_sha256":archive["source_sha256"],
           "study_id":"BLINDED","protocol_revision":"source-reported", "runs":[
             {"run_id":"G001","arm":"BLINDED_UNMAPPED","case_id":None,
              "files":{"generated_patch":"patches/G001.patch"}}]}
        f=self.root/"run.json"
        f.write_text(json.dumps(m))
        register_runs(self.store,f,origin_uri="source://crosswalk",origin_revision="source:v1")
        result=self.view.run_dossier("BLINDED","G001")
        self.assertEqual(result["arm"],"BLINDED_UNMAPPED")
        self.assertIsNone(result["case_id"])
        self.assertEqual(result["assets"][0]["role"],"generated_patch")
        self.assertTrue(result["assets"][0]["byte_integrity_pass"])
        self.assertEqual({x["role"] for x in result["missing_roles"]},{"prompt","scanner_after"})
        coverage=self.view.study_coverage("BLINDED")
        self.assertEqual(coverage["runs"],1)
        self.assertEqual(coverage["recorded_blinded_runs"],1)
        self.assertEqual(coverage["runs_without_case"],1)
        self.assertEqual(coverage["roles_with_bytes"]["generated_patch"],1)

if __name__=="__main__":unittest.main()
