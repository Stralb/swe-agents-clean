#!/bin/bash
#SBATCH --job-name=SCGG12344
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1/12344_job_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1/12344_job_%j.err
set -euo pipefail
umask 077
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1/evaluate.py 12344
