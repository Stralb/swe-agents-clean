#!/bin/bash
#SBATCH --job-name=p3owretry
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p3owretry_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p3owretry_%j.err
set -euo pipefail
export SLURM_ARRAY_TASK_ID=1
export SLURM_ARRAY_JOB_ID="$SLURM_JOB_ID"
bash "$HOME/research_artifacts/prevention_pilot_phase2/pilot3_case8_intervention_patches_20261017_v1/pilot3_case8_interventions_eval.sbatch"
