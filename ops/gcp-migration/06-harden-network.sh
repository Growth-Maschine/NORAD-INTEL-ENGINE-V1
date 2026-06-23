#!/usr/bin/env bash
# Tighten Cloud SQL network after Railway cutover is verified.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_config
require_gcloud

echo "Clearing authorized networks (blocks public internet access except Cloud SQL connector paths) ..."
gcloud sql instances patch "$SQL_INSTANCE" \
  --clear-authorized-networks \
  --project="$GCP_PROJECT"

echo "Done. Railway public-IP access removed."
echo "Use Cloud SQL Auth Proxy for local DDL, or move API to Cloud Run with private IP."
