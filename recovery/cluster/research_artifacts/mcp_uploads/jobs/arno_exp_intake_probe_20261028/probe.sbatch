#!/bin/bash
#SBATCH --job-name=arno_exp_probe
#SBATCH --partition=stampede
#SBATCH --time=00:07:00
#SBATCH --mem=3G
python3 - <<'PY'
from pathlib import Path
import json,re,collections,hashlib,base64,zlib,lzma,sqlite3,datetime
root=Path.home()/'research_artifacts'
out=root/'mcp_uploads/jobs/arno_exp_intake_probe_20261028'
out.mkdir(parents=True,exist_ok=True)
names=['owp14_20261018_v1','seven_case_20261020','seven_minimal_info_intake_20261020','phase2_ten_20261017','screen65_iter3_20261019_transfer_v1','issue_ablation_O_rep1rep2_20261019']
samples={}
case_ids=set()
for name in names:
 d=root/'mcp_uploads'/name
 files=sorted(f for f in d.iterdir() if f.is_file())
 files_summary=[]
 for f in files:
  mt=re.search(r'(?:CASE_|USER_CASE_|ISSUE_)?(0[0-9]{4}|[1-9][0-9]{2,5})(?:_|\.|$)',f.name)
  case=int(mt.group(1)) if mt else None
  if case:case_ids.add(case)
  blob=f.read_bytes()
  files_summary.append({'filename':f.name,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),
                        'case_id_from_filename':case,'prefix':blob[:45].decode('utf-8','replace'),
                        'line_count':blob.count(b'\n')})
 samples[name]={'count':len(files),'total_bytes':sum(x['bytes'] for x in files_summary),'files':files_summary}
 if name=='screen65_iter3_20261019_transfer_v1':
  try:
   raw=b''.join(f.read_bytes().strip() for f in files)
   data=base64.b64decode(raw,validate=True)
   d=lzma.LZMADecompressor()
   decoded=d.decompress(data,max_length=65_000_000)
   meta={'encoded_characters':len(raw),'decoded_compressed_bytes':len(data),
         'uncompressed_bytes_limited':len(decoded),'eof':d.eof,'prefix':decoded[:250].decode('utf-8','replace')}
   if decoded and decoded[:1] in (b'{',b'['):
    val=json.loads(decoded)
    meta['json_type']=type(val).__name__
    meta['json_keys_or_length']=list(val)[:35] if isinstance(val,dict) else len(val)
   samples[name]['decoded_probe']=meta
  except Exception as ex:samples[name]['decoded_error']=type(ex).__name__+': '+str(ex)[:250]
 if name=='seven_case_20261020':
  dec={}
  for f in files:
   try:
    data=zlib.decompress(base64.b64decode(f.read_text().strip(),validate=True))
    dec[f.name]={'bytes':len(data),'prefix':data[:170].decode('utf-8','replace'),'first_line':data.split(b'\n')[0][:130].decode('utf-8','replace')}
   except Exception as ex:dec[f.name]={'error':type(ex).__name__+': '+str(ex)[:180]}
  samples[name]['decoded_probe']=dec
con=sqlite3.connect('file:'+str(root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite')+'?mode=ro',uri=True)
case_status={str(i):bool(con.execute('SELECT 1 FROM cases WHERE id=?',(i,)).fetchone()) for i in sorted(case_ids)}
con.close()
report={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'case_ids':case_status,
        'intake':samples}
(out/'EXPERIMENT_INTAKE_PROBE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
slim={'case_ids':case_status,'directories':{k:{'count':v['count'],'total_bytes':v['total_bytes'],'decoded_probe':v.get('decoded_probe'),'decoded_error':v.get('decoded_error')} for k,v in samples.items()}}
(out/'EXPERIMENT_INTAKE_SUMMARY.json').write_text(json.dumps(slim,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(slim,ensure_ascii=False,indent=2)[:9000])
PY