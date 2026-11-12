from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import hashlib,json
root=Path.home()/"research_artifacts"
d=root/"mcp_uploads/jobs/arno_scgg_03581_v6_20261030_r1";o=d/"results"
b=root/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_03581"
h=root/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results/CASE_03581/RPL7_RUN_887FBD20CB75"
def sha(p):
 z=hashlib.sha256()
 with p.open("rb") as f:
  for chunk in iter(lambda:f.read(1048576),b""):z.update(chunk)
 return z.hexdigest()
r=json.loads((o/"RESULT.json").read_text())
assert r["status"]=="CODEQL_SCAN_COMPLETE" and r["run_id"]=="SCGG_03581_P1"
assert (r["baseline_total"],r["historical_p1_total"],r["after_total"],r["new_vs_baseline"])==(82,84,82,0)
assert r["source_files"]==397 and r["historical_p1_signatures_absent"]==2
assert sha(o/"after.sarif")==r["after_sarif_sha256"]
assert sha(o/"PATCH_SCGG_03581_P1.patch")==r["patch_sha256"]
assert sha(o/"RECEIPT_SCGG_03581_P1.json")==r["receipt_sha256"]
assert sha(b/"baseline.sarif")==json.loads((b/"RESULT.json").read_text())["sarif_sha256"]
assert sha(h/"after.sarif")==json.loads((h/"RESULT.json").read_text())["after_sarif_sha256"]
names={}
for n in ["RESULT.json","warning_delta.json","PATCH_SCGG_03581_P1.patch","RECEIPT_SCGG_03581_P1.json","after.sarif","apply_check.log","apply.log","create.log","analyze.log"]:names["scgg/"+n]=o/n
for n in ["RESULT.json","baseline.sarif"]:names["baseline/"+n]=b/n
for n in ["RESULT.json","after.sarif"]:names["historical_P1/"+n]=h/n
dst=d/"ARNO_SCGG_03581_P1_CODEQL_V6_EVIDENCE.zip"
assert not dst.exists()
with ZipFile(dst,"x",ZIP_DEFLATED,compresslevel=7) as z:
 for n,p in sorted(names.items()):z.write(p,n)
 z.writestr("README.txt","Case 03581 SCGG P1 CodeQL 2.25.6 security-extended; job 78951. Frozen full 397-file repo baseline 82, P1 84, SCGG 82, new findings ZERO. Original two warning signatures absent. SHA-256 verification passed. Functional acceptance NOT VERIFIED; no claim of complete security. Source ZIP hash in scgg/RESULT.json.\n")
with ZipFile(dst) as z: assert z.testzip() is None
info={"status":"VERIFIED_AND_PACKAGED","zip_relative_path":str(dst.relative_to(root)),"bytes":dst.stat().st_size,"sha256":sha(dst),"files":len(names)+1}
(d/"EVIDENCE_PACKAGE_INFO.json").write_text(json.dumps(info,indent=2)+"\n")
print(json.dumps(info,indent=2))
