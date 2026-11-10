#!/bin/bash
#SBATCH --job-name=arno6_modelprobe_v6
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_six_case_abc_preparation_20261030_r1/model_probe_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_six_case_abc_preparation_20261030_r1/model_probe_%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_six_case_abc_preparation_20261030_r1/probe_model_runtime_v6.py
