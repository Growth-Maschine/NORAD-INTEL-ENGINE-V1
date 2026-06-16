# P1-01 — Core Analyst Workflow

| Field | Value |
|-------|-------|
| **Document ref** | P1-01-User |
| **Title** | Core Analyst Workflow |
| **Version** | 1.7 |
| **Last updated** | 2026-06-08 |
| **Audience** | Stakeholders, product, and analyst users |

---

## 1. Introduction

NORAD AI is the analyst application for reading market intelligence, shortlisting companies, and deciding what enters ongoing monitoring.

This document describes the analyst experience in plain language. It explains what the user sees, what they click, and what the system does in response. **Behind the scenes** blocks add a short pipeline flow and a plain-language note on which engines and AI steps run — enough context for stakeholders without implementation detail.

**Section format:**

| Block | Purpose |
|-------|---------|
| **What the user is trying to do** | The goal of this step in the analyst journey — why this screen exists |
| **UI guide** | Component, user action, **action type**, and what the user sees |
| **Behind the scenes** | Pipeline flow line + short paragraph (engines, LLM steps, what gets saved) |
| **Flow** | One-line click path |
| **Failure states** | What the user sees and what the system does when something goes wrong *(action steps only)* |
| **Diagram** | Visual map of the same flow *(end of each workflow)* |

**Action types:** `Read` · `Navigate` · `Filter` · `Escalate` · `Dismiss` · `Configure` · `—` (display only)

Workflows are ordered as the analyst experiences them, starting from the **Home page**.

---

## 2. Workflow — Home page

### 2.1 Overview

| Attribute | Value |
|-----------|-------|
| **Entry point** | Sidebar → **Home** |
| **Sub-tabs** | **Top** · **News** |
| **Top tab** | Curated weekly opportunities — Watchlist companies and Industry signals |
| **News tab** | Full article feed — browse, expand, and **+ ADD** companies for deep research |

The **Top** tab is the analyst's weekly briefing. The **News** tab is where they discover new stories and flag companies for research.

---

### 2.2 Top tab — Opportunities this week — Watchlist

The **first section** on the Top tab. Shows this week's signals for companies the analyst has already promoted to the **Watchlist** (after deep research and **Promote** in Pending review).

**What the user is trying to do:** Catch up on this week's activity for companies already on the Watchlist — without scanning the full News feed.

| Component | User action | Action type | What the user sees |
|-----------|-------------|-------------|-------------------|
| **Top** tab | Click | Navigate | Top view opens (alongside News) |
| **Opportunities this week — Watchlist** heading | Read | Read | Section title |
| **Subtitle** | Read | Read | e.g. "This week's signals and news for companies on your watchlist" |
| **Company card** | Read | Read | Company name (e.g. Pendulum Therapeutics, Ultra Pouches) |
| **Category tag** | Read | Read | Industry segment (e.g. PARTNER, FUND) |
| **Signal tag** | Read | Read | Event type (e.g. Partnership, Funding round) |
| **Bullet points** | Read | Read | Identified signals for that company this week |

**Behind the scenes:**

**Pipeline:** `Promote → Watchlist → Ongoing monitoring → Weekly signal scan → Rules/criteria filter → Watchlist section on Top tab`

After the analyst **Promotes** a company from Pending review, it enters the **Watchlist**. The system monitors those companies continuously. Each week, new activity is detected (news, filings, funding, partnerships, etc.) and evaluated against **configured rules and criteria** (signal type, relevance, recency, tier). Signals that pass appear automatically in **Opportunities this week — Watchlist** — no manual refresh needed.

Watchlist monitoring and rules engine —; Top tab layout is documented.

**Flow:**

`Sidebar → Home` → `Top tab` → `Opportunities this week — Watchlist` → `Read company signals`

**Failure states:**

| Condition | What the user sees | What the system does |
|-----------|-------------------|----------------------|
| No companies on Watchlist yet | Section empty or hidden | Nothing to show until first **Promote** |
| Monitoring inactive | Static or stale cards | Layout visible until weekly refresh runs |
| No signals matched rules this week | Empty section or "no activity" message | Company stays on Watchlist; no false positives shown |

---

### 2.3 Top tab — Opportunities this week — Industry

The **second section** below Watchlist on the Top tab. Shows sector-wide opportunity signals drawn from the **News** feed and cluster monitoring — not limited to Watchlist companies.

**What the user is trying to do:** See the week's highest-priority sector moves the system surfaced automatically — industry-wide, not limited to Watchlist companies.

| Component | User action | Action type | What the user sees |
|-----------|-------------|-------------|-------------------|
| **Opportunities this week — Industry** heading | Read | Read | Section title |
| **Subtitle** | Read | Read | e.g. "This week's sector moves from industry news, clusters, and your monitored roster" |
| **Opportunity card** | Read | Read | Company name or sector headline (e.g. Reynolds American, Health Canada draft rule) |
| **Category tag** | Read | Read | Segment (e.g. FDA, HC, IP, FUND) |
| **Signal tag** | Read | Read | Event type (e.g. FDA filing, Health Canada filing, Patent / IP) |
| **Bullet points** | Read | Read | Key opportunity signals extracted from news |

**Behind the scenes:**

**Pipeline:** `News tab articles + cluster results → AI signal extraction → Rules/criteria filter → Auto-surface on Top · Industry section`

Articles ingested from operator cluster runs and shown on the **News** tab and **Signals** page (§3) are continuously analysed. When an article or story matches **configured rules and criteria** (signal type, category, score threshold, geography, etc.), the system extracts opportunity signals and **automatically adds** them to **Opportunities this week — Industry** on the Top tab. The analyst does not manually curate this list — it is rule-driven from the news pipeline.

Rules engine and auto-surfacing —; Industry section layout is documented.

**Flow:**

`News pipeline feeds articles` → `Rules/criteria evaluate signals` → `Industry section on Top tab updates`

**How the two Top sections differ:**

| Section | Source | What appears |
|---------|--------|--------------|
| **Watchlist** | Companies the analyst **Promoted** after deep research | This week's signals for **monitored watchlist companies only** |
| **Industry** | **News** tab and cluster monitoring | Sector-wide opportunities from **all qualifying news** — watchlist or not |

**Failure states:**

| Condition | What the user sees | What the system does |
|-----------|-------------------|----------------------|
| Rules inactive | Empty or demo cards | Layout visible until rules assign cards |
| No articles matched criteria this week | Empty Industry section | No cards added — analyst uses News tab instead |
| Cluster not configured | Sparse or no industry content | No new articles to evaluate until clusters exist |

---

### 2.4 Top tab — end-to-end flow and diagram

**Flow:**

`Home → Top tab` → `Read Watchlist opportunities (your promoted companies)` → `Read Industry opportunities (auto from news rules)`

The Top tab is the weekly digest: personal watchlist signals on top, broader industry moves below.

```mermaid
flowchart TD
    START([Home · Top tab]) --> WL[Opportunities this week — Watchlist]
    WL --> WL_SRC[Source: Promoted watchlist companies]
    WL_SRC --> WL_MON[Monitoring detects weekly signals]
    WL_MON --> WL_RULES[Rules and criteria filter]
    WL_RULES --> WL_SHOW[Signals shown on Watchlist section]

    START --> IND[Opportunities this week — Industry]
    IND --> IND_SRC[Source: News tab + cluster articles]
    IND_SRC --> IND_AI[AI extracts opportunity signals]
    IND_AI --> IND_RULES[Rules and criteria filter]
    IND_RULES --> IND_SHOW[Signals auto-added to Industry section]
```

---

### 2.5 News tab — Browse Hot News

**What the user is trying to do:** Scan the highest-priority market signals and pick stories worth expanding — the first step toward flagging a company for deep research.

| Component | User action | Action type | What the user sees |
|-----------|-------------|-------------|-------------------|
| **Sidebar → Home** | Click | Navigate | Home page opens |
| **News** tab | Click (default) | Navigate | Hot News table loads |
| **News row** | Read | Read | Headline, one-line summary, category tag, signal tag, score, age (e.g. 18d) |
| **Full feed →** | Click | Navigate | Extended news list |
| **Row chevron (›)** | Click | Navigate | Row expands to full article detail |

**Behind the scenes:**

**Pipeline:** `Cluster run → Exa web search → Articles stored → Hot News list`

Operators configure clusters and queries in the admin console. Scheduled runs execute each query through **Exa**, find matching articles, enrich them, and store them for the analyst feed. Category tags, signal tags, and the headline score on each row come from enrichment applied before articles enter the feed. The analyst sees finished results.

**Flow:**

`Sidebar → Home` → `News tab` → `Scan Hot News list`

The analyst lands on Home and reads the highest-priority market signal. Category tags (e.g. MED-NIC, VAPE) show industry segment. Signal tags (e.g. FUND, FDA, LEGAL) show event type. The red score shows priority.

**Failure states:**

| Condition | What the user sees | What the system does |
|-----------|-------------------|----------------------|
| No clusters configured | Empty Hot News table | No articles until operator configures clusters and runs ingest |
| Cluster run produced zero hits | Empty table or "no stories" message | Run completed with no matches — operator adjusts cluster scope |
| Scheduled runs pending | Stale feed (older dates) | Articles update when cron ingest runs |

---

### 2.6 Expanded article

**What the user is trying to do:** Decide whether this story is strong enough to escalate a company — read the AI summary, signal score, and companies mentioned before clicking **+ ADD**.

| Component | User action | Action type | What the user sees |
|-----------|-------------|-------------|-------------------|
| **Executive summary** | Read | Read | Short analyst-style summary of the article |
| **Why it matters** | Read | Read | Strategic context for the business |
| **What to watch next** | Read | Read | Follow-up items to monitor |
| **Key facts** | Read | Read | Category label and signal type |
| **Signal score** | Read | Read | Overall score (e.g. 92/100) plus relevance, recency, magnitude, and source trust bars |
| **Related coverage** | Click VIEW | Navigate | Other articles on the same story |
| **OPEN** | Click | Navigate | Source article opens in a new browser tab |
| **Bookmark / share icons** | Click | — | Save or share the article |

**Behind the scenes:**

**Pipeline:** `Article stored → AI reads content → Summary + signal scores built → Shown on expand`

Before an article is ready to expand, an **AI analysis step** (Claude LLM) has typically read the article text and produced the executive summary, strategic context, and signal sub-scores (relevance, recency, magnitude, source trust). Expanding the row only displays work already completed — clicking does not start a new pipeline run.

**Flow:**

`News row chevron (click)` → `Read expanded article` → `Review signal score and summary`

**Failure states:**

| Condition | What the user sees | What the system does |
|-----------|-------------------|----------------------|
| AI enrichment still running | Partial expand or loading state | Summary and scores appear when pipeline completes |
| Source URL unavailable | OPEN button disabled or error | Article metadata shown without live source link |
| Low signal score | Score bars shown but low values | Analyst may skip **+ ADD** — no system block |

---

### 2.7 Companies in story

**What the user is trying to do:** Escalate a company spotted in a news signal into deep research for full profiling. This is the primary action the entire News tab exists to support — everything before this step (browsing, expanding, reading scores) is leading here.

| Component | User action | Action type | What the user sees |
|-----------|-------------|-------------|-------------------|
| **Companies in story** block | Read | Read | Companies mentioned in the article |
| **PRIMARY** badge | Read | Read | Main subject company |
| **PARTNER** badge | Read | Read | Secondary or partner company |
| **Company chevron** | Click | Navigate | Expands company description blurb |
| **+ ADD** button | Click | **Escalate** | Queues company for deep research → sends to Pending review |

**Behind the scenes:**

**Pipeline:** `+ ADD → Stage 1 (article context) → Stage 2 (Parallel + Exa + Diffbot) → Stage 3 (Claude Sonnet synthesis) → Stage 3.5 (validate) → Stage 4 (save profile) → Pending review`

Clicking **+ ADD** starts the full **Deep Research** pipeline on the NORAD backend. See **§2.7.1** for every stage and tool. Research runs in the background — the analyst can keep reading news.

**Flow:**

`Expanded article` → `Companies in story` → `+ ADD (click)`

---

**Failure states:**

| Condition | What the user sees | What the system does |
|-----------|-------------------|----------------------|
| Company already in Pending review | Toast: "Already queued" or button disabled | No duplicate run started |
| Stage 2 — one engine fails (Parallel, Exa, or Diffbot) | No visible change — research continues | Run proceeds with remaining engines |
| Stage 2 — all three engines fail | Pending review row shows failed state | Run stops; no profile saved; analyst can retry |
| Stage 3 — AI synthesis fails (unrecoverable) | Pending review row shows failed state | Run stops; no profile saved |
| Article has no companies detected | Companies in story block absent or empty | No + ADD button shown |

---

### 2.7.1 Deep Research pipeline — complete tools

Triggered by **+ ADD**. Produces one company profile per run.

| Stage | Tool / engine | What it does |
|-------|---------------|--------------|
| **1 — Build input** | Application | Binds company name, domain hint, and the news article context that triggered **+ ADD** |
| **2 — Fan-out** | **Parallel** | Deep web research task — returns a structured brief (identity, funding, signals, sources) |
| **2 — Fan-out** | **Exa** | Two deep web searches, then reads the top article pages for full text |
| **2 — Fan-out** | **Diffbot** | Knowledge-graph entity lookup — company record, description, and linked data |
| **3 — Synthesize** | **Claude Sonnet 4.5** (LLM) | Merges Parallel + Exa + Diffbot evidence into one company profile and signal list |
| **3 — Synthesize (retry)** | **Claude Sonnet 4.5** (LLM) | If the first pass returns too few signals or sources, one automatic retry |
| **3.5 — Validate** | Application | Cleans confidence labels and source rules before the profile is saved |
| **4 — Persist** | Application | Saves company, profile card, signals, and source citations to the database |

**Stage 2 behaviour:** Parallel and Exa start together. Diffbot runs with a domain hint (from the article or derived from Exa URLs). If one engine in Stage 2 fails, the run continues with the others. If all three fail, the run stops with no profile saved.

**Pipeline flow:**

`+ ADD` → `Stage 1 · article context` → `Stage 2 · Parallel + Exa + Diffbot` → `Stage 3 · Claude Sonnet synthesis` → `Stage 3.5 · validate` → `Stage 4 · save` → `Pending review`

```mermaid
flowchart TD
    ADD([+ ADD clicked]) --> S1[Stage 1 · Build input from news article]
    S1 --> S2[Stage 2 · Fan-out]
    S2 --> P[Parallel · structured research brief]
    S2 --> E[Exa · deep search + article text]
    S2 --> D[Diffbot · entity record]
    P --> S3[Stage 3 · Claude Sonnet 4.5 synthesis]
    E --> S3
    D --> S3
    S3 --> RETRY{Thin profile?}
    RETRY -->|Yes| S3R[Claude Sonnet retry once]
    RETRY -->|No| S35[Stage 3.5 · Validate profile]
    S3R --> S35
    S35 --> S4[Stage 4 · Save company / card / signals / sources]
    S4 --> PENDING[Pending review]
```

---

### 2.8 End-to-end flow — News tab

**Flow:**

`Sidebar → Home` → `News tab` → `Expand article` → `Read summary and score` → `+ ADD on company`

This is the analyst's daily starting point: scan signal, understand context, and flag a company for deeper profiling.

---

### 2.9 Diagram — News tab

```mermaid
flowchart TD
    START([Analyst opens Home]) --> NEWS[News tab]
    NEWS --> SCAN[Browse Hot News list]
    SCAN --> EXPAND[Expand article row]
    EXPAND --> READ[Read summary and signal score]
    READ --> COMPANIES[Companies in story]
    COMPANIES --> ADD[+ ADD on company]
    ADD --> S1[Stage 1 · article context]
    S1 --> S2[Stage 2 · Parallel + Exa + Diffbot]
    S2 --> S3[Stage 3 · Claude Sonnet synthesis]
    S3 --> S4[Stage 4 · save profile]
    S4 --> PENDING[Pending review]
```

---

## 3. Workflow — Signals page

The **Signals** page shows the **same incoming news** that feeds Home → **News** tab. The difference is presentation: here every story is **categorized and filtered** by configured **rules and criteria** — signal type, category, score, and other rules decide which tab each story appears under.

### 3.1 Overview

| Attribute | Value |
|-----------|-------|
| **Entry** | Sidebar → **Signals** |
| **Purpose** | Browse all ingested news as categorized signals — filter by type without re-reading the full News feed |
| **Data source** | Same cluster → search → article pipeline as Home News (§2.5) |
| **Header** | e.g. "Signals — 11 stories in feed · updated 4m ago" |

**How the three news views relate:**

| View | What it is | Analyst use |
|------|------------|-------------|
| **Home → News** | Full article feed — expandable rows, **+ ADD** | Discover stories and flag companies for deep research |
| **Signals** | Same articles, **categorized by rules** into filter tabs | Scan all signals by type (Regulatory, Filings, Funding, etc.) |
| **Home → Top** | Weekly digest — Watchlist + Industry subsets | Read this week's highest-priority opportunities only |

---

### 3.2 Category filter tabs

**What the user is trying to do:** Triage the full news feed by signal type — find all regulatory, funding, or filing stories without re-reading every row on Home News.

| Component | User action | Action type | What the user sees |
|-----------|-------------|-------------|-------------------|
| **All** tab | Click | Filter | Every signal in the feed (e.g. 11 stories) |
| **Companies** tab | Click | Filter | Company-focused signals only (e.g. 7) |
| **Industry** tab | Click | Filter | Sector-wide signals (e.g. 2 — grey-market vapes, sentiment trends) |
| **Regulatory** tab | Click | Filter | Regulatory signals (e.g. 3) |
| **Filings** tab | Click | Filter | Filing signals — FDA, Health Canada, etc. (e.g. 2) |
| **Hiring** tab | Click | Filter | Hiring signals (e.g. 0 when none match) |
| **Funding** tab | Click | Filter | Funding-round signals (e.g. 3) |
| **Tab count badge** | Read | Read | Number of stories matching that category's rules |
| **Header subtitle** | Read | Read | Updates per tab — e.g. "2 in industry · updated 4m ago" |

**Behind the scenes:**

**Pipeline:** `Incoming article → AI enrichment (category + signal type + score) → Rules/criteria assign tab → Signals page filter`

When articles enter the system from cluster ingest (§7), each one is enriched with a **category tag** (e.g. MED-NIC, VAPE, CESS), a **signal tag** (e.g. FUND, FDA, GREY, SENT), and a **score**. Configured **rules and criteria** map each story to one or more filter tabs. Clicking a tab applies that category filter — the analyst is not manually sorting; the rules engine has already classified each item.

**Flow:**

`Sidebar → Signals` → `Select category tab (All / Companies / Industry / …)`

**Failure states:**

| Condition | What the user sees | What the system does |
|-----------|-------------------|----------------------|
| Tab has zero matches | Tab shows count `0`; empty table | No rows for that category — analyst switches tab |
| Rules engine not live | All tabs show same unfiltered list | Categorization counts may not reflect rules yet |
| Feed stale | "updated Xm ago" shows old timestamp | No new cluster runs since last ingestion |

---

### 3.3 News feed table

| Component | User action | What the user sees |
|-----------|-------------|-------------------|
| **News feed** heading | Read | Table label |
| **Title column** | Read | Headline + one-line summary snippet |
| **Category column** | Read | Category tag (e.g. MED-NIC, VAPE, NIC-ALT, CESS) |
| **Signal column** | Read | Signal type tag (e.g. FUND, FDA, GREY, SENT, IP) |
| **Score column** | Read | Priority score (e.g. 92, 67) — higher = more relevant per rules |
| **Date column** | Read | Age of signal (e.g. 18d, 20d) |

**Behind the scenes:**

**Pipeline:** `Same articles as Home News → Pre-scored and tagged → Displayed in Signals table`

Each row is one article from the shared news pipeline. The score and tags were assigned during ingestion — the same values the analyst sees when expanding an article on Home News. Signals presents them in a scannable table for triage by type, not for deep-read or **+ ADD** (that stays on Home News).

**Flow:**

`Signals page` → `Scan News feed table` → `Switch tab to narrow by category`

---

### 3.4 Priority watch sidebar

| Component | User action | What the user sees |
|-----------|-------------|-------------------|
| **Top signal** card | Read | Highest-priority signal this period (e.g. Ultra Pouches — FUND) |
| **Priority watch** heading | Read | Watchlist companies with active signals |
| **Watchlist company card** | Read | Company name, tags, bullet-point signals (e.g. Pendulum Therapeutics, Stay Wyld Organics) |

**Behind the scenes:**

**Pipeline:** `Promoted watchlist companies → Monitoring detects signals → Rules filter → Priority watch sidebar`

The right sidebar surfaces **Watchlist** companies (promoted after deep research) that have matching signals in the current feed. This is the same watchlist logic as **Opportunities this week — Watchlist** on Home Top (§2.2), shown in context while the analyst browses the full categorized feed.

**Flow:**

`Signals page` → `Priority watch sidebar` → `Read watchlist company signals`

---

### 3.5 End-to-end flow and diagram

**Flow:**

`Clusters ingest news` → `Rules categorize into tabs` → `Signals page` → `Filter by category` → `Read feed + Priority watch`

The Signals page is the **master categorized view** of all incoming news. Home News is for discovery and **+ ADD**. Home Top is the weekly digest. All three draw from the same pipeline.

```mermaid
flowchart TD
    CLUSTERS[Operator cluster runs] --> EXA[Exa web search]
    EXA --> STORE[Articles stored + AI enriched]
    STORE --> RULES[Rules and criteria classify]

    RULES --> NEWS[Home · News tab — full feed + expand + ADD]
    RULES --> SIGNALS[Signals page — categorized tabs]
    RULES --> TOP_IND[Home · Top · Industry digest]
    RULES --> TOP_WL[Home · Top · Watchlist digest]

    SIGNALS --> TABS[Filter: All / Companies / Industry / Regulatory / Filings / Hiring / Funding]
    TABS --> TABLE[News feed table]
    STORE --> PW[Priority watch sidebar]
    PW --> WL_COMP[Watchlist companies]
```

---

## 4. Workflow — Pending review

After **+ ADD**, the company appears in **Pending review**. The sidebar badge shows how many items are waiting (e.g. 2).

### 4.1 Overview

| Attribute | Value |
|-----------|-------|
| **Entry** | Sidebar → **Pending review** |
| **Purpose** | Analyst approves or rejects companies that completed deep research |
| **Subtitle** | e.g. "2 candidates awaiting approval" |

---

### 4.2 Review queue

**What the user is trying to do:** See every company waiting for a go / no-go decision after deep research — and open the one to review first.

| Component | User action | Action type | What the user sees |
|-----------|-------------|-------------|-------------------|
| **Pending review** (sidebar) | Click | Navigate | Review table opens |
| **All / Bookmarked / Manual** tabs | Click | Filter | Filter list by how the company arrived |
| **Table row** | Read | Read | Origin, company name, URL, context, time added |
| **Row chevron** | Click | Navigate | Expands detail for that company |

**Behind the scenes:**

**Pipeline:** `+ ADD → Stages 1–4 (see §2.7.1) → Row appears in Pending review`

Each row is tied to a Deep Research run. While **Stage 2** (Parallel, Exa, Diffbot) or **Stage 3** (Claude Sonnet synthesis) is still running, the row may show a waiting state. When **Stage 4** completes, the saved profile is ready for review. Tools involved: **Parallel**, **Exa**, **Diffbot**, **Claude Sonnet 4.5**. The context column records the originating news signal (e.g. "Series B funding signal — NGP").

**Flow:**

`Sidebar → Pending review` → `Review table`

**Failure states:**

| Condition | What the user sees | What the system does |
|-----------|-------------------|----------------------|
| Research still running | Row visible; expand shows "research in progress" | Analyst waits — profile fills when Stage 4 completes |
| Research failed | Row shows failed state | No profile saved — analyst can retry via **+ ADD** or manual queue |
| Empty queue | "0 candidates" subtitle; badge hidden | Nothing to review |

---

### 4.3 Expanded company card

**What the user is trying to do:** Read the deep research summary and decide whether to **Promote** this company to the Watchlist or **Dismiss** it.

| Component | User action | Action type | What the user sees |
|-----------|-------------|-------------|-------------------|
| **Company name and URL** | Read | Read | Company identity |
| **Source context** | Read | Read | Which news signal triggered this entry |
| **Deep research summary** | Read | Read | Profile summary once research completes |
| **No profile yet** | Read (if in progress) | Read | Message that research is still running |
| **On Promote** checklist | Read | Read | Four steps that happen if the analyst promotes |

**Behind the scenes:**

**Pipeline:** `Stage 1 (article context) → Stage 2 (Parallel + Exa + Diffbot) → Stage 3 (Claude Sonnet synthesis) → Stage 3.5 (validate) → Stage 4 (save) → Summary shown here`

The summary on this card is the finished output of the full Deep Research pipeline (§2.7.1):

| Stage | Tool | Role in what the analyst reads |
|-------|------|-------------------------------|
| 1 | Application | Links profile back to the news signal that triggered **+ ADD** |
| 2 | **Parallel** | Structured brief — identity, funding, early signals |
| 2 | **Exa** | Web search hits and article text used as evidence |
| 2 | **Diffbot** | Entity record — description, linked company data |
| 3 | **Claude Sonnet 4.5** | Writes the deep research summary, signals, and strategic fit narrative |
| 3.5 | Application | Validates confidence and sources before save |
| 4 | Application | Saves profile — what you see once research completes |

While Stages 2–3 are running, the card shows that research is still in progress. The **On Promote** checklist describes downstream steps if the analyst accepts the company.

**Flow:**

`Pending review` → `Expand row` → `Read deep research summary`

**Failure states:**

| Condition | What the user sees | What the system does |
|-----------|-------------------|----------------------|
| Summary not ready | "No profile yet" message on card | Promote/Dismiss disabled or hidden until research completes |
| Thin profile (few signals) | Short summary with low data completeness | Card still shown — analyst judges fit manually |

---

### 4.4 Promote to Watchlist

**What the user is trying to do:** Accept this company for ongoing monitoring — move it from Pending review onto the Watchlist.

| Component | User action | Action type | Outcome |
|-----------|-------------|-------------|---------|
| **Promote** / **Promote to Watchlist** | Click | **Escalate** | Company accepted for monitoring |

**Behind the scenes:**

**Pipeline:** `Promote → Watchlist record created → Baseline screener runs → Fit score + tier filled → Monitoring`

Accepting the company writes it to the **Watchlist** and triggers a **baseline screener** — a lighter pipeline pass that scores strategic fit, assigns a tier, and fills profile fields for ongoing use. The company appears on the **Companies** page (§5). Once monitoring is live, new signals auto-append to the company detail page (§5.8) and weekly highlights surface on Home Top (§2.2).

**Flow:**

`Expanded card` → `Promote to Watchlist (click)` → `Company enters Watchlist`

**Failure states:**

| Condition | What the user sees | What the system does |
|-----------|-------------------|----------------------|
| Research not complete | Promote button disabled | Cannot promote until profile saved |
| Already on Watchlist | Toast or button disabled | No duplicate watchlist entry |
| Baseline screener fails | Company on Watchlist; fit fields empty | Watchlist entry kept; screener retry |

---

### 4.5 Dismiss

**What the user is trying to do:** Reject this company — remove it from the review queue and discard the research card.

| Component | User action | Action type | Outcome |
|-----------|-------------|-------------|---------|
| **Dismiss** (X button) | Click | **Dismiss** | Company removed from Pending review |

**Behind the scenes:**

**Pipeline:** `Dismiss → Pending record removed → Research card discarded (no new pipeline run)`

This is a state change only — no engines or LLM steps run. The company is removed from the pending queue and the research card built for this review is discarded. The analyst is indicating the company is not relevant for monitoring.

**Flow:**

`Expanded card` → `Dismiss (click)` → `Company removed from queue`

**Failure states:**

| Condition | What the user sees | What the system does |
|-----------|-------------------|----------------------|
| Research still running | Dismiss may still be available | Queue entry removed; in-flight run may finish but card discarded |
| Already dismissed | Row no longer visible | Idempotent — no duplicate action |

---

### 4.6 End-to-end flow — Pending review

**Flow:**

`Sidebar → Pending review` → `Expand company` → `Read research summary` → `Promote` or `Dismiss`

The analyst makes a go / no-go decision. Promote sends the company to the Watchlist. Dismiss clears it from the queue.

---

### 4.7 Diagram — Pending review

```mermaid
flowchart TD
    START([Pending review page]) --> LIST[Review queue]
    LIST --> EXPAND[Expand company row]
    EXPAND --> SUMMARY[Read deep research summary]
    SUMMARY --> DECIDE{Analyst decision}
    DECIDE -->|Promote| PROMOTE[Add to Watchlist]
    PROMOTE --> SCREENER[Baseline screener runs]
    SCREENER --> WATCH[Ongoing monitoring]
    DECIDE -->|Dismiss| DISMISS[Remove from queue]
    DISMISS --> END([Done])
```

---

## 5. Workflow — Companies page

The **Companies** page lists every company with a saved profile. Clicking any row opens the **company detailed profile** — the full deep research card plus ongoing updates for watchlist companies.

### 5.1 Overview

| Attribute | Value |
|-----------|-------|
| **Entry** | Sidebar → **Companies** |
| **Header** | e.g. "10 companies — 4 on watchlist" |
| **Purpose** | Browse all saved companies; open full profiles; manually bookmark new ones |
| **Two tabs** | **Watchlist** (promoted subset) · **Companies** (all saved) |

| Tab | What it contains |
|-----|------------------|
| **Watchlist** | Companies the analyst **Promoted** from Pending review — actively monitored |
| **Companies** | **Every saved profile** — watchlist companies plus any researched or manually queued company not yet promoted |

---

### 5.2 Company list

**What the user is trying to do:** Find a saved company and open its full profile — or start the manual bookmark path via **+ Add company**.

| Component | User action | Action type | What the user sees |
|-----------|-------------|-------------|-------------------|
| **Watchlist** tab | Click | Filter | Promoted companies only (e.g. 4) |
| **Companies** tab | Click | Filter | All saved companies (e.g. 10) |
| **Search companies…** | Type | Filter | Filters the table |
| **Table row** | Click | Navigate | Opens company detailed profile |
| **Company column** | Read | Read | Name + website URL |
| **Industry column** | Read | Read | Sector (e.g. Wellness, Biotechnology) |
| **Location column** | Read | Read | City and country |
| **Last Updated column** | Read | Read | When profile or signals last changed |
| **Actions (⋯)** | Click | — | Row actions menu |
| **+ Add company** | Click | Navigate | Opens bookmark modal |

**Behind the scenes:**

**Pipeline:** `Deep research completes → Company saved → Appears on Companies tab` · `Promote → Also tagged watchlist → Appears on Watchlist tab`

Every company that finishes deep research (from News **+ ADD** or manual **Find & queue**) is saved and listed on the **Companies** tab. Only **Promoted** companies also appear on the **Watchlist** tab and enter active monitoring.

**Flow:**

`Sidebar → Companies` → `Watchlist or Companies tab` → `Click company row`

---

### 5.3 Add company manually

**What the user is trying to do:** Escalate a company discovered outside the News feed into deep research — same end goal as **+ ADD**, but without a triggering article.

| Component | User action | Action type | What the user sets |
|-----------|-------------|-------------|-------------------|
| **+ Add company** | Click | Navigate | "Bookmark a company" modal opens |
| **Company name** (optional) | Type | Configure | e.g. Lumina Nicotine |
| **Website** (optional) | Type | Configure | URL or domain — at least one field required |
| **Find & queue** | Click | **Escalate** | Company queued for review |
| **Cancel** | Click | — | Modal closes |

**Behind the scenes:**

**Pipeline:** `Find & queue → Pending review (Manual) → Deep Research pipeline (§2.7.1) → Company saved → Companies tab`

Manual bookmark skips the News **+ ADD** path but follows the same research pipeline. The company enters **Pending review** under the **Manual** tab. After research completes, the analyst **Promotes** or **Dismisses** as usual. On save, the profile appears on the **Companies** tab.

**Flow:**

`Companies` → `+ Add company` → `Enter name or URL` → `Find & queue` → `Pending review → Promote or Dismiss`

**Failure states:**

| Condition | What the user sees | What the system does |
|-----------|-------------------|----------------------|
| Both fields empty | Find & queue disabled | Cannot submit without name or URL |
| Company already queued | Toast: "Already queued" | No duplicate run started |
| Invalid URL format | Inline validation error | Submit blocked until URL corrected |
| Deep research fails | Pending review row shows failed state | Same failure handling as §2.7 |

---

### 5.4 Company detailed profile — header and tabs

**What the user is trying to do:** Read the full deep research card and ongoing signals for one company — the single source of truth after Promote.

| Component | User action | Action type | What the user sees |
|-----------|-------------|-------------|-------------------|
| **Breadcrumb** | Read | Read | e.g. Companies › Ultra Pouches |
| **Company logo + name** | Read | Read | Identity |
| **Fit badge** | Read | Read | e.g. HIGH FIT |
| **Overview** tab | Click | Navigate | Key facts, description, signal timeline, market snapshot |
| **Signals** tab | Click | Navigate | Live intent signal, score trend, signal feed |
| **People** tab | Click | Navigate | Decision makers, decision map |
| **Financials** tab | Click | Navigate | Revenue, headcount, deal sizing |
| **Timeline** tab | Click | Navigate | Chronological company events |
| **Analysis** tab | Click | Navigate | Deep research analysis sections |
| **Outreach** tab | Click | Navigate | Outreach tools (when available) |

**Behind the scenes:**

**Pipeline:** `Deep Research Stage 4 save → Company card loaded → Profile tabs populated`

The detailed profile is built from the **Deep Research** pipeline output (§2.7.1) — Parallel, Exa, Diffbot evidence synthesised by **Claude Sonnet** into a structured company card. Key facts, signals, people, and financials all come from that initial research run.

**Flow:**

`Companies list` → `Click row` → `Company detailed profile`

**Failure states:**

| Condition | What the user sees | What the system does |
|-----------|-------------------|----------------------|
| Profile not yet saved | Redirect or empty profile | Company only appears after deep research completes |
| Non-watchlist company | Profile static since last research | No auto-append until **Promote** (§5.8) |
| Partial card data | Sections show "not available" | Fields without evidence left empty — not guessed |

---

### 5.5 Overview tab

| Component | User action | What the user sees |
|-----------|-------------|-------------------|
| **Key facts grid** | Read | Founded, CEO, employees, sector, location, website |
| **Company description** | Read / expand | Deep research narrative — View More |
| **Revenue / ACV bar** | Read | Estimated financials |
| **Lead score** | Read | e.g. 78 — STRONG MATCH |
| **Signal Analysis** | Read | Timeline of signals with dates and source counts |
| **Latest Developments** | Read | Recent milestones |
| **Strategic Considerations** | Read | Analyst-style strategic notes |
| **Market Snapshot** | Read | Moat, competitors, intent signal, data completeness |
| **Similar Companies** | Read | Comparable companies with scores |

**Behind the scenes:**

**Pipeline:** `Deep Research synthesis → Company card fields → Overview tab display`

Overview shows the core output of **Claude Sonnet** synthesis — identity, funding, strategic fit, moat, and the initial signal set from Stage 2 engines. For **watchlist** companies, new entries also append here daily via monitoring (§5.8).

**Flow:**

`Company profile` → `Overview tab` → `Read key facts and signal timeline`

---

### 5.6 Signals tab

| Component | User action | What the user sees |
|-----------|-------------|-------------------|
| **Intent Signal** card | Read | Live status — e.g. Strongly Surging |
| **Score Trend** | Read | 12-week trend chart (e.g. +36pts) |
| **Signal feed** | Read | Dated signals — type (STRATEGIC, GROWTH), confidence (confirmed/estimated), tier, sources |

**Behind the scenes:**

**Pipeline:** `Initial deep research signals` + `Watchlist monitoring → new signals daily → Signals tab feed`

The Signals tab lists every identified signal for this company. Initial signals come from deep research. For **watchlist** companies only, monitoring detects new news and activity daily and **auto-appends** new signal rows here.

**Flow:**

`Company profile` → `Signals tab` → `Read intent + signal feed`

---

### 5.7 People and Financials tabs

| Tab | What the user sees |
|-----|-------------------|
| **People** | Decision makers table (name, function, role), filters (Champions, Influencers, Buyers, Technical), Decision Map |
| **Financials** | Reported revenue, estimated ACV, headcount, 5-year trajectory, deal sizing tiers |
| **Timeline** | Chronological event history |
| **Analysis** | Extended deep research analysis |
| **Outreach** | Contact and outreach actions (when available) |

**Behind the scenes:**

**Pipeline:** `Deep Research synthesis → Structured card sections → Tab content`

People, financials, and timeline fields are extracted during **Claude Sonnet** synthesis from Parallel, Exa, and Diffbot evidence. Fields without source data show as unavailable rather than guessed.

---

### 5.8 Watchlist monitoring — auto-append on detail page

**Only watchlist companies** receive ongoing updates. Companies on the **Companies** tab that were never promoted do **not** auto-append.

| What updates | Where it appears |
|--------------|------------------|
| New news or articles about the company | Signal Analysis timeline (Overview), Signals feed |
| New funding, product, hiring, regulatory events | Latest Developments, Signals tab |
| Score / intent changes | Lead score, Intent Signal card, Score Trend |

**Behind the scenes:**

**Pipeline:** `Watchlist company → Daily monitoring scan → New signal detected → Rules filter → Auto-append to company detail page`

Each day the system scans for new activity related to **watchlist** companies. When a new article or signal is found and passes rules, it is **automatically appended** to that company's detail page — Overview timeline, Signals feed, and Last Updated on the Companies list. The analyst does not manually refresh or re-run research.

Watchlist daily monitoring appends new signals to the company profile. Profile layout and deep research content come from the research pipeline.

**Flow:**

`Promoted to Watchlist` → `Daily monitoring` → `New signal found` → `Auto-appended on company detail page`

---

### 5.9 End-to-end flow and diagram

**Flow:**

`Companies list (Watchlist or Companies tab)` → `Click company` → `Read profile tabs` → `Watchlist: new signals auto-append daily`

```mermaid
flowchart TD
    LIST([Companies page]) --> TABS{Which tab?}
    TABS -->|Watchlist| WL[Promoted companies — monitored]
    TABS -->|Companies| ALL[All saved profiles]

    WL --> CLICK[Click company row]
    ALL --> CLICK
    CLICK --> PROFILE[Company detailed profile]

    PROFILE --> DR[Deep research card — Overview / Signals / People / Financials]
    WL --> MON[Daily watchlist monitoring]
    MON --> NEW[New signal detected]
    NEW --> APPEND[Auto-append to profile timeline + Signals tab]
```

---

## 6. Complete analyst journey

**Discovery path:**

`Home → News tab` → `Expand article` → `+ ADD` → `Deep research` → `Pending review` → `Promote` or `Dismiss`

**Manual add path:**

`Companies → + Add company` → `Find & queue` → `Pending review` → `Deep research` → `Promote or Dismiss`

**After Promote:**

`Companies · Watchlist tab` → `Company detail profile` → `Daily monitoring auto-appends new signals`

`Weekly signals` → `Home Top · Opportunities this week — Watchlist`

**Industry digest (automatic):**

`News pipeline` → `Rules/criteria` → `Top tab · Opportunities this week — Industry`

The analyst discovers companies via News or manual bookmark, approves them in Pending review, and promoted companies appear on Companies Watchlist with a living profile that grows as monitoring detects new activity.

```mermaid
flowchart LR
    A[Home News] --> B[Expand article]
    B --> C[+ ADD]
    C --> S2[Parallel + Exa + Diffbot]
    S2 --> S3[Claude Sonnet synthesis]
    S3 --> S4[Save profile]
    S4 --> E[Pending review]
    E --> F{Promote or Dismiss}
    F -->|Promote| G[Watchlist]
    G --> COMP[Companies detail profile]
    COMP --> MON[Daily signal auto-append]
    F -->|Dismiss| H[Removed]
```

---

## 7. How news enters the feed (supporting workflow)

This section explains where Hot News content comes from. Clusters and queries are configured in the **admin console** — analysts read the resulting feed on Home → News.

### 7.1 Overview

| Attribute | Value |
|-----------|-------|
| **Configured by** | Operator — admin console `/discover-web` |
| **Consumed by** | Analyst — Home **News** tab and **Signals** page |
| **Purpose** | Themed Exa searches that ingest articles into the intelligence feed |
| **Schedule** | Cron ingest |

---

### 7.2 Operator cluster setup (reference)

**What happens:** The operator defines monitoring scope — keywords, geography, sources, signal priorities — and adds Exa search queries per cluster. Running a cluster (or scheduled cron) executes queries, collects hits, and (when wired) enriches them before they appear as **Articles** on the analyst feed.

**Pipeline:** `Operator configures cluster → Adds queries → Run or cron → Exa search per query → Articles enriched → Home News feed`

Analyst workflow for this path: read Home → News. Cluster CRUD lives in [P1-01-Admin](./P1-01-admin.md) and [P1-02-Admin](./P1-02-admin.md).

**Failure states (analyst-visible):**

| Condition | What the user sees | What the system does |
|-----------|-------------------|----------------------|
| No clusters configured | Empty Hot News table | Operator must configure clusters and run ingest |
| Cluster run produced zero hits | Empty table | Operator adjusts cluster scope |
| Scheduled ingest | Stale feed | Articles update when cron ingest runs |

---

### 7.3 Scheduled cluster runs

| Capability |
| ------------ |
| Operator sets run schedule (cron) |
| Articles auto-append to Home News |
| Post-run LLM enrichment on ingest |

---

### 7.4 Diagram — Cluster to News

```mermaid
flowchart TD
    ADMIN([Admin console — Clusters]) --> CREATE[Create or edit cluster]
    CREATE --> QUERIES[Add search queries]
    QUERIES --> SCHEDULE[Schedule runs]
    SCHEDULE --> RUN[Cluster search executes]
    RUN --> NEWS[Articles on analyst Home News]
```

---

## 8. Capability status

| Capability | User experience today |
|------------|----------------------|
| Home Top tab layout (Watchlist + Industry sections) |
| Watchlist weekly signals (rules-driven) |
| Industry auto-surface from news (rules-driven) |
| Home News tab layout |
| Expand article and signal scores |
| + ADD → deep research |
| Pending review queue |
| Research summary on expand |
| Promote to Watchlist | UI ready; links to §2.2 when monitoring live |
| Dismiss from pending |
| Cluster create and manage |
| Scheduled cluster runs → News feed |
| Signals page — categorized tabs + feed table |
| Signals — rules/criteria auto-categorization |
| Companies page — list tabs + detail profile |
| + Add company → Pending review (Manual) |
| Watchlist daily monitoring → auto-append on detail |
