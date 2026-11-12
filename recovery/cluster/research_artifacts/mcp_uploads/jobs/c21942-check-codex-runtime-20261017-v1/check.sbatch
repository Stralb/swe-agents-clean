#!/bin/bash
#SBATCH --job-name=case21942runtime
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:03:00
python3 - <<'PY'
import shutil,subprocess,json
binary=shutil.which('codex')
data={'codex_binary':binary,'codex_version':None,'codex_error':None}
if binary:
 try:
  v=subprocess.run([binary,'--version'],capture_output=True,text=True,timeout=15)
  data['codex_version']=v.stdout.strip()[:250]
  data['codex_exit']=v.returncode
 except Exception as e:data['codex_error']=str(e)[:250]
print(json.dumps(data),flush=True)
PY
