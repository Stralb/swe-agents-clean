from pathlib import Path
import hashlib,zipfile,json
root=Path.home()/"research_artifacts"
source=root/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips"
cases={"03429":("RPL7_RUN_6F9E2CE56C8C.zip",241,"1b1b705eed0c73888116afd325f885428cdbfc9ff8011af629dfc89158138fdf"),
"31207":("RPL7_RUN_18A6F0AE41E9.zip",15499,"42b69d9440604450ca5953a40da6665a32698c17ee87cf52352936ba17762e3e")}
out={}
for case,(name,num,expected) in cases.items():
 p=source/name
 hz=hashlib.sha256()
 with p.open("rb") as fh:
  for chunk in iter(lambda:fh.read(1048576),b""):hz.update(chunk)
 assert hz.hexdigest()==expected,(case,"Source ZIP SHA mismatch",hz.hexdigest())
 h=hashlib.sha256()
 with zipfile.ZipFile(p) as z:
  files=sorted(n for n in z.namelist() if n.startswith("REPO/") and not n.endswith("/"))
  assert len(files)==num
  assert z.testzip() is None
  for filename in files:
   b=filename.encode();data=z.read(filename)
   h.update(len(b).to_bytes(8,"big"));h.update(b)
   h.update(len(data).to_bytes(8,"big"));h.update(data)
 out[case]={"file_count":len(files),"canonical_file_fingerprint":h.hexdigest(),"v6_zip_sha256":hz.hexdigest()}
dest=root/"mcp_uploads/jobs/arno_archgen_next2_verify_20261031_r1"/"CANONICAL_FINGERPRINTS.json"
assert not dest.exists()
dest.write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps(out,indent=2),flush=True)
