#!/bin/bash
#SBATCH --job-name=arno_v6_baseline_preflight
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:20:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_v6_exact_baseline_registry/preflight_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_v6_exact_baseline_registry/preflight_%j.err
set -euo pipefail
python3 -m py_compile /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_v6_exact_baseline_registry/register.py
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_v6_exact_baseline_registry/register.py
