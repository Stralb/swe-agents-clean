#!/bin/bash
#SBATCH --job-name=arc3kaggleauthcheck
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:03:00
set -euo pipefail
echo "Node=$(hostname)"
echo "USER=$USER"
echo "HOME=$HOME"
for directory in "$HOME/.kaggle" "/home-mscluster/astrauss/.kaggle" "/home/astrauss/.kaggle"; do
  if [ -d "$directory" ]; then
    echo "DIRECTORY_EXISTS: $directory"
    if [ -s "$directory/access_token" ]; then
      echo "ACCESS_TOKEN_PRESENT_NONEMPTY: $directory"
    elif [ -e "$directory/access_token" ]; then
      echo "ACCESS_TOKEN_EXISTS_EMPTY: $directory"
    else
      echo "ACCESS_TOKEN_ABSENT: $directory"
    fi
    if [ -s "$directory/kaggle.json" ]; then echo "LEGACY_KAGGLE_JSON_PRESENT: $directory"; fi
  else
    echo "DIRECTORY_ABSENT: $directory"
  fi
done
echo "No token content was read or logged."
