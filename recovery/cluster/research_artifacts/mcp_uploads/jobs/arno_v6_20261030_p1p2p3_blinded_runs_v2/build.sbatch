#!/bin/bash
#SBATCH --job-name=arno_rpl7_blind_v2
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=02:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/build_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/build_%j.err
set -euo pipefail
python3 -m py_compile /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/build.py
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/build.py
