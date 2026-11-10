#!/bin/bash
#SBATCH --job-name=isixhosa_conda_check
#SBATCH --partition=batch
#SBATCH --time=00:04:00
#SBATCH --mem=512M
set -eu
for py in /home-mscluster/astrauss/.conda/envs/apex_env/bin/python /usr/local/bin/python3.13 /usr/bin/python3.13 /usr/bin/python3.12; do
  if [ -x "$py" ]; then
    echo "$py"
    "$py" --version
    "$py" - <<'PY'
try:
 import numpy,pandas,matplotlib
 print('OK numpy',numpy.__version__,'pandas',pandas.__version__,'matplotlib',matplotlib.__version__)
except Exception as e:
 print('MISSING',repr(e))
PY
  fi
done
