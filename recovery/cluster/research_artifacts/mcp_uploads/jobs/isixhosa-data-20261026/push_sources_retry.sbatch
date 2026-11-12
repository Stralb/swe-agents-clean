#!/bin/bash
#SBATCH --job-name=publish_isixhosa_data_retry
#SBATCH --partition=batch
#SBATCH --time=00:09:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
set -euo pipefail
source_dir=/home-mscluster/astrauss/isixhosa-upload
repo=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/isixhosa-data-20261026/clean-repository-checkout
a=375c5864e180717f34403287e502cf8812b038baf5a8fb4ae8ee8cdb2be321d5
b=41fc2a7cab043025df3e2127ee21878c5ae5b6457a8bd55b5e210fb1c50cde10
echo "$a  $source_dir/TxtLangFiles1870-1894_TB.zip" | sha256sum -c -
echo "$b  $source_dir/1. TxtFiles1870-1894_TB.zip" | sha256sum -c -
if [ ! -d "$repo/.git" ]; then
    git clone --quiet https://github.com/Stralb/isixhosa-archive-nlp.git "$repo"
fi
cd "$repo"
git checkout -q main
git fetch -q origin main
git merge --ff-only origin/main
cp "$source_dir/TxtLangFiles1870-1894_TB.zip" data/TxtLangFiles1870-1894_TB.zip
cp "$source_dir/1. TxtFiles1870-1894_TB.zip" data/TxtFiles1870-1894_TB.zip
echo "$a  data/TxtLangFiles1870-1894_TB.zip" | sha256sum -c -
echo "$b  data/TxtFiles1870-1894_TB.zip" | sha256sum -c -
git add data/TxtLangFiles1870-1894_TB.zip data/TxtFiles1870-1894_TB.zip
git diff --cached --stat
if git diff --cached --quiet; then echo ALREADY_TRACKED; exit 0; fi
git -c user.name="Arno Strauss" -c user.email="arnostrauss13@gmail.com" commit -m "data: add both original verified newspaper archives"
export GIT_TERMINAL_PROMPT=0
echo PUSH_ATTEMPT
if git push origin HEAD:main; then echo PUSH_SUCCESS; else echo PUSH_FAILED_AUTH_OR_PROTECTION; exit 18; fi
git rev-parse HEAD
