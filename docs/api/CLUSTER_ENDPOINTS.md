# Cluster API — testing reference

Internal admin surface for the **Search Clusters** page. Part of **Phase 0** in [API_CONTRACT_PLAN.md](./API_CONTRACT_PLAN.md).

Base path: `/api/web-discovery`

---

## Endpoints (5)

| Method | Path | Page use | Auth in prod (`DEBUG=false`) |
|--------|------|----------|------------------------------|
| `GET` | `/clusters` | List + summary metrics | `X-Admin-Token` |
| `GET` | `/clusters/{id}` | Cluster detail | `X-Admin-Token` |
| `POST` | `/clusters` | Create cluster | `X-Admin-Token` |
| `PUT` | `/clusters/{id}` | Edit cluster | `X-Admin-Token` |
| `DELETE` | `/clusters/{id}` | Delete cluster | `X-Admin-Token` |

**Phase 0 scope only.** Queries, runs, articles under `/api/web-discovery/*` are untouched — no admin gate yet.

---

## What changed (code)

All **5 cluster** routes use `app/core/admin_auth.require_admin`:

- `GET /clusters`
- `GET /clusters/{id}`
- `POST /clusters`
- `PUT /clusters/{id}`
- `DELETE /clusters/{id}`

Nothing else was changed. Settings and other routers were not touched.

---

## Request / response

**Create or update body:**

```json
{
  "name": "Nootropic & Cognitive Products",
  "description": "Optional",
  "priority": "P2 Daily Intelligence",
  "is_active": true,
  "include_keywords": [],
  "exclude_keywords": [],
  "geography_focus": [],
  "source_preferences": [],
  "signal_priorities": []
}
```

`priority` enum: `P1 Critical` | `P2 Daily Intelligence` | `P3 Weekly Monitoring`

**List:** `{ "clusters": [ ... ] }` — frontend derives Total / Active / Signals queued from this array (no stats endpoint).

**Delete:** `{ "ok": true }`

---

## Testing

**Local (`DEBUG=true`):** all 5 work without header.

**Prod-like (`DEBUG=false`, `NORAD_ADMIN_TOKEN` set):**

```bash
# All cluster calls — header required
curl "$API/api/web-discovery/clusters" \
  -H "X-Admin-Token: $NORAD_ADMIN_TOKEN"

curl -X POST "$API/api/web-discovery/clusters" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $NORAD_ADMIN_TOKEN" \
  -d '{"name":"Test Cluster","is_active":true}'
```

| Missing / wrong token | `401` |
| Token not configured on server (`DEBUG=false`) | `503` |

Env on API: `NORAD_ADMIN_TOKEN` (or `ADMIN_TOKEN`). Frontend: `VITE_ADMIN_TOKEN` → sent as `X-Admin-Token`.

---

## Tomorrow onward

Full API contract work (v1, API keys, request IDs, etc.) starts in **Phase 1** — see [API_CONTRACT_PLAN.md](./API_CONTRACT_PLAN.md). Clusters stay on internal admin auth, not BAT v1.
