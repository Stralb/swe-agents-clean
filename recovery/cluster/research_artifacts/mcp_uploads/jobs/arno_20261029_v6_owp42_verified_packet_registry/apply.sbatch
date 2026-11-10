#!/bin/bash
#SBATCH --job-name=arno_owp42_append
#SBATCH --partition=batch
#SBATCH --dependency=afterok:77995
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_v6_owp42_verified_packet_registry/apply_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_v6_owp42_verified_packet_registry/apply_%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_v6_owp42_verified_packet_registry/registry.py --apply
