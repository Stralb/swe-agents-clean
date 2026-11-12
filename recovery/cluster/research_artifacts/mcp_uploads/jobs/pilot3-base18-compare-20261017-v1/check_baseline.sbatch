#!/usr/bin/env bash
#SBATCH --job-name=p3base18
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=00:45:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p3base18_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p3base18_%j.err
set -euo pipefail
export PATH="$HOME/tools/node/bin:$PATH"
ROOT="$HOME/research_artifacts/prevention_pilot_phase2"
OUT="$ROOT/pilot3_base18_job$SLURM_JOB_ID"
SCRATCH="/tmp/astrauss_pilot3_base18_$SLURM_JOB_ID"
test ! -e "$OUT" && test ! -e "$SCRATCH"
mkdir -p "$OUT" "$SCRATCH"
export HOME="$SCRATCH/home"
mkdir -p "$HOME"
export npm_config_cache="$SCRATCH/npm_cache"
export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
export PUPPETEER_SKIP_BROWSER_DOWNLOAD=1
curl -fLsS --retry 3 --connect-timeout 20 --max-time 180 "https://codeload.github.com/breaking-brake/cc-wf-studio/tar.gz/cb9a1de74972ccf5b732749da386115fbe0ad81d" -o "$SCRATCH/base.tar.gz"
mkdir "$SCRATCH/repo"
tar -xzf "$SCRATCH/base.tar.gz" -C "$SCRATCH/repo" --strip-components=1
cd "$SCRATCH/repo"
node --version | tee "$OUT/node_version.log"
set +e
npm ci --ignore-scripts --no-audit --no-fund > "$OUT/dependency_install.log" 2>&1
echo "$?" > "$OUT/install_exit_code.txt"
npm run compile > "$OUT/base_compile.log" 2>&1
echo "$?" > "$OUT/compile_exit_code.txt"
set -e
python3 - "$OUT" "$ROOT/pilot3_functional_job69727/rank_18/logs/project_compile.log" <<'PY'
import json,pathlib,re,sys
out=pathlib.Path(sys.argv[1]);patched=pathlib.Path(sys.argv[2])
def errors(p):
 text=p.read_text(errors='replace') if p.exists() else ''
 return [x.strip() for x in text.splitlines() if 'error TS' in x]
base=errors(out/'base_compile.log');new=errors(patched)
def norm(s):return re.sub(r'\(\d+,\d+\)','',s)
basen={norm(s) for s in base}
newn={norm(s) for s in new}
report=dict(base_compile_exit=int((out/'compile_exit_code.txt').read_text()),patched_compile_exit=2,base_error_count=len(base),patched_error_count=len(new),new_error_signatures=sorted(newn-basen),removed_error_signatures=sorted(basen-newn),comparison='same npm ci --ignore-scripts and Node 20 environment')
(out/'RESULT.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
PY
