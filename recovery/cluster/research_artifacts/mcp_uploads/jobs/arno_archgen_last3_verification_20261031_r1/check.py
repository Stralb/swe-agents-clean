from pathlib import Path
import json,hashlib,zipfile
root=Path.home()/"research_artifacts"
base=root/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips"
cases={
"03581":"RPL7_RUN_887FBD20CB75",
"08152":"RPL7_RUN_23E9AAB8295A",
"12344":"RPL7_RUN_E0EDE434153B"
}
result={}
for case,run in cases.items():
 p=base/(run+".zip")
 zhash=hashlib.sha256()
 with p.open("rb") as f:
  for block in iter(lambda:f.read(1048576),b""):zhash.update(block)
 fingerprint=hashlib.sha256()
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None
  names=sorted(n for n in z.namelist() if n.startswith("REPO/") and not n.endswith("/"))
  for name in names:
   binary=z.read(name)
   rel=name.encode("utf8")
   fingerprint.update(len(rel).to_bytes(8,"big"))
   fingerprint.update(rel)
   fingerprint.update(len(binary).to_bytes(8,"big"))
   fingerprint.update(binary)
 result[case]={"input_zip_sha256":zhash.hexdigest(),"file_count":len(names),"canonical_file_fingerprint":fingerprint.hexdigest()}
dest=root/"mcp_uploads/jobs/arno_archgen_last3_verification_20261031_r1"/"ORIGINAL_SOURCE_FINGERPRINTS.json"
assert not dest.exists()
dest.write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result,indent=2),flush=True)
