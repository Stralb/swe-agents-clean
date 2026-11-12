#!/bin/bash
#SBATCH --job-name=isixhosa_env_check
#SBATCH --partition=batch
#SBATCH --time=00:04:00
#SBATCH --mem=512M
set -u
echo "PYTHON PATHS"
which -a python python3 python3.13 python3.12 python3.11 python3.10 pip pip3 2>/dev/null || true
echo "MODULES"
type module 2>/dev/null || true
if type module >/dev/null 2>&1; then module avail python 2>&1 | head -n 40; fi
echo "VENV OR CONDA LOCATIONS"
for d in /home-mscluster/astrauss/miniconda3 /home-mscluster/astrauss/anaconda3 /home-mscluster/astrauss/.conda/envs /home-mscluster/astrauss/.virtualenvs /home-mscluster/astrauss/research_artifacts/venv /home-mscluster/astrauss/research_artifacts/.venv; do if [ -d "$d" ]; then echo "$d"; ls "$d" | head -n 12; fi; done
echo "PYTHON PIP"
python3 -m pip --version 2>&1 || true
echo "ENV DIAGNOSTIC COMPLETE"
