# Railway cutover — Cloud SQL

## 1. Allow Railway to reach Cloud SQL

Railway → service → Settings → Networking → copy **outbound IPv4**.

GCP Console → SQL → `norad-pg-prod` → Connections → **Authorized networks** → add `YOUR.IP/32`.

Or via CLI:

```bash
gcloud sql instances patch norad-pg-prod \
  --authorized-networks=YOUR.IP/32 \
  --project=norad-498414
```

## 2. Generate env vars

```bash
cd ops/gcp-migration
cp config.env.example config.env   # set GCP_PROJECT if needed
./05-print-railway-env.sh
```

Copy the three `GCP_DATABASE_URL*` lines into your Railway API service variables.

Remove any old `SUPABASE_*` variables.

## 3. Redeploy and verify

```bash
curl -s https://YOUR-RAILWAY-API/health/db | jq .
```

Expect Postgres and Redis both OK.

## 4. Smoke test

- One Web Discovery cluster run
- One research run
