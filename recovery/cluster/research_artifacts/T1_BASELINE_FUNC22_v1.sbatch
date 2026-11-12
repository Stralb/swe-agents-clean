#!/bin/bash
#SBATCH --job-name=t1base22
#SBATCH --partition=bigbatch
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_BASELINE_FUNC22_v1.out

set -euo pipefail

ROOT="$HOME/research_artifacts"
AUDIT="$ROOT/T1_PRIMARY_PILOT_PACKET_AUDIT_v1.tar.gz"
NODE22="$HOME/tools/node22/bin"

export PATH="$NODE22:$PATH"

TMP="${SLURM_TMPDIR:-/tmp}/t1base_${SLURM_JOB_ID}"
mkdir -p "$TMP"

python3 - <<'PY'
import json, tarfile
from pathlib import Path

audit = Path("/home-mscluster/astrauss/research_artifacts/T1_PRIMARY_PILOT_PACKET_AUDIT_v1.tar.gz")
out = Path("/tmp/t1base_prov.json")

with tarfile.open(audit, "r:gz") as tf:
    m = next(x for x in tf.getmembers() if x.isfile() and x.name.endswith("/SEALED_PROVENANCE.json"))
    p = json.loads(tf.extractfile(m).read().decode())["PAIR_PRIMARY"]

out.write_text(json.dumps({
    "repo": p["repository"],
    "base": p["true_base_sha"]
}))
PY

REPO=$(python3 -c 'import json; print(json.load(open("/tmp/t1base_prov.json"))["repo"])')
BASE=$(python3 -c 'import json; print(json.load(open("/tmp/t1base_prov.json"))["base"])')

git clone -q --filter=blob:none --no-checkout "https://github.com/$REPO.git" "$TMP/repo"
cd "$TMP/repo"

git fetch -q origin "$BASE"
git checkout -q --detach "$BASE"

echo "NODE=$(node -v)"
echo "NPM=$(npm -v)"

npm ci > "$ROOT/T1_BASELINE_FUNC22_INSTALL.log" 2>&1
echo "INSTALL=PASS"

set +e
npm test > "$ROOT/T1_BASELINE_FUNC22_TEST.log" 2>&1
RC=$?
set -e

echo "TEST_RC=$RC"
tail -n 40 "$ROOT/T1_BASELINE_FUNC22_TEST.log"

if [ "$RC" -eq 0 ]; then
    echo "BASELINE_TEST=PASS"
else
    echo "BASELINE_TEST=FAIL"
fi
