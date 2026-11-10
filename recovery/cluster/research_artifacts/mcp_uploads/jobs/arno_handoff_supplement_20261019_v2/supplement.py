#!/usr/bin/env python3
"""Transport exact original ZIPs whose only blocked files are env templates; exclude real .env secrets."""
from pathlib import Path
import zipfile,hashlib,csv,io,json,re
R=Path.home()/"research_artifacts";SRC=R/"prevention_pilot_phase2"/"owp14_allcases_packets_job71014"
OUT=R/"ARNO_CODEQL_EXPORT_20261019_ADDENDUM_V2"
if OUT.exists():raise SystemExit("Will not overwrite "+str(OUT))
OUT.mkdir(mode=0o700)
cases=[668,6104,8152,12344,21682]
template=re.compile(r"(?:^|/)\.env(?:\.[a-z0-9_-]+)*\.(?:example|sample|template|dist)$",re.I)
secrets=[re.compile(x) for x in (rb"AIza[\w-]{25,}",rb"gh[pousr]_[\w-]{25,}",rb"sk-[\w-]{25,}",rb"AKIA[A-Z0-9]{16}",rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----")]
rows=[]
archive=OUT/"01_ADDITIONAL_ORIGINAL_INPUTS_TEMPLATE_ONLY.zip"
with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_STORED,allowZip64=True) as dest:
 for cid in cases:
  for arm in ("O","W","P"):
   p=SRC/("CASE_%05d_%s.zip"%(cid,arm))
   with zipfile.ZipFile(p) as z:
    names=[x.filename for x in z.infolist() if re.search(r"(^|/)\.env", x.filename, re.I)]
    assert all(template.search(x) for x in names),(p.name,names)
    for name in names:
     x=z.read(name)
     assert not any(r.search(x) for r in secrets),("template appears to contain token",p.name,name)
   raw=p.read_bytes()
   dest.writestr("01_ORIGINAL_OWP_INPUTS/"+p.name,raw,compress_type=zipfile.ZIP_STORED)
   rows.append({"filename":p.name,"source_path":str(p),"case_id":cid,"arm":arm,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"preservation":"RAW_IDENTICAL"})
with zipfile.ZipFile(archive) as z:assert z.testzip() is None and len(z.namelist())==15
h=hashlib.sha256(archive.read_bytes()).hexdigest()
for arm in ("O","W","P"):
 p=SRC/("CASE_15151_%s.zip"%arm)
 with zipfile.ZipFile(p) as z:
  names=[x for x in z.namelist() if x.rsplit("/",1)[-1] in (".env",".env.production")]
  lengths=[len(z.read(name)) for name in names]
  assignments=[sum(1 for line in z.read(name).splitlines() if b"=" in line and not line.lstrip().startswith(b"#")) for name in names]
 print("SENSITIVE_INPUT_EXCLUDED",p.name,"env_members",len(names),"member_lengths",lengths,"assignment_lines",assignments,flush=True)
(OUT/"MISSING_SENSITIVE_INPUTS.md").write_text("# Original input exclusions\nThe original O/W/P input ZIPs for CASE_15151 contain .env and .env.production entries; preserving their original ZIP bytes would also transmit these files. To honor the explicit secret-exclusion request they were NOT included. The originals remain unchanged on Wits under prevention_pilot_phase2/owp14_allcases_packets_job71014. No redacted copy is presented as original.\n")
s=io.StringIO();w=csv.DictWriter(s,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
(OUT/"ADDENDUM_INDEX.csv").write_text(s.getvalue())
(OUT/"SUMMARY.json").write_text(json.dumps({"stage":"COMPLETE","input_zip_count":len(rows),"part_zip":archive.name,"part_bytes":archive.stat().st_size,"part_sha256":h,"excluded_case":"15151","excluded_count":3},indent=2)+"\n")
print("ADDENDUM_COMPLETE",archive,archive.stat().st_size,h,flush=True)
