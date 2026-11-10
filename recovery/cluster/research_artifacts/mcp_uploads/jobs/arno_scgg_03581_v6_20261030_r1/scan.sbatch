#!/bin/bash
#SBATCH --job-name=arnoSCGG03581
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_scgg_03581_v6_20261030_r1/job_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_scgg_03581_v6_20261030_r1/job_%j.err
set -euo pipefail
umask 077
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_scgg_03581_v6_20261030_r1/eval_scgg.py
