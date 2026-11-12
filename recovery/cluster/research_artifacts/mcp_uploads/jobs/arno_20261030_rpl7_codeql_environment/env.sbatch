#!/bin/bash
#SBATCH --job-name=arno_rpl7_scan_env
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:08:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_codeql_environment/env_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_codeql_environment/env_%j.err
set -euo pipefail
echo START_ENV_CHECK
echo HOST="$(hostname)"
if test -f "$HOME/new/malicious-issue-miner-rate-smart/.venv/bin/activate"; then
 source "$HOME/new/malicious-issue-miner-rate-smart/.venv/bin/activate"
 echo VENV="$VIRTUAL_ENV"
else
 echo VENV_NOT_FOUND
fi
python -c 'import sys;print("PYTHON",sys.executable);print("VERSION",sys.version.split()[0])'
for candidate in "$HOME/tools/codeql/codeql" "$HOME/codeql/codeql" "$HOME/.local/bin/codeql" "$HOME/new/malicious-issue-miner-rate-smart/codeql/codeql"; do
 if test -x "$candidate"; then export CODEQL_BIN="$candidate"; break; fi
done
if test -z "${CODEQL_BIN:-}"; then CODEQL_BIN="$(command -v codeql || true)"; fi
if test -z "$CODEQL_BIN"; then echo CODEQL_NOT_FOUND; exit 2; fi
echo CODEQL_PATH="$CODEQL_BIN"
"$CODEQL_BIN" version
"$CODEQL_BIN" resolve languages | head -n 14
test -d /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips
echo SOURCE_ZIPS_PRESENT
echo FINISH_ENV_CHECK
