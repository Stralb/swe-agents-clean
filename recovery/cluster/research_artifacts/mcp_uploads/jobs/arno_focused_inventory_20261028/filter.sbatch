#!/bin/bash
#SBATCH --job-name=arno_inventory_filter
#SBATCH --partition=stampede
#SBATCH --time=00:03:00
#SBATCH --mem=1G
python3 - <<'PY'
import json
from pathlib import Path
root=Path.home()/'research_artifacts'
r=json.loads((root/'mcp_uploads/jobs/arno_find_final_new70_D7_20261028/SOURCE_RECOVERY_INVENTORY.json').read_text())
out=root/'mcp_uploads/jobs/arno_focused_inventory_20261028'
out.mkdir(parents=True,exist_ok=True)
eligible=[]
for x in r['files']:
 p=Path(x['path']);low=p.name.lower();full=x['path'].lower()
 if '/.git/' in full or '/objects/' in full or '/real122_repo_cache/' in full:continue
 if any(t in low for t in ('new70','d7','adjudic','final_root','final_m_root','step1_canonical','step2_finding','step3_attribution','phase6_')):eligible.append(x)
archive=[]
for x in r['archive_members']:
 if any(t in str(x.get('matching_member_names',[])).lower() for t in ('new70','step1','step2','step3','d7','final_root','adjudic')):
  archive.append({'archive':x['archive'],'matching_member_names':x.get('matching_member_names',[])[:60]})
summary={'scanned_files':r['visited_files'],'eligible_files_count':len(eligible),'eligible_files':eligible[:300],'archive_candidates':archive,'interesting_directories':[x for x in r['directories'] if any(z in x.lower() for z in ('new70','adjudic','phase6','d7'))][:150]}
(out/'FOCUSED_LIST.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'files':len(eligible),'archive_candidates':len(archive)}))
PY