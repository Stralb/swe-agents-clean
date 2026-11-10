#!/bin/bash
#SBATCH --job-name=verify_isixhosa_zips
#SBATCH --partition=batch
#SBATCH --time=00:06:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=512M
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/isixhosa-data-20261026/verify_sources-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/isixhosa-data-20261026/verify_sources-%j.err
set -euo pipefail
d=/home-mscluster/astrauss/isixhosa-upload
printf 'NODE: '; hostname
printf 'UPLOADED FILES:\n'
ls -lh "$d/TxtLangFiles1870-1894_TB.zip" "$d/1. TxtFiles1870-1894_TB.zip"
printf 'SHA256:\n'
sha256sum "$d/TxtLangFiles1870-1894_TB.zip" "$d/1. TxtFiles1870-1894_TB.zip"
printf 'GIT COMMAND:\n'
command -v git
printf 'SSH IDENTITY CHECK (non-sensitive, public ref access only):\n'
timeout 20s git ls-remote git@github.com:Stralb/isixhosa-archive-nlp.git HEAD 2>&1 | head -n 5 || true
printf 'HTTPS READ CHECK:\n'
timeout 20s git ls-remote https://github.com/Stralb/isixhosa-archive-nlp.git HEAD 2>&1 | head -n 5 || true
printf 'LOCAL REPO PRESENCE:\n'
if [ -d /home-mscluster/astrauss/isixhosa-archive-nlp/.git ]; then echo "home clone present"; else echo "home clone absent"; fi
if [ -d /home-mscluster/astrauss/research_artifacts/isixhosa-archive-nlp/.git ]; then echo "research clone present"; else echo "research clone absent"; fi
printf 'DIAGNOSTIC COMPLETE\n'