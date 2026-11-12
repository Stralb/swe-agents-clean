#!/usr/bin/env python3
"""Reassemble 30 user-returned evidence artifacts from integrity-checked chunks."""
from pathlib import Path
import ast,base64,hashlib,io,json,lzma,os,re,struct
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_ac6_v6_20261030"
OUT=D/"input"
SHA_XZ="b535fc88face73880264479675677e84e9745ebe32558b66134789425770b457"
SHA_RAW="a95ad248a78dde73384c833eab30ac19aef0543a5a9e5f964b8db47c60120e1d"
def digest(a):return hashlib.sha256(a).hexdigest()
def parse_chunks():
 parts=[]
 for i in range(7):
  t=(D/("piece_%02d.py"%i)).read_text()
  assert t.startswith("DATA = ")
  b=ast.literal_eval(t[7:].strip())
  assert isinstance(b,str) and re.fullmatch(r"[A-Za-z0-9+/=]+",b)
  parts.append(b)
 compressed=base64.b64decode("".join(parts),validate=True)
 assert digest(compressed)==SHA_XZ
 raw=lzma.decompress(compressed)
 assert digest(raw)==SHA_RAW
 assert raw[:8]==b"ARNO12V1"
 size=struct.unpack(">H",raw[8:10])[0];assert size==30
 offset=10;items={}
 for i in range(size):
  l=struct.unpack(">H",raw[offset:offset+2])[0];offset+=2
  name=raw[offset:offset+l].decode();offset+=l
  dlen=struct.unpack(">I",raw[offset:offset+4])[0];offset+=4
  value=raw[offset:offset+dlen];offset+=dlen
  assert re.fullmatch(r"(PATCH|RECEIPT|RISKS)_PILOT[0-9]{5}_(MECHANISM|PROSPECTIVE_PREDICT|PROSPECTIVE_BUILD)_R1\.(patch|json)",name),name
  assert name not in items and len(value)==dlen and dlen<1000000
  items[name]=value
 assert offset==len(raw)
 return items
def main():
 assert not OUT.exists(),"Evidence input directory already exists; refusing overwrite"
 files=parse_chunks()
 OUT.mkdir(mode=0o700)
 manifest=[]
 for name,data in sorted(files.items()):
  (OUT/name).write_bytes(data)
  manifest.append({"name":name,"sha256":digest(data),"bytes":len(data)})
 cases=("03429","03581","08152","12344","31207","32759")
 for case in cases:
  for condition in ("MECHANISM","PROSPECTIVE_BUILD"):
   p="PATCH_PILOT%s_%s_R1.patch"%(case,condition)
   rec="RECEIPT_PILOT%s_%s_R1.json"%(case,condition)
   assert files[p].startswith(b"diff --git "),p
   obj=json.loads(files[rec])
   assert obj["run_id"]=="PILOT%s_%s_R1"%(case,condition)
   if obj.get("patch_sha256"):assert obj["patch_sha256"]==digest(files[p])
   if condition=="PROSPECTIVE_BUILD":
    risk="RISKS_PILOT%s_PROSPECTIVE_PREDICT_R1.json"%case
    assert obj["prediction_report_sha256"]==digest(files[risk]),case
 (D/"INPUT_MANIFEST.json").write_text(json.dumps({"status":"ALL_12_PATCHES_RECEIPTS_VALIDATED",
  "case_ids":cases,"item_count":len(files),"lzma_sha256":SHA_XZ,
  "uncompressed_sha256":SHA_RAW,"files":manifest},indent=2))
 print("ALL_12_PATCHES_RECEIPTS_VALIDATED",len(files),flush=True)
if __name__=="__main__":main()
