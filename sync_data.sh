#!/bin/bash
# ============================================================
# DSA-Portfolio — Data sync
# Bidirectional sync between local repo and Google Drive.
# Never deletes — only adds and updates files.
#
# Usage:
#   ./sync_data.sh pull     # GDrive → local (before working)
#   ./sync_data.sh push     # local → GDrive (after working)
# ============================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE="gdrive:dev-data/DSA-Portfolio"

# Folders to sync, relative to repo root.
# Format: "local_path|remote_subpath"
SYNC_MAP=(
  "proj-00-digital-engagement-analytics-for-agribusiness-growth/data|proj-00/data"
  "proj-00-digital-engagement-analytics-for-agribusiness-growth/docs|proj-00/docs"
  "proj-01-basic-to-advanced-data-eng-ETL-pipelines/data|proj-01/data"
)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

remote_exists() {
  # Returns 0 if the remote path exists, 1 otherwise.
  rclone lsf "$1" --max-depth 1 >/dev/null 2>&1
}

sync_one() {
  local direction="$1" local_path="$2" remote_path="$3"
  local src dst

  if [[ "$direction" == "pull" ]]; then
    if ! remote_exists "$REMOTE/$remote_path/"; then
      log "  skip (remote folder missing): $remote_path"
      return
    fi
    src="$REMOTE/$remote_path/"
    dst="$REPO_DIR/$local_path/"
    mkdir -p "$dst"
  else
    if [[ ! -d "$REPO_DIR/$local_path" ]]; then
      log "  skip (local folder missing): $local_path"
      return
    fi
    src="$REPO_DIR/$local_path/"
    dst="$REMOTE/$remote_path/"
  fi

  log "  $direction: $local_path"
  rclone copy "$src" "$dst" --update --progress
}

cmd_pull() {
  log "Pulling DSA-Portfolio data from GDrive"
  for entry in "${SYNC_MAP[@]}"; do
    IFS='|' read -r local_path remote_path <<< "$entry"
    sync_one pull "$local_path" "$remote_path"
  done
  log "Pull complete"
}

cmd_push() {
  log "Pushing DSA-Portfolio data to GDrive"
  for entry in "${SYNC_MAP[@]}"; do
    IFS='|' read -r local_path remote_path <<< "$entry"
    sync_one push "$local_path" "$remote_path"
  done
  log "Push complete"
}

case "${1:-}" in
  pull) cmd_pull ;;
  push) cmd_push ;;
  *)    echo "Usage: $0 {pull|push}"; exit 1 ;;
esac
