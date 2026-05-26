import type { LucideIcon } from "lucide-react";
import {
  Building2,
  Globe2,
  Layers,
  Scale,
  Shield,
  Sparkles,
  Tag,
} from "lucide-react";
import type { ReactElement, ReactNode } from "react";

import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";

type CardDoc = Record<string, unknown>;

function val(v: unknown): unknown {
  if (v != null && typeof v === "object" && "value" in (v as object)) {
    return (v as { value?: unknown }).value;
  }
  return v;
}

function hasText(v: unknown): boolean {
  const x = val(v);
  if (x == null) return false;
  if (typeof x === "string") return x.trim().length > 0;
  return true;
}

function hasItems(v: unknown): boolean {
  return Array.isArray(v) && v.length > 0;
}

function displayList(items: unknown[], max = 8): string {
  const parts = items
    .map((x) => {
      if (typeof x === "string") return x;
      if (x && typeof x === "object" && "name" in x) return String((x as { name: string }).name);
      return null;
    })
    .filter((s): s is string => !!s);
  if (parts.length === 0) return "";
  const shown = parts.slice(0, max).join(", ");
  return parts.length > max ? `${shown} +${parts.length - max}` : shown;
}

function channelLabel(presence: unknown): string | null {
  if (typeof presence !== "string" || presence === "none" || presence === "unknown") {
    return null;
  }
  return presence.replace(/_/g, " ");
}

function FieldRow({ label, value }: { label: string; value: unknown }) {
  if (value == null || value === "") return null;
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-wider text-soft">{label}</div>
      <div className="mt-0.5 text-ink">{String(value)}</div>
    </div>
  );
}

/** Returns null when every body field is empty — no header-only shells. */
function buildIntelSection(
  key: string,
  icon: LucideIcon,
  title: string,
  children: ReactNode[],
) {
  const body = children.filter(Boolean);
  if (body.length === 0) return null;

  const Icon = icon;
  return (
    <Card key={key} className="h-fit w-full break-inside-avoid">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 shrink-0 text-soft" />
          <CardTitle>{title}</CardTitle>
        </div>
      </CardHeader>
      <CardBody className="space-y-3 text-sm">{body}</CardBody>
    </Card>
  );
}

/**
 * Secondary intelligence blocks from CompanyCardV1.
 * Masonry columns so short cards (e.g. Distribution) never stretch to match
 * tall neighbours — each card is only as tall as its content.
 */
export function CompanyBriefSections({ card }: { card: CardDoc }) {
  const products = (card.products_and_skus ?? {}) as Record<string, unknown>;
  const distribution = (card.distribution_and_channels ?? {}) as Record<string, unknown>;
  const business = (card.business_model ?? {}) as Record<string, unknown>;
  const market = (card.market_and_competitors ?? {}) as Record<string, unknown>;
  const legal = (card.legal_regulatory_risk ?? {}) as Record<string, unknown>;
  const brand = (card.brand_marketing_sentiment ?? {}) as Record<string, unknown>;
  const tech = (card.technology_ip_defensibility ?? {}) as Record<string, unknown>;

  const productList = products.products as Array<Record<string, unknown>> | undefined;

  const channels = [
    ["DTC", distribution.dtc_presence],
    ["Retail", distribution.retail_presence],
    ["Wholesale", distribution.wholesale_presence],
    ["Marketplace", distribution.marketplace_presence],
  ]
    .map(([label, p]) => (channelLabel(p) ? `${label}: ${channelLabel(p)}` : null))
    .filter(Boolean) as string[];

  const legalLists: Array<{ label: string; items: unknown[] }> = [
    { label: "Lawsuits", items: (legal.lawsuits as unknown[]) ?? [] },
    { label: "Regulatory warnings", items: (legal.regulatory_warnings as unknown[]) ?? [] },
    { label: "Product recalls", items: (legal.product_recalls as unknown[]) ?? [] },
    { label: "FDA issues", items: (legal.fda_issues as unknown[]) ?? [] },
    { label: "Negative press", items: (legal.negative_press as unknown[]) ?? [] },
  ].filter((row) => hasItems(row.items));

  const techLists: Array<{ label: string; items: unknown[] }> = [
    { label: "Patents", items: (tech.patents_granted as unknown[]) ?? [] },
    { label: "Applications", items: (tech.patent_applications as unknown[]) ?? [] },
    { label: "Trademarks", items: (tech.trademarks as unknown[]) ?? [] },
    { label: "Clinical studies", items: (tech.clinical_studies as unknown[]) ?? [] },
    {
      label: "Exclusive partnerships",
      items: (tech.exclusive_partnerships as unknown[]) ?? [],
    },
  ].filter((row) => hasItems(row.items));

  const moats = [
    ["Manufacturing", tech.manufacturing_moat],
    ["Distribution", tech.distribution_moat],
    ["Brand", tech.brand_moat],
    ["Regulatory", tech.regulatory_moat],
  ]
    .map(([label, m]) => {
      const v = val(m);
      if (typeof v === "string" && v !== "unknown" && v !== "none") {
        return `${label}: ${v}`;
      }
      return null;
    })
    .filter(Boolean) as string[];

  const visible = [
    buildIntelSection("products", Tag, "Products & SKUs", [
        hasText(products.hero_product) ? (
          <div key="hero">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-soft">
              Hero product
            </div>
            <div className="mt-0.5 font-medium text-ink">
              {String(val(products.hero_product))}
            </div>
          </div>
        ) : null,
        hasItems(productList) ? (
          <ul key="list" className="space-y-2">
            {(productList ?? []).slice(0, 6).map((p, i) => (
              <li
                key={`${p.name}-${i}`}
                className="flex items-start gap-2 rounded-md border border-border/60 bg-tint/20 px-3 py-2"
              >
                {p.hero ? (
                  <Pill variant="accent" className="shrink-0">
                    Hero
                  </Pill>
                ) : null}
                <div className="min-w-0">
                  <div className="font-medium text-ink">{String(p.name ?? "Product")}</div>
                  {p.category != null && String(p.category).trim() !== "" && (
                    <div className="text-xs text-muted">{String(p.category)}</div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ) : null,
        hasItems(products.product_categories as unknown[]) ? (
          <FieldRow
            key="cats"
            label="Categories"
            value={displayList(products.product_categories as unknown[])}
          />
        ) : null,
        hasText(products.pricing_summary) ? (
          <FieldRow
            key="pricing"
            label="Pricing"
            value={String(val(products.pricing_summary))}
          />
        ) : null,
    ]),

    buildIntelSection("distribution", Globe2, "Distribution & Channels", [
        channels.length > 0 ? (
          <div key="channels" className="flex flex-wrap gap-1.5">
            {channels.map((c) => (
              <span
                key={c}
                className="rounded-md border border-border bg-white px-2 py-1 text-xs capitalize text-ink"
              >
                {c}
              </span>
            ))}
          </div>
        ) : null,
        hasItems(distribution.retail_partners as unknown[]) ? (
          <FieldRow
            key="retail"
            label="Retail partners"
            value={displayList(distribution.retail_partners as unknown[])}
          />
        ) : null,
        hasItems(distribution.geographic_coverage as unknown[]) ? (
          <FieldRow
            key="geo"
            label="Geography"
            value={displayList(distribution.geographic_coverage as unknown[])}
          />
        ) : null,
        hasItems(distribution.amazon_listings as unknown[]) ? (
          <FieldRow
            key="amazon"
            label="Amazon"
            value={`${(distribution.amazon_listings as unknown[]).length} listing(s)`}
          />
        ) : null,
    ]),

    buildIntelSection("business", Building2, "Business Model", [
        hasText(business.business_model_summary) ? (
          <p key="summary" className="leading-relaxed text-muted">
            {String(val(business.business_model_summary))}
          </p>
        ) : null,
        hasItems(business.revenue_streams as unknown[]) ? (
          <div key="streams" className="flex flex-wrap gap-1.5">
            {(business.revenue_streams as string[]).map((s) => (
              <Pill key={s} variant="neutral">
                {s.replace(/_/g, " ")}
              </Pill>
            ))}
          </div>
        ) : null,
        business.recurring_revenue != null &&
        typeof business.recurring_revenue === "object" &&
        (business.recurring_revenue as { confidence?: string }).confidence !== "unknown" ? (
          <FieldRow
            key="recurring"
            label="Recurring revenue"
            value={val(business.recurring_revenue) ? "Yes" : "No"}
          />
        ) : null,
    ]),

    buildIntelSection("market", Layers, "Market Position", [
        hasText(market.competitive_advantage) ? (
          <div key="adv">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-soft">
              Competitive advantage
            </div>
            <p className="mt-1 leading-relaxed text-muted">
              {String(val(market.competitive_advantage))}
            </p>
          </div>
        ) : null,
        hasText(market.weaknesses) ? (
          <div key="weak">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-soft">
              Weaknesses
            </div>
            <p className="mt-1 leading-relaxed text-muted">
              {String(val(market.weaknesses))}
            </p>
          </div>
        ) : null,
        hasItems(market.category_leaders as unknown[]) ? (
          <FieldRow
            key="leaders"
            label="Category leaders"
            value={displayList(market.category_leaders as unknown[])}
          />
        ) : null,
        hasItems(market.consumer_trends as unknown[]) ? (
          <FieldRow
            key="trends"
            label="Consumer trends"
            value={displayList(market.consumer_trends as unknown[])}
          />
        ) : null,
    ]),

    buildIntelSection("legal", Scale, "Legal & Regulatory", [
        typeof legal.overall_risk_level === "string" &&
        legal.overall_risk_level !== "unknown" ? (
          <Pill
            key="risk"
            variant={
              legal.overall_risk_level === "high" || legal.overall_risk_level === "critical"
                ? "danger"
                : legal.overall_risk_level === "medium"
                  ? "warning"
                  : "neutral"
            }
          >
            Overall risk: {legal.overall_risk_level}
          </Pill>
        ) : null,
        ...legalLists.map((row) => (
          <FieldRow
            key={row.label}
            label={row.label}
            value={displayList(row.items, 4)}
          />
        )),
        hasItems(legal.consumer_complaints_themes as unknown[]) ? (
          <FieldRow
            key="complaints"
            label="Complaint themes"
            value={displayList(legal.consumer_complaints_themes as unknown[], 4)}
          />
        ) : null,
    ]),

    buildIntelSection("brand", Sparkles, "Brand & Marketing", [
        hasText(brand.brand_positioning) ? (
          <div key="pos">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-soft">
              Positioning
            </div>
            <p className="mt-1 leading-relaxed text-muted">
              {String(val(brand.brand_positioning))}
            </p>
          </div>
        ) : null,
        hasText(brand.target_audience) ? (
          <FieldRow
            key="audience"
            label="Target audience"
            value={String(val(brand.target_audience))}
          />
        ) : null,
        hasText(brand.customer_persona) ? (
          <FieldRow key="persona" label="Persona" value={String(val(brand.customer_persona))} />
        ) : null,
        typeof brand.review_sentiment === "string" && brand.review_sentiment !== "unknown" ? (
          <Pill key="reviews" variant="neutral">
            Reviews: {brand.review_sentiment}
          </Pill>
        ) : null,
    ]),

    buildIntelSection("tech", Shield, "Technology & IP", [
        hasText(tech.scientific_backing) ? (
          <p key="science" className="leading-relaxed text-muted">
            {String(val(tech.scientific_backing))}
          </p>
        ) : null,
        moats.length > 0 ? (
          <div key="moats" className="flex flex-wrap gap-1.5">
            {moats.map((m) => (
              <span
                key={m}
                className="rounded-md border border-border bg-tint/30 px-2 py-1 text-xs capitalize"
              >
                {m}
              </span>
            ))}
          </div>
        ) : null,
        ...techLists.map((row) => (
          <FieldRow key={row.label} label={row.label} value={displayList(row.items, 5)} />
        )),
    ]),
  ].filter((node): node is ReactElement => node != null);
  if (visible.length === 0) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-base font-semibold text-ink">Company Intelligence</h2>
        <span className="text-xs text-muted">{visible.length} sections</span>
      </div>

      {/*
        Masonry flow: each card is h-fit + break-inside-avoid so short sections
        never stretch to row height. Order is source order — easy to reorder later.
      */}
      <div className="columns-1 gap-4 md:columns-2 [&>*]:mb-4">
        {visible}
      </div>
    </div>
  );
}
