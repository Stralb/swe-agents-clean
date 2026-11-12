#!/bin/bash
#SBATCH --job-name=arno_122_source_check
#SBATCH --partition=stampede
#SBATCH --time=00:08:00
#SBATCH --mem=2G
python3 - <<'PY'
import csv,json,re,collections,datetime
from pathlib import Path
home=Path.home()
data=home/'new/malicious-issue-miner-rate-smart/data'
root=home/'research_artifacts'
out=root/'mcp_uploads/jobs/first122_source_recon_20261028'
out.mkdir(parents=True,exist_ok=True)
sources={
  'precleanup_step1':data/'step1_canonical_findings_134/step1_canonical_events_134.csv',
  'original_provenance':root/'D_COMPLETE_ROOT_PROVENANCE_v1_0/01_INPUT/PROV_Phase6_FULL_PROVENANCE_455_FROZEN_v1.0.csv',
  'new70_step1':data/'final-study-snapshot-20260829/manual-review/new70-step1/Step1_Canonical_Findings_NEW70.csv'
}
views={}
for name,path in sources.items():
 with path.open(encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f); rows=list(reader); fields=reader.fieldnames
 views[name]={'path':str(path),'row_count':len(rows),'fields':fields,'sample_first_row':rows[0] if rows else None}
 if name=='original_provenance':
  original=[r for r in rows if r.get('Source Cohort')=='original122']
  all_cf=collections.Counter()
  for r in original:
   for cf in re.findall(r'CF-[0-9]{4}',r.get('Canonical Finding ID(s)') or ''):
    all_cf[cf]+=1
  views[name].update({'original_pcs':len(original),'distinct_original_pcs':len({r['Source Producing Change ID'] for r in original}),'unique_CF_IDs_from_original_pcs':len(all_cf),'canonical_id_multiplicity':dict(collections.Counter(all_cf.values())),'original_canonical_ids_first20':sorted(all_cf)[:20],'original_canonical_ids_last20':sorted(all_cf)[-20:],'original_origids':sorted(all_cf)})
 if name=='precleanup_step1':
  possible=[k for k in fields if ('canonical' in k.lower() and 'id' in k.lower()) or ('case' in k.lower() and 'id' in k.lower())]
  views[name]['likely_id_fields']=possible
  views[name]['case_examples']={k:rows[0].get(k) for k in possible}
 if name=='new70_step1':
  views[name]['qc_status_counts']=dict(collections.Counter(r.get('QC Status') for r in rows))
  views[name]['unique_cases']=len({r.get('Case ID') for r in rows})
old=views['original_provenance']['original_origids']
fs=views['precleanup_step1']['fields']
candidate_cols=[k for k in fs if 'canonical' in k.lower() and 'id' in k.lower()]
for key in candidate_cols:
  with sources['precleanup_step1'].open(encoding='utf-8-sig',newline='') as f:
   rows=list(csv.DictReader(f))
  ids={r.get(key) for r in rows}
  views['precleanup_step1']['join_using_'+key]={'common':len(ids&set(old)),'missing_count':len(set(old)-ids),'missing_sample':sorted(set(old)-ids)[:15],'other_ids':len(ids-set(old))}
del views['original_provenance']['original_origids']
(out/'COMPARISON.json').write_text(json.dumps(views,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:{a:v for a,v in data.items() if a not in ('sample_first_row','fields')} for k,data in views.items()},indent=2)[:7000])
PY