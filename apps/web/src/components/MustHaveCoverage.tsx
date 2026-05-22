import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp, CheckCircle2, AlertCircle, MinusCircle } from "lucide-react";

import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

/**
 * Must-Have Coverage card.
 *
 * Renders the "must-have" parameters from the NORAD spec as a grouped,
 * expandable checklist (~47-49 rows depending on how composite params are
 * split). Each row reflects coverage status derived from the synthesized
 * CompanyCardV1:
 *   verified  — Claude returned a value with confidence="confirmed"
 *               (or a hard-fact field like company_name is populated)
 *   uncertain — value present but confidence is "estimated" / "inferred"
 *   missing   — no value / confidence="unknown"
 *
 * Click any row to see the value, Claude's basis (why it believes it), and
 * which source ids back it up.
 */

type Status = "verified" | "uncertain" | "missing";

type Cell = {
  value: unknown;
  confidence?: string;
  basis?: string | null;
  sources?: number[];
  status: Status;
};

type Row = {
  label: string;
  pick: (card: any) => Cell;
};

type Group = {
  label: string;
  rows: Row[];
};

// ── helpers ────────────────────────────────────────────────────────────────

const isEmpty = (v: unknown): boolean => {
  if (v === null || v === undefined) return true;
  if (typeof v === "string") return v.trim() === "";
  if (Array.isArray(v)) return v.length === 0;
  if (typeof v === "object") return Object.keys(v as object).length === 0;
  return false;
};

/** Cell from a `Valued[T]` field on the card (with confidence + basis). */
function valued(v: any): Cell {
  const value = v?.value;
  const confidence = v?.confidence as string | undefined;
  const basis = v?.basis ?? null;
  const sources = Array.isArray(v?.sources) ? v.sources : [];
  return { value, confidence, basis, sources, status: statusFor(value, confidence) };
}

/** Map a confidence string to a coverage Status, given the value is non-empty.
 *  Single source of truth so custom rows can't drift from the rule. */
function statusFor(value: unknown, confidence: string | undefined): Status {
  if (isEmpty(value)) return "missing";
  if (confidence === "confirmed") return "verified";
  if (confidence === "estimated" || confidence === "inferred") return "uncertain";
  return "missing"; // unknown / undefined / anything else
}

/** Cell from a plain (non-Valued) field on the card. Direct fact = verified. */
function plain(value: unknown): Cell {
  const empty = isEmpty(value);
  return {
    value,
    confidence: empty ? "unknown" : "confirmed",
    basis: null,
    sources: [],
    status: empty ? "missing" : "verified",
  };
}

/** Format any cell value into a short display string. */
function display(v: unknown): string {
  if (isEmpty(v)) return "—";
  if (typeof v === "string") return v;
  if (typeof v === "number") return Number.isFinite(v) ? v.toLocaleString() : "—";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (Array.isArray(v)) {
    const parts = v
      .map((x) => (typeof x === "string" ? x : x?.name ?? null))
      .filter((s): s is string => !!s);
    if (parts.length === 0) return `${v.length} item${v.length === 1 ? "" : "s"}`;
    return parts.slice(0, 4).join(", ") + (parts.length > 4 ? ` +${parts.length - 4}` : "");
  }
  if (typeof v === "object") {
    const o = v as Record<string, unknown>;
    if ("low" in o || "high" in o) {
      const cur = (o.currency as string) || "USD";
      const fmt = (n: unknown) =>
        typeof n === "number"
          ? n >= 1e9
            ? `${(n / 1e9).toFixed(1)}B`
            : n >= 1e6
              ? `${(n / 1e6).toFixed(1)}M`
              : n.toLocaleString()
          : "?";
      return `${cur} ${fmt(o.low)}–${fmt(o.high)}`;
    }
    if ("name" in o && typeof o.name === "string") return o.name;
    return JSON.stringify(o).slice(0, 80);
  }
  return String(v);
}

// ── parameter map (the 47 must-haves from the NORAD spec) ──────────────────

const GROUPS: Group[] = [
  {
    label: "Identity",
    rows: [
      { label: "Company name", pick: (c) => plain(c?.company_identity?.company_name) },
      { label: "Website", pick: (c) => plain(c?.company_identity?.website ?? c?.company_identity?.domain) },
      { label: "Legal entity", pick: (c) => plain(c?.company_identity?.legal_entity_name) },
      { label: "Founded date", pick: (c) => plain(c?.company_identity?.founded_date ?? c?.company_identity?.founded_year) },
      { label: "Headquarters", pick: (c) => plain(c?.company_identity?.headquarters) },
      { label: "Status", pick: (c) => plain(c?.company_identity?.status && c.company_identity.status !== "unknown" ? c.company_identity.status : null) },
    ],
  },
  {
    label: "Classification",
    rows: [
      { label: "Industry", pick: (c) => plain(c?.classification?.industry) },
      { label: "Sector", pick: (c) => plain(c?.classification?.sector) },
      { label: "Category", pick: (c) => plain(c?.classification?.category) },
      { label: "Subcategory", pick: (c) => plain(c?.classification?.subcategory) },
    ],
  },
  {
    label: "People",
    rows: [
      { label: "CEO", pick: (c) => plain(c?.people_and_decision_map?.ceo?.name) },
      { label: "Founders", pick: (c) => plain(c?.people_and_decision_map?.founders) },
      { label: "Key executives", pick: (c) => plain(c?.people_and_decision_map?.executives) },
      { label: "Decision map", pick: (c) => plain(c?.people_and_decision_map?.decision_map) },
    ],
  },
  {
    label: "Traction",
    rows: [
      { label: "Employee count", pick: (c) => valued(c?.traction_and_momentum?.employee_count_estimate) },
      { label: "Employee growth", pick: (c) => valued(c?.traction_and_momentum?.employee_growth_90d) },
    ],
  },
  {
    label: "Products",
    rows: [
      { label: "Products", pick: (c) => plain(c?.products_and_skus?.products) },
      { label: "SKUs (count)", pick: (c) => valued(c?.products_and_skus?.sku_count) },
      {
        label: "Product claims",
        pick: (c) => {
          const list: string[] = [];
          const prods = c?.products_and_skus?.products;
          if (Array.isArray(prods)) {
            for (const p of prods) {
              if (Array.isArray(p?.claims)) list.push(...p.claims);
            }
          }
          return plain(list.length ? list : null);
        },
      },
      { label: "Pricing", pick: (c) => plain(c?.products_and_skus?.pricing_summary) },
    ],
  },
  {
    label: "Distribution",
    rows: [
      { label: "Store count", pick: (c) => valued(c?.distribution_and_channels?.store_count_estimate) },
      { label: "Retail partners", pick: (c) => plain(c?.distribution_and_channels?.retail_partners) },
      {
        label: "Distribution channels",
        pick: (c) => {
          const d = c?.distribution_and_channels ?? {};
          const present: string[] = [];
          if (d.dtc_presence && d.dtc_presence !== "none") present.push(`DTC (${d.dtc_presence})`);
          if (d.retail_presence && d.retail_presence !== "none") present.push(`Retail (${d.retail_presence})`);
          if (d.wholesale_presence && d.wholesale_presence !== "none") present.push(`Wholesale (${d.wholesale_presence})`);
          if (d.marketplace_presence && d.marketplace_presence !== "none") present.push(`Marketplace (${d.marketplace_presence})`);
          return plain(present.length ? present : null);
        },
      },
    ],
  },
  {
    label: "Business Model",
    rows: [
      { label: "Business model", pick: (c) => valued(c?.business_model?.business_model_summary) },
    ],
  },
  {
    label: "Financials",
    rows: [
      { label: "Revenue estimate", pick: (c) => valued(c?.financials?.revenue_estimate) },
    ],
  },
  {
    label: "Funding",
    rows: [
      { label: "Funding raised (total)", pick: (c) => valued(c?.funding_and_investors?.total_funding) },
      {
        label: "Last funding round",
        pick: (c) =>
          plain(
            c?.funding_and_investors?.last_round_type
              ? `${c.funding_and_investors.last_round_type}${c.funding_and_investors.last_round_date ? " · " + c.funding_and_investors.last_round_date : ""}`
              : null,
          ),
      },
      { label: "Investors", pick: (c) => plain(c?.funding_and_investors?.known_investors) },
      { label: "Valuation estimate", pick: (c) => valued(c?.funding_and_investors?.last_valuation_estimate) },
    ],
  },
  {
    label: "Market",
    rows: [
      { label: "Similar companies", pick: (c) => plain(c?.market_and_competitors?.private_comparables) },
      { label: "Competitors", pick: (c) => plain(c?.market_and_competitors?.direct_competitors) },
      { label: "Market/category trend", pick: (c) => plain(c?.market_and_competitors?.consumer_trends) },
    ],
  },
  {
    label: "Brand & Sentiment",
    rows: [
      {
        label: "Social stats",
        pick: (c) => {
          const b = c?.brand_marketing_sentiment ?? {};
          const cands = [b.instagram_followers, b.tiktok_followers, b.linkedin_followers].filter(
            (x: any) => x && !isEmpty(x?.value),
          );
          if (cands.length === 0) {
            return { value: null, confidence: "unknown", basis: null, sources: [], status: "missing" };
          }
          // Best-confidence candidate becomes the row's representative.
          const rank = (x: any) =>
            x?.confidence === "confirmed" ? 3 : x?.confidence === "estimated" ? 2 : x?.confidence === "inferred" ? 1 : 0;
          const best = [...cands].sort((a, b) => rank(b) - rank(a))[0];
          const parts: string[] = [];
          const fmt = (n: any) => (typeof n === "number" ? n.toLocaleString() : String(n));
          if (!isEmpty(b.instagram_followers?.value)) parts.push(`IG ${fmt(b.instagram_followers.value)}`);
          if (!isEmpty(b.tiktok_followers?.value)) parts.push(`TT ${fmt(b.tiktok_followers.value)}`);
          if (!isEmpty(b.linkedin_followers?.value)) parts.push(`LI ${fmt(b.linkedin_followers.value)}`);
          const value = parts.join(" · ");
          return {
            value,
            confidence: best?.confidence,
            basis: best?.basis ?? null,
            sources: Array.isArray(best?.sources) ? best.sources : [],
            status: statusFor(value, best?.confidence),
          };
        },
      },
      { label: "Social growth", pick: (c) => valued(c?.traction_and_momentum?.social_follower_growth_90d) },
      { label: "Consumer sentiment", pick: (c) => valued(c?.products_and_skus?.review_summary) },
      { label: "News mentions", pick: (c) => plain(c?.traction_and_momentum?.awards) },
      { label: "Partnerships", pick: (c) => plain(c?.traction_and_momentum?.new_distributor_partnerships) },
    ],
  },
  {
    label: "Tech & IP",
    rows: [
      { label: "Patents / trademarks", pick: (c) => plain(c?.technology_ip_defensibility?.patents ?? c?.technology_ip_defensibility?.trademarks) },
    ],
  },
  {
    label: "Risk",
    rows: [
      {
        label: "Regulatory risks",
        pick: (c) => {
          const lvl = c?.legal_regulatory_risk?.overall_risk_level;
          return plain(lvl && lvl !== "unknown" ? lvl : null);
        },
      },
      {
        label: "Lawsuits / recalls",
        pick: (c) => {
          const r = c?.legal_regulatory_risk ?? {};
          const arr = [
            ...(Array.isArray(r.lawsuits) ? r.lawsuits : []),
            ...(Array.isArray(r.product_recalls) ? r.product_recalls : []),
          ];
          return plain(arr.length ? arr : null);
        },
      },
    ],
  },
  {
    label: "Signals",
    rows: (["growth", "fundraising", "acquisition", "partnership", "risk"] as const).map((t) => ({
      label: `${t[0].toUpperCase()}${t.slice(1)} signals`,
      pick: (c: any) => {
        const sigs = Array.isArray(c?.signals) ? c.signals : [];
        return plain(sigs.filter((s: any) => s?.type === t).map((s: any) => s?.headline).filter(Boolean));
      },
    })),
  },
  {
    label: "Strategic Fit",
    rows: [
      { label: "Strategic fit", pick: (c) => valued(c?.strategic_fit?.fit_summary) },
      { label: "Recommended next action", pick: (c) => valued(c?.strategic_fit?.recommended_next_action) },
    ],
  },
  {
    label: "Provenance",
    rows: [
      {
        label: "Source URLs",
        pick: (c) => {
          const srcs = c?.sources_and_confidence?.sources;
          const n = Array.isArray(srcs) ? srcs.length : 0;
          return plain(n ? `${n} sources` : null);
        },
      },
      {
        label: "Overall confidence",
        pick: (c) => {
          const oc = c?.sources_and_confidence?.overall_confidence;
          if (!oc || oc === "unknown") return { value: null, confidence: "unknown", basis: null, sources: [], status: "missing" };
          return {
            value: oc,
            confidence: oc === "high" ? "confirmed" : "estimated",
            basis: c?.sources_and_confidence?.coverage_summary ?? null,
            sources: [],
            status: oc === "high" ? "verified" : "uncertain",
          };
        },
      },
    ],
  },
];

// ── UI ──────────────────────────────────────────────────────────────────────

const STATUS_META: Record<
  Status,
  { label: string; icon: typeof CheckCircle2; chip: string; dot: string }
> = {
  verified: {
    label: "Verified",
    icon: CheckCircle2,
    chip: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-500",
  },
  uncertain: {
    label: "Uncertain",
    icon: AlertCircle,
    chip: "bg-amber-50 text-amber-700 border-amber-200",
    dot: "bg-amber-500",
  },
  missing: {
    label: "Missing",
    icon: MinusCircle,
    chip: "bg-tint text-soft border-border",
    dot: "bg-soft/50",
  },
};

export function MustHaveCoverage({ card }: { card: any }) {
  const [expanded, setExpanded] = useState(false);

  const totals = useMemo(() => {
    let v = 0,
      u = 0,
      m = 0,
      total = 0;
    for (const g of GROUPS) {
      for (const r of g.rows) {
        total++;
        const cell = r.pick(card);
        if (cell.status === "verified") v++;
        else if (cell.status === "uncertain") u++;
        else m++;
      }
    }
    return { v, u, m, total };
  }, [card]);

  const pct = Math.round(((totals.v + totals.u * 0.5) / Math.max(totals.total, 1)) * 100);
  // Collapsed = preview of just the first group (Identity) so the user can
  // see what the audit looks like without it dominating the page.
  const visibleGroups = expanded ? GROUPS : GROUPS.slice(0, 1);
  const hiddenRowCount = GROUPS.slice(1).reduce((n, g) => n + g.rows.length, 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile Completeness</CardTitle>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold tabular-nums text-ink">
            {pct}%
          </span>
          <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-soft">
            · {totals.v} verified · {totals.u} uncertain · {totals.m} missing
          </span>
        </div>
      </CardHeader>

      {/* Coverage bar */}
      <div className="px-5 pb-3 pt-3">
        <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-tint">
          <div
            className="h-full bg-emerald-500"
            style={{ width: `${(totals.v / totals.total) * 100}%` }}
          />
          <div
            className="h-full bg-amber-400"
            style={{ width: `${(totals.u / totals.total) * 100}%` }}
          />
        </div>
      </div>

      <CardBody className="px-0 py-0">
        <div className="divide-y divide-border/60">
          {visibleGroups.map((g) => (
            <GroupBlock key={g.label} group={g} card={card} />
          ))}
        </div>

        {/* Expand / collapse toggle. When collapsed we only show Identity;
            the rest is one click away. */}
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="flex w-full items-center justify-center gap-1.5 border-t border-border/60 bg-tint/30 px-5 py-2.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-soft transition-colors hover:bg-tint/60 hover:text-ink"
        >
          {expanded ? (
            <>
              <ChevronUp className="h-3 w-3" />
              Show less
            </>
          ) : (
            <>
              <ChevronDown className="h-3 w-3" />
              Show full audit · {hiddenRowCount} more
            </>
          )}
        </button>
      </CardBody>
    </Card>
  );
}

function GroupBlock({ group, card }: { group: Group; card: any }) {
  const cells = group.rows.map((r) => ({ row: r, cell: r.pick(card) }));
  const verified = cells.filter((x) => x.cell.status === "verified").length;
  const uncertain = cells.filter((x) => x.cell.status === "uncertain").length;
  const missing = cells.filter((x) => x.cell.status === "missing").length;

  return (
    <section>
      <header className="flex items-center justify-between bg-tint/40 px-5 py-2">
        <span className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-soft">
          {group.label}
        </span>
        <span className="flex items-center gap-2 text-[10px] font-medium text-soft">
          <span className="inline-flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            {verified}
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
            {uncertain}
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-soft/40" />
            {missing}
          </span>
        </span>
      </header>
      <ul>
        {cells.map(({ row, cell }) => (
          <ParamRow key={row.label} label={row.label} cell={cell} />
        ))}
      </ul>
    </section>
  );
}

function ParamRow({ label, cell }: { label: string; cell: Cell }) {
  const [open, setOpen] = useState(false);
  const meta = STATUS_META[cell.status];
  const Icon = meta.icon;
  const hasDetails = cell.basis || (cell.sources && cell.sources.length > 0) || !isEmpty(cell.value);

  return (
    <li className="border-t border-border/40 first:border-t-0">
      <button
        type="button"
        onClick={() => hasDetails && setOpen((o) => !o)}
        className={cn(
          "flex w-full items-center gap-3 px-5 py-2.5 text-left transition-colors",
          hasDetails ? "hover:bg-tint/40" : "cursor-default",
        )}
      >
        <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", meta.dot)} />
        <span className="flex-1 truncate text-[12.5px] font-medium text-ink">
          {label}
        </span>
        <span
          className={cn(
            "max-w-[40%] truncate text-right text-[12px] tabular-nums",
            cell.status === "missing" ? "text-soft/60" : "text-muted",
          )}
        >
          {display(cell.value)}
        </span>
        <span
          className={cn(
            "inline-flex shrink-0 items-center gap-1 rounded-md border px-1.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.06em]",
            meta.chip,
          )}
        >
          <Icon className="h-2.5 w-2.5" />
          {meta.label}
        </span>
        {hasDetails && (
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 shrink-0 text-soft transition-transform",
              open && "rotate-180",
            )}
          />
        )}
      </button>
      {open && hasDetails && (
        <div className="space-y-2 bg-tint/30 px-5 py-3 text-[12px] text-muted">
          {!isEmpty(cell.value) && (
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-soft">
                Value
              </div>
              {typeof cell.value === "string" ? (
                <p className="mt-1 whitespace-pre-wrap break-words text-ink/80">
                  {cell.value}
                </p>
              ) : (
                <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] text-ink/80">
                  {JSON.stringify(cell.value, null, 2)}
                </pre>
              )}
            </div>
          )}
          {cell.confidence && cell.confidence !== "unknown" && (
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-soft">
                Confidence:{" "}
              </span>
              <span className="text-ink capitalize">{cell.confidence}</span>
            </div>
          )}
          {cell.basis && (
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-soft">
                Basis
              </div>
              <p className="mt-0.5 text-ink/80">{cell.basis}</p>
            </div>
          )}
          {cell.sources && cell.sources.length > 0 && (
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-soft">
                Sources:{" "}
              </span>
              <span className="text-ink">
                {cell.sources.map((n) => `[${n}]`).join(" ")}
              </span>
            </div>
          )}
        </div>
      )}
    </li>
  );
}
