#!/bin/bash
#SBATCH --job-name=isixhosa_exploratory_20261026
#SBATCH --partition=batch
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
set -euo pipefail
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
repo="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/isixhosa-data-20261026/clean-repository-checkout"
branch="research/exploratory-metric-coupling-2026-10-26"
test -d "$repo/.git"
cd "$repo"
echo "Git initial head: $(git rev-parse HEAD)"
git fetch origin "$branch"
git checkout -B "$branch" "origin/$branch"
test -z "$(git status --porcelain)"
echo "Python environment:"
python3 --version
python3 - <<'PY'
import numpy,pandas,matplotlib
print("numpy",numpy.__version__,"pandas",pandas.__version__,"matplotlib",matplotlib.__version__)
PY
echo "FROZEN SOURCE INPUT HASHES"
sha256sum results/raw/segmentation.csv results/raw/bigram.csv results/segmentation.csv results/bigram.csv
echo "RUN EXPLORATORY ANALYSES"
python3 src/analysis/metric_relationships.py --root .
echo "CHECK DETERMINISTIC OUTPUTS"
python3 src/analysis/metric_relationships.py --root . --verify
echo "CHECK GENERATED FILES"
ls -lh results/exploratory results/figures/*1888.png
echo "STAGE ONLY NEW EXPLORATORY ARTIFACTS"
git add results/exploratory/issue_allocation_effects.csv \
        results/exploratory/metric_coupling_summary.csv \
        results/exploratory/length_quartile_effects.csv \
        results/exploratory/robustness_summary.csv \
        results/exploratory/analysis_provenance.json \
        results/figures/metric_coupling_1888.png \
        results/figures/length_quartiles_1888.png
git diff --cached --stat
git -c user.name="Arno Strauss" -c user.email="arnostrauss13@gmail.com" commit \
    -m "results: commit post-hoc issue-level and length-stratified evidence"
export GIT_TERMINAL_PROMPT=0
git push origin "HEAD:$branch"
echo "COMPLETED SHA"
git rev-parse HEAD
