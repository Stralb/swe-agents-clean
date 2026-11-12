#!/bin/bash
#SBATCH --job-name=p3armzip
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p3armzip_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p3armzip_%j.err
set -euo pipefail
python3 - <<'PY'
import hashlib,json,os,pathlib,zipfile
root=pathlib.Path.home()/'research_artifacts'/'prevention_pilot_phase2'
original=root/'pilot3_context_20261017_v1'/'PILOT_08_arra-oracle-skills-cli.zip'
assert hashlib.sha256(original.read_bytes()).hexdigest()=='7f610095efdf63a1e410f474446dc5d3c22f41a50ae1d9dd2ab6ee1189d7851b'
output=root/'pilot3_case8_interventions_20261017_v1'
output.mkdir(parents=True,exist_ok=False)
requirements={
 'OW':(
  'SECURITY REQUIREMENT: Scanner-informed hindsight information',
  'A static analyzer (CodeQL rule js/insecure-temporary-file) warns about insecure creation of files under the operating-system temporary directory. This can occur when code writes to predictable paths under os.tmpdir(), including in test fixtures, especially directories named using fixed strings or process IDs. While implementing this issue, ensure newly created temporary directories/files are race-resistant and isolated across executions. Prefer atomic creation of unpredictable per-run directories via mkdtemp and exclusive creation when needed. Do not silence the analyzer or omit tests.'
 ),
 'OP':(
  'SECURITY REQUIREMENT: General implementation principle',
  'When adding code or tests that create temporary files or directories, ensure the resulting paths cannot collide across runs or expose files to unintended processes. Safely isolate new temporary workspaces and clean them up. Do not suppress diagnostics, skip tests, or change the requested functional behavior.'
 )
}
meta={
 'experiment':'Exploratory within-task O versus O+W versus O+P; NOT historical production warning recreation',
 'case_id':21942,
 'repo':'Soul-Brews-Studio/arra-oracle-skills-cli',
 'base_sha':'639150316e6f14cdc78e7dba8c6263504895b2e1',
 'original_archive_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
 'original_issue_sha256':'f04cf054cf45ad7e55366000d223affcf916010c2046ebc488cf7e2d28db247d',
 'source_packet_unchanged_except_one_additional_requirements_file':True,
 'warning_basis':'fresh baseline R1 and R2 CodeQL test-file alerts; NOT historical production warning',
 'variants':{}
}
with zipfile.ZipFile(original,'r') as src:
 entries=src.infolist()
 names=[e.filename for e in entries]
 assert len(names)==len(set(names))
 assert 'ADDITIONAL_SECURITY_REQUIREMENT.md' not in names
 assert any('issue' in n.lower() for n in names)
 (output/'SOURCE_ZIP_FILENAMES.json').write_text(json.dumps(names,indent=2)+'\n')
 for arm,(heading,requirement) in requirements.items():
  dst=output/('PILOT_08_'+arm+'.zip')
  text=heading+'\n\n'+requirement+'\n\nPriority: Keep the original issue specification unchanged, implement it completely, and satisfy this additional constraint. This packet contains no baseline patches.\n'
  with zipfile.ZipFile(dst,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as dest:
   for member in entries:
    dest.writestr(member,src.read(member.filename))
   dest.writestr('ADDITIONAL_SECURITY_REQUIREMENT.md',text)
  meta['variants'][arm]={
   'file':dst.name,'sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),
   'bytes':dst.stat().st_size,'added_instruction_sha256':hashlib.sha256(text.encode()).hexdigest(),
   'added_instruction':text
  }
  print('BUILT',arm,dst,meta['variants'][arm]['sha256'],flush=True)
 (output/'RESEARCHER_PROTOCOL.json').write_text(json.dumps(meta,indent=2)+'\n')
 print('ORIGINAL_ZIP_CONTENT_FILES',len(names),flush=True)
 print('ISSUE_CANDIDATES',json.dumps([n for n in names if 'issue' in n.lower()][:15]),flush=True)
PY
