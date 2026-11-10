#!/bin/bash
#SBATCH --job-name=arno_merge_v05
#SBATCH --partition=stampede
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G

set -euo pipefail
ROOT="$HOME/research_artifacts"
RUN="$ROOT/mcp_uploads/jobs/arno_capsule_merge_v05_20261028"
MASTER="$ROOT/ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
ARCHIVE="$RUN/ARNO_Research_Source_Evidence_Capsule_v05_20261028.sqlite.xz"
CAPSULE="$RUN/ARNO_Research_Source_Evidence_Capsule_v05_20261028.sqlite"
MERGER="$RUN/merge_arno_capsule_v05.py"
REPORT="$RUN/V05_MERGE_REPORT.json"
test -f "$MASTER"
test -f "$ARCHIVE"
test -f "$MERGER"
test ! -e "$REPORT"
printf '%s  %s\n' '07b2d88d321f0d9d6b5b2b55b28a92f3d5d84cf13f919affe170c5620d90361a' "$ARCHIVE" | sha256sum -c -
printf '%s  %s\n' 'e92d9e777306fba1055f5ddbd9ce3989294c884baee57db4df6344cff0b29d5e' "$MERGER" | sha256sum -c -
if [ ! -f "$CAPSULE" ]; then
    xz -dc -- "$ARCHIVE" > "$CAPSULE.tmp"
    mv -- "$CAPSULE.tmp" "$CAPSULE"
fi
printf '%s  %s\n' 'c7df4808e38782a93b93d61684cdc1f485060301a005ea5d6760f8173af37948' "$CAPSULE" | sha256sum -c -
python3 "$MERGER" --master "$MASTER" --capsule "$CAPSULE" --report "$REPORT"
