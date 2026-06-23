#!/usr/bin/env bash
# Shared helpers for NORAD Cloud SQL ops (Railway cutover, network hardening).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export PATH="/opt/homebrew/opt/libpq/bin:/opt/homebrew/share/google-cloud-sdk/bin:${PATH:-}"

load_config() {
  if [[ -f "$SCRIPT_DIR/config.env" ]]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/config.env"
  fi
  : "${GCP_PROJECT:?Set GCP_PROJECT in ops/gcp-migration/config.env}"
  : "${GCP_REGION:=europe-west2}"
  : "${SQL_INSTANCE:=norad-pg-prod}"
  : "${SQL_DATABASE:=norad}"
  : "${SQL_APP_USER:=norad_app}"
  : "${SECRET_NAME:=norad-db-password}"
}

require_gcloud() {
  command -v gcloud >/dev/null || { echo "gcloud not found. brew install google-cloud-sdk"; exit 1; }
  if ! gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q .; then
    echo "Run: gcloud auth login && gcloud config set project $GCP_PROJECT"
    exit 1
  fi
}

cloud_sql_public_ip() {
  gcloud sql instances describe "$SQL_INSTANCE" \
    --project="$GCP_PROJECT" \
    --format='value(ipAddresses[0].ipAddress)'
}

instance_connection_name() {
  echo "${GCP_PROJECT}:${GCP_REGION}:${SQL_INSTANCE}"
}
