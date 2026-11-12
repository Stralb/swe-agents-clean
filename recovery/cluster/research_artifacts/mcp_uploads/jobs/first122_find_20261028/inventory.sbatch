#!/bin/bash
#SBATCH --job-name=arno_find_122
#SBATCH --partition=stampede
#SBATCH --time=00:07:00
#SBATCH --mem=2G
python3 - <<'PY'
from pathlib import Path
import os,json,csv,collections,datetime,hashlib
home=Path.home()
out=home/'research_artifacts/mcp_uploads/jobs/first122_find_20261028'
out.mkdir(parents=True,exist_ok=True)
targets=[home/'research_artifacts/D_COMPLETE_ROOT_PROVENANCE_v1_0/01_INPUT/PROV_Phase6_FULL_PROVENANCE_455_FROZEN_v1.0.csv',home/'research_artifacts/D_COMPLETE_ROOT_PROVENANCE_v1_0/01_INPUT/D1_ROOT_PC_EVIDENCE_CROSSWALK_455.csv']
summaries=[]
for f in targets:
 with f.open(encoding='utf-8-sig',newline='') as fd:
  data=list(csv.DictReader(fd))
 prefix='PROV_' if 'CROSSWALK' in f.name else ''
 col={k:prefix+k for k in ('Source Cohort','Source Producing Change ID','Canonical Finding ID(s)','Frozen Broad Attribution','Broad Attribution Basis','Broad Attribution Reason','Source Cohort','Case ID')}
 co=collections.Counter(str(x.get(col['Source Cohort'])) for x in data)
 orig=[x for x in data if 'original122' in str(x.get(col['Source Cohort']))]
 pcs={x.get(col['Source Producing Change ID']) for x in orig}
 cfs=set()
 for x in orig:
  raw=str(x.get(col['Canonical Finding ID(s)']) or '')
  import re
  cfs.update(re.findall(r'CF-\\d{4}',raw))
 summaries.append({'path':str(f),'rows':len(data),'cohorts':dict(co),'orig_rows':len(orig),'distinct_orig_pcs':len(pcs),'distinct_orig_canonical_ids':len(cfs),'first_original':{k:x.get(v) for k,v in col.items()} if (x:=orig[0] if orig else None) else None,'sample_original_cf_values':[str(x.get(col['Canonical Finding ID(s)']))[:150] for x in orig[:7]]})
# Targeted path scan: no full recursive home, skip huge generated trees
scan_roots=[home/'research_artifacts',home/'new/malicious-issue-miner-rate-smart/data',home/'Documents',home/'Downloads']
matched=[]
for base in scan_roots:
 if not base.is_dir():continue
 for root,dirs,files in os.walk(base,topdown=True):
  depth=len(Path(root).relative_to(base).parts)
  dirs[:]=[d for d in dirs if d not in ('.git','.venv','node_modules','_base_extract','_base_codeql_db','gh_cache','repo_cache','checkouts','repos','packets','by_root_A','by_root_B') and depth<4]
  for name in files:
   low=name.lower()
   if (low.endswith(('.xlsx','.csv','.zip','.tar.gz','.json')) and any(t in low for t in ('manual_evaluation','step1_canonical','step2_finding','step3_attribution','new70_phase','new70_final','d7_final_root','risk_assessment_final','source_map'))):
    file=Path(root)/name
    matched.append({'path':str(file),'bytes':file.stat().st_size})
report={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'provenance_csv':summaries,'candidate_files':sorted(matched,key=lambda x:x['path'])}
(out/'FIRST122_RECOVERY_INVENTORY.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
print(json.dumps({'candidate_file_count':len(matched),'provenance_summary':summaries},default=str)[:6000])
PY