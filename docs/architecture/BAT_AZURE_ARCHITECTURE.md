# BAT Discovery Frontend — Azure Architecture (Simple)
**Prepared by:** Growth Maschine
**For:** BAT
**Scope:** Frontend application + Azure resources it directly depends on. Backend pipelines are out of scope.
**Tenant:** BYOC — runs in BAT's own Azure tenant
**Companion file:** `BAT_AZURE_ARCHITECTURE.eraser` (paste into Eraser.io → New Diagram → Cloud Architecture)

---

## 1. What's in the diagram

Eight Azure resources. That's it.

| # | Resource | Why it's there |
|---|---|---|
| 1 | **Azure Front Door** | Global edge, WAF, DDoS protection. First thing every request hits. |
| 2 | **Microsoft Entra ID** | SSO for BAT users. BAT already runs M365 — one-day integration. |
| 3 | **Azure App Service (Web App)** | Hosts the React dashboard. Lower latency than Static Web Apps, supports WebSockets / SignalR for the future chat feature, easier scaling story for a real product. |
| 4 | **Azure API Management** | The gateway. **This is where whitelisting lives.** Also handles JWT validation and rate limiting. |
| 5 | **Container Apps (BFF)** | Backend-for-Frontend. Orchestrates calls to Foundry, Cosmos, Redis, NORAD. |
| 6 | **Azure AI Foundry** | The Grader + Rubric. **First thing that touches a discovered company.** Single endpoint, single call. |
| 7 | **Cosmos DB** | Persists graded companies and user data. |
| 8 | **Azure Cache for Redis** | Sessions + read cache for the dashboard. |
| + | **Key Vault** | Holds the NORAD API key and other secrets. Accessed via Managed Identity — no secrets in app config. |

**Removed from v1:**
- ~~Azure AI Search~~ (no RAG needed)
- ~~Azure Functions~~ (frontend doesn't need scheduled jobs)
- ~~Service Bus / Event Grid~~ (no eventing in scope for the frontend)
- ~~Azure SQL Hyperscale~~ (Cosmos is enough)
- ~~Logic Apps / CRM Sync~~ (backend concern, not frontend)
- ~~Sentinel / Defender / Purview~~ (BAT will add these at the subscription level, not part of the frontend diagram)
- ~~Azure DevOps lane~~ (deployment pipeline, not architecture)

---

## 2. The triggers (left side of the diagram)

These are the things that activate the system. They are **inputs**, not cron jobs.

| Trigger | Source | Path |
|---|---|---|
| **NLP query** | BAT user typing in the dashboard | Dashboard → APIM → BFF → Foundry → Cosmos |
| **Auto-discovery** | System-driven, continuous | (drives BFF directly — exact mechanism TBD with BAT) |
| **News monitoring** | Source-driven, continuous | (drives BFF directly — exact mechanism TBD with BAT) |
| **Manual analyst action** | "Investigate this company" button | Dashboard → APIM → BFF → Foundry → Cosmos |

**Important:** the trigger list is tentative. BAT will firm this up in the upcoming meeting. The diagram leaves the triggers shown as inputs so they're easy to relabel or extend.

---

## 3. The flow

For any new VC company entering the system:

```
1. Trigger fires (NLP query / auto-discovery / news / analyst action)
2. Request reaches APIM (whitelist check + JWT validation + rate limit)
3. APIM forwards to the BFF
4. BFF pulls raw company data from NORAD's API (using key from Key Vault)
5. BFF calls Azure AI Foundry endpoint
   → Grader + Rubric run together inside Foundry as a single step
   → Returns graded + scored company
6. BFF persists result to Cosmos DB
7. BFF caches hot result in Redis
8. Dashboard reads back through BFF for display
```

---

## 4. Whitelisting — what it actually means

Whitelisting lives in **two places**, layered:

1. **Front Door WAF** — geo + bot rules at the global edge.
2. **APIM `ip-filter` policy** — IP allow-list of:
   - NORAD's egress IP range (so NORAD can reach back if needed)
   - BAT's corporate NAT range (so BAT users on the corporate network are recognized)
   - Any partner IPs BAT explicitly approves

Anyone outside the allow-list gets a 403 at the gateway. Nothing reaches the BFF, Foundry, or data tier.

---

## 5. What's deliberately not here

- **No backend pipeline.** Ingestion, eventing, search indexing, CRM sync — not in this diagram.
- **No observability stack.** App Insights / Sentinel / Defender / Purview are subscription-wide concerns BAT will configure separately.
- **No DevOps lane.** Bicep / pipelines / ACR — separate document.
- **No outreach module.** Per BAT's confirmed scope, BAT consumes opportunities; outreach lives in their existing CRM.

---

## 6. Open questions for the BAT meeting

1. **What exactly drives auto-discovery and news monitoring?** Is the BFF polling something, or are these external services pushing into Azure? The diagram works either way but the arrows will change.
2. **Where does NORAD's data physically land first?** Today the diagram shows BFF pulling from NORAD on demand. If BAT wants a continuous stream, we add a queue. Cleaner to confirm before drawing.
3. **Region.** Canada Central or East US 2? Drives Cosmos + Foundry placement.
4. **Foundry SKU.** CPU-only is fine for a classifier-style grader. GPU only needed if the rubric model is large transformer-class.
5. **Does BAT want App Insights on the frontend explicitly?** It's not in the diagram today, but they may ask.

---

*End of document. Companion DSL: `BAT_AZURE_ARCHITECTURE.eraser`.*
