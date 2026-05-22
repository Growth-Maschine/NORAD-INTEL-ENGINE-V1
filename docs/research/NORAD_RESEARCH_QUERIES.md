# NORAD — Optimal Deep Research Queries (Parallel AI + Exa Deep)
*Trend Hunter seed: Nic and Jet Fuel + Ultra. UI-pasteable. v2.*

---

## What each tool's UI actually supports (corrected)

**Parallel AI UI** — one text box, Ultra processor toggle, that's it. No schema field. No separate system prompt. Everything goes in the one prompt.

**Exa Playground UI** — two real slots:
1. **Search query** (keyword-style query, separate field at top)
2. **Structured outputs → System Prompt** (ONE slot with a **Text / Object** toggle):
   - **Text mode** = natural-language synthesis instruction
   - **Object mode** = JSON schema for strict structured output
   - You pick one, not both.

Plus toggles: Result category, Highlights, Number of results.

**Recommended setup for our comparison:**
- **Parallel AI** → single prompt with JSON template embedded inside (because no schema field exists).
- **Exa** → Search query carries disambiguation. Set System Prompt to **Object** mode, paste the JSON schema from §0.

That gives us comparable JSON output on both sides without manual cleanup.

---

## The fields we want back (reference structure)

Use this as the shape both tools should return. For Exa, paste as JSON schema (see §0 below). For Parallel, the prompt asks for these fields in JSON inside the prompt itself.

**Fields:**
`company_name`, `tagline`, `website`, `founded_year`, `headquarters`, `founders[]`, `leadership[]`, `funding_total_usd`, `funding_rounds[]` (round / amount / date / investors / source_url), `product_line[]`, `key_ingredients_or_tech[]`, `target_audience`, `distribution_channels[]`, `retailers[]`, `price_points_usd[]`, `social_handles{}`, `recent_news_12mo[]` (date / headline / source / url), `competitors[]`, `competitive_positioning`, `regulatory_notes`, `sources[]`.

---

## §0. Exa output setup — TWO OPTIONS, PICK ONE

> ⚠️ Exa Object mode has hard limits: **max 10 top-level properties AND max nesting depth of 2**. That kills any rich nested schema. You have two choices:
>
> - **Option A (Object mode, strict)** — use the flattened schema in §0a below. Strict JSON, fits the limits, but funding rounds and news become formatted text strings instead of structured objects.
> - **Option B (Text mode, flexible — RECOMMENDED for client demo)** — use the natural-language prompt in §0b. No schema limits. Exa returns the same rich nested JSON Parallel returns. Less strict on field names but richer data.
>
> **For comparing Parallel vs Exa side-by-side: pick Option B.** It matches Parallel's output shape directly.

### §0a. Flattened schema (Object mode — fits Exa's 10-prop / depth-2 limits)

Paste this in System Prompt → Object mode.

```json
{
  "type": "object",
  "properties": {
    "company_name":              { "type": "string" },
    "website":                   { "type": "string" },
    "founders_and_leadership":   { "type": "array", "items": { "type": "string" } },
    "funding_history":           { "type": "array", "items": { "type": "string" } },
    "products_and_ingredients":  { "type": "array", "items": { "type": "string" } },
    "distribution_and_retailers":{ "type": "array", "items": { "type": "string" } },
    "competitors":               { "type": "array", "items": { "type": "string" } },
    "regulatory_notes":          { "type": "string" },
    "recent_news_12mo":          { "type": "array", "items": { "type": "string" } },
    "sources":                   { "type": "array", "items": { "type": "string" } }
  }
}
```

**Formatting convention for the array-of-string fields** (put this in your search query so Exa knows how to fill them):
- `founders_and_leadership`: `"Name — Role — Background"`
- `funding_history`: `"Round — $Amount — Date — Investors — SourceURL"`
- `products_and_ingredients`: `"SKU name | strength/size | key ingredients with dosages"`
- `distribution_and_retailers`: `"Channel — specific retailer/platform"`
- `recent_news_12mo`: `"YYYY-MM-DD — Headline — Source — URL"`

### §0b. Text-mode synthesis prompt (RECOMMENDED — paste in System Prompt → Text mode)

Use this **instead** of the schema if you want richer nested output that matches Parallel AI's shape.

```
You are producing a structured brand intelligence profile. Synthesize findings from the search results into a single JSON object with EXACTLY this nested structure (do not flatten, do not rename keys, do not add keys). If a field is not publicly available, use null or an empty array — DO NOT GUESS.

{
  "identity": {
    "company_name": "",
    "tagline": "",
    "website": "",
    "founded_year": null,
    "headquarters": ""
  },
  "people": {
    "founders": [],
    "leadership": []
  },
  "funding": {
    "total_usd": null,
    "rounds": [
      { "round": "", "amount_usd": null, "date": "", "investors": [], "source_url": "" }
    ]
  },
  "product": {
    "product_line": [],
    "key_ingredients_or_tech": [],
    "price_points_usd": []
  },
  "distribution": {
    "channels": [],
    "retailers": []
  },
  "audience_and_positioning": {
    "target_audience": "",
    "competitors": [],
    "competitive_positioning": ""
  },
  "social_handles": { "instagram": "", "tiktok": "", "linkedin": "", "twitter": "" },
  "recent_news_12mo": [
    { "date": "", "headline": "", "source": "", "url": "" }
  ],
  "regulatory_notes": "",
  "sources": []
}

For every populated field, append the source URL to the `sources` array. Return ONLY the JSON object, no prose, no markdown fences.
```

```json
{
  "type": "object",
  "properties": {
    "identity": {
      "type": "object",
      "properties": {
        "company_name":  { "type": "string" },
        "tagline":       { "type": "string" },
        "website":       { "type": "string" },
        "founded_year":  { "type": ["integer", "null"] },
        "headquarters":  { "type": ["string", "null"] }
      }
    },
    "people": {
      "type": "object",
      "properties": {
        "founders":   { "type": "array", "items": { "type": "string" } },
        "leadership": { "type": "array", "items": { "type": "string" } }
      }
    },
    "funding": {
      "type": "object",
      "properties": {
        "total_usd": { "type": ["number", "null"] },
        "rounds": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "round":      { "type": "string" },
              "amount_usd": { "type": ["number", "null"] },
              "date":       { "type": "string" },
              "investors":  { "type": "array", "items": { "type": "string" } },
              "source_url": { "type": "string" }
            }
          }
        }
      }
    },
    "product": {
      "type": "object",
      "properties": {
        "product_line":            { "type": "array", "items": { "type": "string" } },
        "key_ingredients_or_tech": { "type": "array", "items": { "type": "string" } },
        "price_points_usd":        { "type": "array", "items": { "type": "string" } }
      }
    },
    "distribution": {
      "type": "object",
      "properties": {
        "channels":  { "type": "array", "items": { "type": "string" } },
        "retailers": { "type": "array", "items": { "type": "string" } }
      }
    },
    "audience_and_positioning": {
      "type": "object",
      "properties": {
        "target_audience":         { "type": "string" },
        "competitors":             { "type": "array", "items": { "type": "string" } },
        "competitive_positioning": { "type": "string" }
      }
    },
    "social_handles": {
      "type": "object",
      "properties": {
        "instagram": { "type": "string" },
        "tiktok":    { "type": "string" },
        "linkedin":  { "type": "string" },
        "twitter":   { "type": "string" }
      }
    },
    "recent_news_12mo": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "date":     { "type": "string" },
          "headline": { "type": "string" },
          "source":   { "type": "string" },
          "url":      { "type": "string" }
        }
      }
    },
    "regulatory_notes": { "type": "string" },
    "sources":          { "type": "array", "items": { "type": "string" } }
  }
}
```

**10 top-level groups:** identity · people · funding · product · distribution · audience_and_positioning · social_handles · recent_news_12mo · regulatory_notes · sources.

---

## 1. Brand: NIC AND JET FUEL

**Seed:** Trend Hunter — *"Nicotine-Infused Energy Drinks"* (Oct 1, 2025, Grace Mahas). Ref: nicandjetfuel.
**Context:** Nicotine-infused canned energy drink. Two strengths — Lite (3 MG) and Max (6 MG). Flavors: Citrus Surge, Grapefruit Spark. Microdosed nicotine + caffeine + adaptogens + nootropics. Sugar-free. Positioned as "clean fuel."

> ⚠️ Disambiguation: ignore aviation jet fuel, JP-8, military fuel, JetBlue. Anchor on SKU names (Lite 3MG / Max 6MG / Citrus Surge / Grapefruit Spark). Emerging brand — Diffbot KG returned "no matching results." Expect thin source coverage.

---

### 1a. Parallel AI — paste this in the Deep Research box (Ultra processor)

```
Produce a complete brand intelligence profile for the company "Nic and Jet Fuel" — a nicotine-infused energy drink brand surfaced via a Trend Hunter article dated October 1, 2025 (author Grace Mahas).

Disambiguation — ignore any results about aviation jet fuel, JP-8, military fuel, JetBlue, or any unrelated "jet fuel" branded product. The target brand sells canned energy drinks with microdosed nicotine in two strengths (Lite 3 MG, Max 6 MG) and two flavors (Citrus Surge, Grapefruit Spark), positioned as "clean fuel."

Brand context from the seed article:
- Canned nicotine-infused energy drinks.
- Lite = 3 MG nicotine. Max = 6 MG nicotine.
- Flavors: Citrus Surge, Grapefruit Spark.
- Formulation: microdosed nicotine + caffeine + adaptogens + nootropics. Sugar-free.
- Positioning: alternative delivery method for existing nicotine users; distances itself from combustible tobacco and vaping; targets performance- and focus-oriented consumers. NOT marketed as smoking-cessation therapy.
- Referenced source: nicandjetfuel (likely nicandjetfuel.com).

Research and report the following fields. Return your final answer as a single JSON object with EXACTLY this nested structure (do not flatten, do not rename). If a field is not publicly available, use null or an empty array — DO NOT GUESS.

{
  "identity": {
    "company_name": "",
    "tagline": "",
    "website": "",
    "founded_year": null,
    "headquarters": ""
  },
  "people": {
    "founders": [],
    "leadership": []
  },
  "funding": {
    "total_usd": null,
    "rounds": [
      { "round": "", "amount_usd": null, "date": "", "investors": [], "source_url": "" }
    ]
  },
  "product": {
    "product_line": [],
    "key_ingredients_or_tech": [],
    "price_points_usd": []
  },
  "distribution": {
    "channels": [],
    "retailers": []
  },
  "audience_and_positioning": {
    "target_audience": "",
    "competitors": [],
    "competitive_positioning": ""
  },
  "social_handles": { "instagram": "", "tiktok": "", "linkedin": "", "twitter": "" },
  "recent_news_12mo": [
    { "date": "", "headline": "", "source": "", "url": "" }
  ],
  "regulatory_notes": "",
  "sources": []
}

Pay specific attention to:
- Founders + their prior companies (likely background: Zyn / Lucy / Velo / Black Buffalo / FRE / Rogue, energy-drink industry, or vape industry).
- Full ingredient stack per SKU with disclosed dosages (nicotine source — synthetic vs tobacco-derived — caffeine mg, specific adaptogens, specific nootropics, sweetener system).
- Co-packer / manufacturing location.
- Specific named retailers (DTC website, smoke shops, gas stations, convenience stores, gyms — note Amazon restricts nicotine).
- US price points per can and per multi-pack.
- Recent news 12 mo — funding, retail expansion, athlete/influencer deals.
- Competitors in the nicotine-beverage category (NicShot, Jolt, Wild Hempettes) and adjacent (Lucy pouches, Zyn, FRE).
- REGULATORY (highest priority) — FDA stance on nicotine-infused beverages, any FDA warning letters to the company or category, PMTA (Premarket Tobacco Application) status, state-level bans / restrictions, age-gating compliance, sales-tax classification, any pending enforcement.

Source preferences in order:
1. Brand website + official press releases.
2. BusinessWire / PR Newswire / Crunchbase / PitchBook.
3. Tobacco Reporter, CSP Daily News, Convenience Store News, Vaping360, BevNet.
4. FDA.gov warning-letter database + state AG press releases.
5. LinkedIn (founder / exec profiles).
6. Founder interviews on podcasts or trade press.

For every fact populated, include the source URL in the `sources` array. This is an emerging brand — expect many null fields and report them honestly. Return ONLY the JSON object, no surrounding prose.
```

---

### 1b. Exa Playground — set up like this

**Search Type:** Deep · **Deep model:** deep-reasoning · **Result category:** Company · **Highlights:** ON · **Number of results:** 25.

**Structured outputs:** ON · **System Prompt:** ON → pick ONE:
- **Option B (recommended):** toggle to **Text** mode → paste prompt from **§0b**.
- **Option A (strict):** toggle to **Object** mode → paste schema from **§0a**.

**Search query field** (paste this regardless of which option you picked above):

```
"Nic and Jet Fuel" company — nicotine-infused canned energy drink brand. SKUs: Lite 3MG nicotine, Max 6MG nicotine. Flavors: Citrus Surge, Grapefruit Spark. Sugar-free, microdosed nicotine plus caffeine, adaptogens, nootropics. Positioned as "clean fuel" for performance and focus. Surfaced via Trend Hunter article October 1 2025 by Grace Mahas, ref nicandjetfuel.

Research: founders and prior companies, leadership, funding history (Crunchbase PitchBook BusinessWire), full ingredient stack per SKU with dosages, co-packer, retailers (DTC, smoke shops, gas stations, convenience), US price points, social handles, recent news 12 months, competitors NicShot Jolt Wild Hempettes Lucy Zyn FRE, and — critically — FDA regulatory status: warning letters, PMTA, state restrictions, age-gating.

IGNORE: aviation jet fuel, JP-8, military fuel, JetBlue, or any unrelated "jet fuel" product.
```

---

## 2. Brand: ULTRA (non-addictive oral pouches)

**Seed:** Trend Hunter — *"Non-Addictive Oral Pouches"* (Jan 21, 2026, Kalin Ned). Ref: businesswire.
**Context:** $11M Series A. Oral pouch — no nicotine, no caffeine. Uses paraxanthine via **Enfinity®**, plus L-theanine, Alpha GPC, B vitamins, ginseng extract.

> ⚠️ Disambiguation: "Ultra" is noisy. Anchor on "non-addictive oral pouch" + "$11M Series A" + "Enfinity paraxanthine" to avoid Ultra music festival, Ultra Mobile, Ulta Beauty, Ultra Tune, etc.

---

### 2a. Parallel AI — paste this in the Deep Research box (Ultra processor)

```
Produce a complete brand intelligence profile for the company "Ultra" — specifically the brand making NON-ADDICTIVE oral pouches that raised an $11 million Series A announced via BusinessWire in January 2026. This is NOT Ultra music festival, Ultra Mobile, Ulta Beauty, Ultra Tune, Ultra Records, or any other "Ultra"-named entity.

Disambiguation anchors (the target brand has all of these):
- Product: oral pouch, no nicotine, no caffeine, sugar-free.
- $11 million Series A announced ~January 2026 via BusinessWire.
- Uses paraxanthine delivered via Enfinity® (a branded paraxanthine ingredient licensed from Ingenious Ingredients / TSI Group).
- Other ingredients: L-theanine, Alpha GPC, B vitamins, ginseng extract.
- Positioning: cognitive enhancement / focus for professionals and athletes — performance without nicotine, caffeine, or addictive compounds.

Research and report the following fields. Return your final answer as a single JSON object with EXACTLY this nested structure (do not flatten, do not rename). If a field is not publicly available, use null or an empty array — DO NOT GUESS.

{
  "identity": {
    "company_name": "",
    "tagline": "",
    "website": "",
    "founded_year": null,
    "headquarters": ""
  },
  "people": {
    "founders": [],
    "leadership": []
  },
  "funding": {
    "total_usd": null,
    "rounds": [
      { "round": "", "amount_usd": null, "date": "", "investors": [], "source_url": "" }
    ]
  },
  "product": {
    "product_line": [],
    "key_ingredients_or_tech": [],
    "price_points_usd": []
  },
  "distribution": {
    "channels": [],
    "retailers": []
  },
  "audience_and_positioning": {
    "target_audience": "",
    "competitors": [],
    "competitive_positioning": ""
  },
  "social_handles": { "instagram": "", "tiktok": "", "linkedin": "", "twitter": "" },
  "recent_news_12mo": [
    { "date": "", "headline": "", "source": "", "url": "" }
  ],
  "regulatory_notes": "",
  "sources": []
}

Pay specific attention to:
- Founders + prior companies. Many oral-pouch founders come from Zyn, Lucy, On!, Velo, Rogue, FRE, or the wellness industry.
- $11M Series A — confirm date, lead investor, participating investors, post-money valuation if disclosed. List any prior pre-seed / seed rounds.
- Enfinity® / paraxanthine sourcing relationship — is Ultra a licensee of TSI Group / Ingenious Ingredients? Any exclusivity?
- Full SKU list — every flavor and strength of the non-addictive pouch line, with disclosed per-pouch dosages.
- Specific named retailers (DTC, Amazon, convenience, gas stations, smoke shops, gyms, supplement retailers).
- US price points per tin and per multi-pack.
- Recent news 12 mo — funding, retail expansion, athlete/influencer deals, product launches.
- Direct competitors in non-nicotine functional pouches (Lucy Breaks, FRE, Rogue, Black Buffalo, Grinds, Neuro Gum/Mints, Magic Mind).
- REGULATORY — FDA / FTC status of paraxanthine, GRAS filings, label/claim disputes, ingredient compliance issues. Paraxanthine + Enfinity is a relatively new GRAS ingredient — research current status.

Source preferences in order:
1. BusinessWire / PR Newswire $11M Series A announcement (this is the seed source).
2. Brand website + official press releases.
3. Crunchbase / PitchBook / Dealroom (funding verification).
4. Tobacco Reporter / CSP Daily News / Convenience Store News (trade press).
5. LinkedIn (founder / exec profiles).
6. Founder interviews on podcasts or trade press.

For every fact populated, include the source URL in `sources`. Do not confuse this entity with Ultra music festival, Ultra Mobile, Ulta Beauty, Ultra Tune, or any other "Ultra" company. Return ONLY the JSON object, no surrounding prose.
```

---

### 2b. Exa Playground — set up like this

**Search Type:** Deep · **Deep model:** deep-reasoning · **Result category:** Company · **Highlights:** ON · **Number of results:** 25.

**Structured outputs:** ON · **System Prompt:** ON → pick ONE:
- **Option B (recommended):** toggle to **Text** mode → paste prompt from **§0b**.
- **Option A (strict):** toggle to **Object** mode → paste schema from **§0a**.

**Search query field** (paste this regardless of which option you picked above):

```
"Ultra" company — brand making NON-ADDICTIVE oral pouches with NO nicotine and NO caffeine. Raised $11 million Series A announced via BusinessWire January 21 2026. Ingredients: paraxanthine delivered as Enfinity (licensed from TSI Group / Ingenious Ingredients), L-theanine, Alpha GPC, B vitamins, ginseng extract. Sugar-free. Targets professionals and athletes for cognitive enhancement and focus. Surfaced via Trend Hunter article January 21 2026 by Kalin Ned.

Research: legal entity, founders and prior companies (often ex-nicotine industry — Zyn, Lucy, On!, Velo, Rogue, FRE), leadership, $11M Series A details (lead investor, participating investors, valuation, date), prior rounds, full SKU list with flavors and strengths, Enfinity / paraxanthine licensing relationship, full ingredient stack with per-pouch dosages, retailers (DTC, Amazon, convenience, gas stations, smoke shops, gyms), US price points, social handles, recent news 12 months, competitors Lucy Breaks FRE Rogue Black Buffalo Grinds Neuro Magic Mind, and regulatory status of paraxanthine (FDA, GRAS, label disputes).

IGNORE: Ultra music festival, Ultra Mobile MVNO, Ulta Beauty, Ultra Tune, Ultra Records, or any other "Ultra"-named company.
```

---

## How to compare the four outputs

Run both brands through both tools → 4 JSON blobs. Diff them field-by-field on:
- **Coverage** — count of non-null fields.
- **Accuracy** — spot-check 3 facts per blob against the cited URL.
- **Source quality** — primary (brand site, BW, Crunchbase) vs secondary (blog roundups).
- **Latency** — seconds.
- **Cost** — Parallel Ultra is more expensive than Exa Deep.

Decision rule for v1: whichever tool wins on coverage + accuracy for ≥2 of the 2 brands becomes primary; the other becomes fallback.

---

## Honest caveat about UI vs strict JSON

Because Parallel AI's UI doesn't have a real schema field:
- Parallel may sometimes wrap the JSON in markdown fences (```json … ```) or add a one-line preamble. Strip those when comparing.
- Parallel may occasionally rename fields or add extra ones. Light normalization needed.
- If you want **strict same-shape JSON on both sides without manual cleanup**, you'll need to call Parallel's API instead of the UI. ~15 lines of Python — let me know and I'll write it.

Exa Playground's structured output is enforced on its side, so its JSON will be clean.
