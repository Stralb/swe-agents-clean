#!/bin/bash
#SBATCH --job-name=p3r2funcfix
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=00:45:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/pilot3_r2funcfix_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/pilot3_r2funcfix_%j.err
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$HOME/tools/bun/bin:$PATH"
export SLURM_ARRAY_TASK_ID=0
export SLURM_ARRAY_JOB_ID="$SLURM_JOB_ID"
python3 - <<'PY'
import hashlib,os,pathlib,subprocess
root=pathlib.Path.home()/'research_artifacts'/'prevention_pilot_phase2'
patch=root/'pilot3_r2_job69745'/'PILOT_08_R2.patch'
expect='5990e260d07289bfa98593a735b0a8dd76db84e3e7c7f752e69d284bb892ed1e'
assert hashlib.sha256(patch.read_bytes()).hexdigest()==expect
original=(root/'pilot3_functional_v1.sbatch').read_text()
old='0e013e16a4c8f772ae404fddfbb0faad100ed13e041ecf7ab594e6b4a01bca4b'
assert original.count(old)==1
script=original.replace(old,expect)
needle="patchmap=ast.literal_eval(line.partition('=')[2]);patch=zlib.decompress(base64.b64decode(patchmap[str(rank)]))"
assert script.count(needle)==1
script=script.replace(needle,"patch=(ROOT/'pilot3_r2_job69745'/'PILOT_08_R2.patch').read_bytes()")
assert script.count('pilot3_functional_job')==1
script=script.replace('pilot3_functional_job','pilot3_functional_r2fix_job')
script=script.replace('pilot3_functional_%A_%a','pilot3_functional_r2fix_%A_%a')
scratch=pathlib.Path(os.environ.get('SLURM_TMPDIR') or '/tmp')/('p3r2func_runner_'+os.environ['SLURM_JOB_ID'])
scratch.mkdir(parents=True,exist_ok=False)
runner=scratch/'run.sh';runner.write_text(script)
print('RUN',patch,'on fresh base; SHA',expect,flush=True)
p=subprocess.run(['bash',str(runner)])
print('EXIT',p.returncode,flush=True)
raise SystemExit(p.returncode)
PY
