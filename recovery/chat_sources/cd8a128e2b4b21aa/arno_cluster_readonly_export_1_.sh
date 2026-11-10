#!/usr/bin/env bash
# Execute on YOUR local computer (WSL/Linux/macOS), NOT on the Wits cluster.
# This script only READS the cluster via SSH. Output files are saved locally.
# Usage: bash arno_cluster_readonly_export.sh YOUR_EXISTING_SSH_TARGET [LOCAL_OUTPUT_DIR]

REMOTE="${1:-}"
if [ -z "$REMOTE" ]; then
  printf 'Usage: bash %s SSH_TARGET [LOCAL_OUTPUT_DIR]\n' "$0"
  printf 'Example: bash %s mscluster "$HOME/arno_cluster_recovery"\n' "$0"
  exit 2
fi

OUT="${2:-$HOME/arno_cluster_recovery}"
mkdir -p "$OUT" || exit 2
printf 'All output is LOCAL: %s\n' "$OUT"
printf 'Testing read-only SSH...\n'
if ! ssh "$REMOTE" 'printf "Remote user: "; id -un; printf "Remote home: %s\n" "$HOME"'; then
  printf 'SSH failed. Use the same SSH alias or host you normally use for mscluster.\n' >&2
  exit 1
fi

printf '\n[1/3] Inventory top-level home directories (remote: READ ONLY).\n'
ssh "$REMOTE" 'find "$HOME" -maxdepth 3 -type d \
  \( -name .cache -o -name .venv -o -name node_modules -o -name .git -o -name repo_cache -o -name repos \) -prune -o \
  -type d -print 2>/dev/null' \
  > "$OUT/home_directories_depth3.txt"

printf '\n[2/3] Inventory code scripts and archive filenames (remote: READ ONLY).\n'
ssh "$REMOTE" 'find "$HOME" -maxdepth 4 \
  \( -name .cache -o -name .venv -o -name node_modules -o -name .git -o -name repo_cache -o -name repos \) -prune -o \
  -type f \( -name "*.py" -o -name "*.sh" -o -name "*.sbatch" -o -name "*.ipynb" \
    -o -name "*.zip" -o -name "*.tar.gz" -o -name "*.yml" -o -name "*.yaml" \
    -o -name "pyproject.toml" -o -name "requirements*.txt" -o -name "package.json" \) \
  -print 2>/dev/null' \
  > "$OUT/candidate_sources_archives_depth4.txt"

printf '\n[3/3] Stream original miner source directly to a LOCAL archive.\n'
printf 'No TAR archive is written on the Wits cluster.\n'
if ssh "$REMOTE" 'test -d "$HOME/new/malicious-issue-miner-rate-smart"'; then
  if ssh "$REMOTE" 'cd "$HOME/new" && tar -czf - \
      --exclude=".git" --exclude="*/.git" \
      --exclude=".venv" --exclude="*/.venv" \
      --exclude="node_modules" --exclude="*/node_modules" \
      --exclude="__pycache__" --exclude="*/__pycache__" \
      --exclude=".env" --exclude=".env.*" --exclude="*/.env" --exclude="*/.env.*" \
      --exclude="*.pem" --exclude="*.key" --exclude="*.p12" \
      --exclude="*.db" --exclude="*.db-*" --exclude="*.sqlite" --exclude="*.sqlite3" \
      --exclude="*.parquet" --exclude="*.zip" --exclude="*.tar.gz" \
      --exclude="data" --exclude="*/data" \
      --exclude="distributed_spool" --exclude="*/distributed_spool" \
      malicious-issue-miner-rate-smart' \
    > "$OUT/miner_source_without_runtime_data_or_secrets.tar.gz"; then
      printf 'Created LOCAL miner source archive successfully.\n'
  else
      printf 'Source transfer failed. LOCAL archive might be incomplete.\n' >&2
      exit 1
  fi
else
  printf 'Source directory not found; check home_directories_depth3.txt.\n' >&2
fi

printf '\nLocal outputs:\n'
ls -lh "$OUT/home_directories_depth3.txt" \
       "$OUT/candidate_sources_archives_depth4.txt" \
       "$OUT/miner_source_without_runtime_data_or_secrets.tar.gz" 2>/dev/null
printf '\nBefore sharing: review file names, check for secrets, then upload the source TAR and two inventory TXT files to this chat.\n'
