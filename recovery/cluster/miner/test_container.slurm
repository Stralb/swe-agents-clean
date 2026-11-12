#!/bin/bash
#SBATCH --job-name=test-sif
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=00:10:00
#SBATCH --mem=8G
#SBATCH --output=/home-mscluster/%u/test_sif_%j.log

set -euo pipefail

module load apptainer 2>/dev/null || module load singularity 2>/dev/null
BIN=$(command -v apptainer || command -v singularity)

SIF=/home-mscluster/$USER/old/research_env.sif

echo "Host: $(hostname)"
echo "User: $USER"
echo "SIF: $SIF"
ls -lh "$SIF"

echo "--- Python ---"
$BIN exec --nv "$SIF" python --version

echo "--- Pip ---"
$BIN exec --nv "$SIF" pip --version || true

echo "--- Git ---"
$BIN exec --nv "$SIF" git --version

echo "--- Make ---"
$BIN exec --nv "$SIF" make --version | head -n 1

echo "--- CodeQL ---"
$BIN exec --nv "$SIF" bash -lc 'which codeql || true; codeql version || true'

echo "--- Done ---"
