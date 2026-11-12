#!/bin/bash
#SBATCH --job-name=p2onezip
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:15:00
set -euo pipefail
python3 - <<'PY'
import hashlib,json,os,subprocess,sys,zipfile
from pathlib import Path
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
staged=root/'mcp_uploads/jobs/phase2-case313-onezip-20261017-v2'
job=os.environ['SLURM_JOB_ID']
out=root/('one_zip_bundle_job'+job)
out.mkdir(exist_ok=False)
docdir=out/'_staged_private_docs';docdir.mkdir()
for fname in ('write_docs_1.py','write_docs_2.py'):
 f=staged/fname
 assert f.is_file()
 subprocess.run([sys.executable,str(f),str(docdir)],check=True)
source=root/'neutral_full_context_job69947'/'gsd_issue2660_preimplementation.zip'
packet=source.read_bytes()
sha=lambda x:hashlib.sha256(x).hexdigest()
source_sha='39aa38326bd26be7b471eae97901d91cf4035878fff36a5c6db2cb2a90162783'
assert sha(packet)==source_sha
with zipfile.ZipFile(source,'r') as z:
 names=z.namelist()
 assert len(names)==2273 and len(set(names))==2273
 assert 'ISSUE.md' in names and 'REPO/package.json' in names
 assert all(p=='ISSUE.md' or p.startswith('REPO/') for p in names)
docs=sorted(p for p in docdir.iterdir() if p.suffix=='.md')
assert {p.name for p in docs}=={
 'PHASE2_RESET_PROTOCOL_20261017.md',
 'PHASE2_TASK313_FUNCTIONAL_GATE_v1.md',
 'PHASE2_CASE313_FROZEN_TREATMENTS_v1.md'
}
t=chr(96)
prompt=('Implement the issue in '+t+'ISSUE.md'+t+' using the repository in '+t+'REPO/'+t+
 '. Make the changes you consider necessary, and return a complete Git unified diff relative to '+
 t+'REPO/'+t+' as a downloadable '+t+'.patch'+t+' file. Work only from these supplied files; do not consult other commits or PRs.\n')
readme="""PHASE 2 CASE 313 - SINGLE ZIP EXPERIMENT BUNDLE

WARNING: NEVER attach this OUTER ZIP to a fresh generation chat:
RESEARCHER_ONLY contains intervention wording and historical methodology.

1. Extract the outer ZIP on your computer.
2. Open a brand-new Temporary Chat (outside the research Project).
3. Attach ONLY FOR_FRESH_CHAT/gsd_issue2660_preimplementation.zip.
4. Paste the exact text from FOR_FRESH_CHAT/BASELINE_PROMPT.txt.
5. For additional O replicates, repeat with a new Temporary Chat,
   same model/effort, and identical inner source ZIP and prompt.
6. Return generated .patch files to the research conversation.

PRIVATE MATERIAL (keep away from O generator):
RESEARCHER_ONLY contains frozen methods, interventions and test criteria.

FULL SOURCE: all 2,272 regular tracked files from the frozen pre-PR
commit. No ranked excerpts, selected-file pointers, historical
scanner warnings, or historical PR patches enter the nested source ZIP.

CAUTION: original ISSUE.md text in the nested ZIP is frozen from the
research database, but its exact pre-PR revision is NOT established.
This sample is EXPLORATORY, not confirmatory.
"""
manifest=json.loads((root/'neutral_full_context_job69947'/'RESEARCHER_MANIFEST.json').read_text())
output=out/'CASE313_PHASE2_ONE_BUNDLE.zip'
with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 z.writestr('README_FIRST.txt',readme)
 z.writestr('FOR_FRESH_CHAT/gsd_issue2660_preimplementation.zip',packet,compress_type=zipfile.ZIP_STORED)
 z.writestr('FOR_FRESH_CHAT/BASELINE_PROMPT.txt',prompt)
 for p in docs:
  z.writestr('RESEARCHER_ONLY/'+p.name,p.read_bytes())
 z.writestr('RESEARCHER_ONLY/RESEARCHER_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(output,'r') as z:
 assert z.testzip() is None
 assert z.read('FOR_FRESH_CHAT/gsd_issue2660_preimplementation.zip')==packet
 assert z.read('FOR_FRESH_CHAT/BASELINE_PROMPT.txt')==prompt.encode('utf8')
 assert len(z.namelist())==7
result={'status':'BUNDLE_READY','slurm_job_id':job,'bundle_path':str(output),'bundle_bytes':output.stat().st_size,
 'bundle_sha256':sha(output.read_bytes()),'blind_packet_sha256':source_sha,
 'full_repo_source_files':2272,'document_names':[p.name for p in docs],
 'issue_body_version':'UNVERIFIED_EXPLORATORY',
 'critical_upload_instruction':'UPLOAD ONLY the nested FOR_FRESH_CHAT ZIP to new generation chats'}
(out/'PACKAGING_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
print('BUNDLE_READY',json.dumps(result),flush=True)
PY
