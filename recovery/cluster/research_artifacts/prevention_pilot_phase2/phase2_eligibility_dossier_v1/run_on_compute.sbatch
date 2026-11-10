#!/usr/bin/env bash
#SBATCH --job-name=p2_dossier
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:12:00
#SBATCH --output=p2_dossier_%j.out
#SBATCH --error=p2_dossier_%j.err
set -euo pipefail
ROOT="$HOME/research_artifacts/prevention_pilot_phase2"
cd "$ROOT"
source "$HOME/new/malicious-issue-miner-rate-smart/.venv/bin/activate"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/p2_dossier_${SLURM_JOB_ID}_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
tar -xzf phase2_eligibility_dossier_v1.tar.gz -C "$TMP"
python "$TMP/phase2_eligibility_dossier_v1/build_dossier.py"
tar -czf "$ROOT/case_screen_dossier_v1_RESEARCHER_ONLY.tar.gz" -C "$ROOT" case_screen_dossier_v1
sha256sum "$ROOT/case_screen_dossier_v1_RESEARCHER_ONLY.tar.gz" > "$ROOT/case_screen_dossier_v1_RESEARCHER_ONLY.tar.gz.sha256"
ls -lah "$ROOT/case_screen_dossier_v1_RESEARCHER_ONLY.tar.gz"
