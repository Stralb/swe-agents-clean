#!/bin/bash
#SBATCH --job-name=arno_source_locator
#SBATCH --partition=stampede
#SBATCH --time=00:09:00
#SBATCH --mem=2G
python3 - <<'PY'
import os,re,json,hashlib
from pathlib import Path
R=Path.home()/'research_artifacts'
O=R/'mcp_uploads/jobs/arno_source_discovery_20261028'
O.mkdir(parents=True,exist_ok=True)
sha_targets={'d07517a4f118369071a196219470a094f46abd2cacdd1355fdc7cbf27dc738c3':'NEW70_FINAL_FINDINGS','a7f2a5416d07c5321974ec24ce7360864a4fe769d0deeddc3a264c026eef9cb7':'NEW70_FINAL_CHANGES','c480a83c1d5e0672453802df1f1741499c6348c003e56fc186e3a2249fffc8ad':'C5_ARCHIVE','3cbc412b64acf791580883884f9a1ff1e4b2c4cb4921ed768b3e76451c78f5ec':'C6_ARCHIVE','459bb1d70505ea447ff0f4c23c7ec468afa7d1196bc0fd9bbe35a2ea482e6511':'C7_CSV','bc7d13114fa4c661011f5f2ad1106cf4b31b9feccbafd1560b880fb0cd1d0798':'T1_ARCHIVE'}
pat=re.compile('new70|step1|phase6|canonical|producing|d7|matched|c5_|c6_|c7_|t1_v9|restoration',re.I)
res=[];n=0
for base,ds,fs in os.walk(R):
 ds[:]=[d for d in ds if d not in ('node_modules','.git','.venv')]
 for name in fs:
  n+=1
  if not pat.search(name):continue
  p=Path(base)/name
  try: sz=p.stat().st_size
  except OSError:continue
  record={'name':str(p.relative_to(R)),'size':sz}
  if sz<=15000000 and p.suffix.lower() in ('.csv','.gz','.zip','.txt','.db','.sqlite'):
   try:
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    if digest in sha_targets:record['exact_target_match']=sha_targets[digest]
   except OSError:pass
  res.append(record)
rep={'files_examined':n,'matching_names':len(res),'exact_matches':[x for x in res if 'exact_target_match' in x],'items':res[:2000]}
(O/'DISCOVERY.json').write_text(json.dumps(rep,indent=2)+'\n')
print(json.dumps({'status':'COMPLETE','files_examined':n,'names':len(res),'matches':rep['exact_matches']}))
PY