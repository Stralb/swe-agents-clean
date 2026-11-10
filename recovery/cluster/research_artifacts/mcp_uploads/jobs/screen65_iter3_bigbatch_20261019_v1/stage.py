#!/usr/bin/env python3
"""Stage 65 user third-iteration patches with byte-for-byte transfer verification; never execute patches."""
import base64,csv,hashlib,io,json,os,re,tarfile
from pathlib import Path,PurePosixPath
R=Path.home()/"research_artifacts"
DIR=R/"mcp_uploads/screen65_iter3_20261019_transfer_v1"
OUT=R/"prevention_pilot_phase2/screen65_iter3_staged_20261019_v2_bigbatch"
OUT.mkdir(parents=True,exist_ok=False)
MANIFEST={"bytes":382568,"sha256":"f056afba155916915a7fb6613a4a9fa11dc0940f3a4ac5f6deae46359941aee4",
          "original_uploaded_zip_sha256":"58f8d4ee577f964090571e18aa83e1cfb08c97d63799a32007d4288ce0cc8a1d"}
pieces=[]
for i in range(1,48):
 f=DIR/("chunk_%02d.txt"%i)
 assert f.is_file(),("MISSING_TRANSFER_CHUNK",i)
 chunk=f.read_text("ascii").strip()
 assert len(chunk)==(4092 if i==47 else 11000),(i,len(chunk))
 assert re.fullmatch("[A-Za-z0-9+/=]+",chunk),("BAD_CHUNK",i)
 pieces.append(chunk)
encoded="".join(pieces)
assert len(encoded)==510092
raw=base64.b64decode(encoded,validate=True)
assert len(raw)==MANIFEST["bytes"] and hashlib.sha256(raw).hexdigest()==MANIFEST["sha256"],"TRANSFER_SHA_ERROR"
(OUT/"SCREEN65_ITER3_TRANSFER_ORIGINAL.tar.xz").write_bytes(raw)
patchdir=OUT/"patches";patchdir.mkdir()
with tarfile.open(fileobj=io.BytesIO(raw),mode="r:xz") as tf:
 members=tf.getmembers()
 assert len(members)==66 and all(m.isfile() for m in members)
 names=[m.name for m in members]
 assert len(set(names))==66
 assert names.count("RESULTS_INDEX.csv")==1
 records=list(csv.DictReader(io.StringIO(tf.extractfile("RESULTS_INDEX.csv").read().decode("utf-8-sig"))))
 assert len(records)==65 and set(records[0])=={"case_id","status","filename","notes"}
 assert set(x["status"] for x in records)=={"patched","partial_patch"}
 seen=set();rows=[]
 for record in records:
  fname=record["filename"]
  assert re.fullmatch(r"O_CASE_\d{5}\.patch",fname) and fname in names
  assert record["case_id"]=="CASE_"+fname.split("CASE_")[1][:5]
  cid=int(fname.split("CASE_")[1][:5]);assert cid not in seen;seen.add(cid)
  item=tf.extractfile(fname)
  assert item is not None
  buf=item.read()
  assert 0<len(buf)<2_000_000 and buf.startswith(b"diff --git ")
  assert b"\x00" not in buf,("BINARY_PATCH_NOT_SUPPORTED",cid)
  assert b"new file mode 120000" not in buf and b"old mode 120000" not in buf
  heads=re.findall(rb"^diff --git a/([^\r\n]+) b/([^\r\n]+)",buf,re.M)
  assert heads,("MISSING_GIT_DIFF",cid)
  changed=[]
  for left,right in heads:
   assert left==right,("RENAME_CHANGE_REQUIRES_REVIEW",cid)
   rel=PurePosixPath(left.decode("utf8"))
   assert not rel.is_absolute() and ".." not in rel.parts and ".git" not in rel.parts
   changed.append(str(rel))
  name="CASE_%05d.patch"%cid
  (patchdir/name).write_bytes(buf)
  rows.append({"case_id":cid,"status":record["status"],"patch_filename":name,
    "uploaded_filename":fname,"patch_bytes":len(buf),
    "patch_sha256":hashlib.sha256(buf).hexdigest(),
    "changed_files":changed,"notes":record["notes"][:400]})
 assert len(seen)==65
 (OUT/"RESULTS_INDEX_ORIGINAL.csv").write_bytes(tf.extractfile("RESULTS_INDEX.csv").read())
manifest={"status":"STAGED","iteration":3,"transfer":MANIFEST,"patch_count":len(rows),
  "case_ids":sorted(seen),"patches":sorted(rows,key=lambda r:r["case_id"])}
(OUT/"MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n")
print("ITER3_PATCH_STAGE_READY",str(OUT),"cases",len(rows),"SHA",MANIFEST["sha256"],flush=True)
