#!/bin/bash
#SBATCH --job-name=arno_find_exact
#SBATCH --partition=stampede
#SBATCH --time=00:04:00
#SBATCH --mem=3G
python3 - <<'PY'
import json,re
from pathlib import Path
root=Path.home()/'research_artifacts'
src=root/'mcp_uploads/jobs/arno_find_final_new70_D7_20261028/SOURCE_RECOVERY_INVENTORY.json'
r=json.loads(src.read_text())
out=root/'mcp_uploads/jobs/arno_find_missing_final_exact_20261028'
out.mkdir(parents=True,exist_ok=True)
hits=[]
for x in r['files']:
 p=Path(x['path']);name=p.name.lower();full=x['path'].lower()
 if '/objects/' in full or '/cache/' in full or '/repos/' in full or '/checkouts/' in full:continue
 if (name.startswith(('new70_','step1_','step2_','step3_','d7_','d4_','phase6_'))
     or 'canonical_findings' in name
     or 'producing_changes_final' in name
     or 'root_census_with_cohorts' in name
     or 'adjudication_final' in name
     or 'risk_assessment_final' in name
     or 'phase6_step2' in name):
  hits.append(x)
archives=[]
for x in r['archive_members']:
 m=[n for n in x.get('matching_member_names',[]) if any(t in Path(n).name.lower() for t in ('new70','canonical_findings','root_census','adjudication_final','step1_','step2_','step3_','d7_'))]
 if m:archives.append({'archive':x['archive'],'matching_member_names':m[:120]})
res={'inventory_bytes':src.stat().st_size,'scanned_files':r.get('visited_files'),'exact_hits':len(hits),'hits':hits[:350],'archives':archives}
(out/'EXACT_SOURCE_CANDIDATES.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'exact_hits':len(hits),'archives':len(archives),'first':hits[:12]}))
PY