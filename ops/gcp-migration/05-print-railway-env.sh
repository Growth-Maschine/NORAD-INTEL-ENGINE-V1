#!/usr/bin/env bash
# Print Railway env var values for Cloud SQL cutover (paste into Railway dashboard).
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_config
require_gcloud

PUBLIC_IP="$(cloud_sql_public_ip)"
APP_PASSWORD="$(gcloud secrets versions access latest --secret="$SECRET_NAME" --project="$GCP_PROJECT")"
ENC_PASS="$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$APP_PASSWORD''', safe=''))")"

ASYNC_URL="postgresql+asyncpg://${SQL_APP_USER}:${ENC_PASS}@${PUBLIC_IP}:5432/${SQL_DATABASE}?sslmode=require"
SYNC_URL="postgresql://${SQL_APP_USER}:${ENC_PASS}@${PUBLIC_IP}:5432/${SQL_DATABASE}?sslmode=require"

cat <<EOF

Paste these into Railway → apps/api service → Variables (API + worker):

GCP_DATABASE_URL=$ASYNC_URL
GCP_DATABASE_URL_POOL=$SYNC_URL
GCP_DATABASE_URL_DIRECT=$SYNC_URL

Then redeploy both services and hit:

  GET https://<your-railway-api>/health/db

EOF
