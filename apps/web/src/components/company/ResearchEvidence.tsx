import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  BookOpen,
  Database,
  ExternalLink,
  Globe,
  Layers,
  Link2,
  Loader2,
  Search,
  Sparkles,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Pill } from "@/components/ui/Pill";
import {
  getCompanyEvidence,
  type CompanyEvidence,
  type DiffbotEvidence,
  type ExaPageRow,
  type ParallelSignal,
  type ParallelBasisField,
  type SourceRow,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type TabId = "overview" | "diffbot" | "parallel" | "exa" | "links";

const TABS: { id: TabId; label: string; icon: typeof Database }[] = [
  { id: "overview", label: "Overview", icon: Layers },
  { id: "diffbot", label: "Knowledge Graph", icon: Database },
  { id: "parallel", label: "Web Research", icon: Sparkles },
  { id: "exa", label: "Live Reads", icon: BookOpen },
  { id: "links", label: "All Links", icon: Link2 },
];

export function ResearchEvidence({
  companyId,
  cardSources,
}: {
  companyId: string;
  cardSources: SourceRow[];
}) {
  const [tab, setTab] = useState<TabId>("overview");

  const q = useQuery({
    queryKey: ["company-evidence", companyId],
    queryFn: () => getCompanyEvidence(companyId),
    staleTime: 60_000,
  });

  const data = q.data;

  if (q.isLoading) {
    return (
      <Card>
        <CardBody className="flex items-center justify-center gap-2 py-14 text-sm text-soft">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading research evidence…
        </CardBody>
      </Card>
    );
  }

  if (q.isError || !data) {
    return (
      <Card>
        <CardBody>
          <EmptyState
            icon={Search}
            title="Evidence unavailable"
            description="Could not load raw engine data for this company."
          />
        </CardBody>
      </Card>
    );
  }

  if (!data.summary.has_evidence && !data.run_id) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Research Evidence</CardTitle>
        </CardHeader>
        <CardBody>
          <EmptyState
            icon={Globe}
            title="No research run yet"
            description="Run company research to collect Diffbot, Parallel, and Exa evidence."
          />
        </CardBody>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-col gap-4 border-b border-border/60 bg-tint/30 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle>Research Evidence</CardTitle>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-muted">
            Everything fetched from Diffbot, Parallel, and Exa — before synthesis
            into the intelligence brief. Use this to see what we actually collected.
          </p>
        </div>
        <EvidenceMeta data={data} />
      </CardHeader>

      <div
        role="tablist"
        aria-label="Research evidence sections"
        className="flex gap-1 overflow-x-auto border-b border-border/60 bg-white px-3 py-2 scrollbar-thin"
      >
        {TABS.map(({ id, label, icon: Icon }) => {
          const active = tab === id;
          const badge = tabBadge(id, data);
          return (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setTab(id)}
              className={cn(
                "inline-flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition",
                active
                  ? "bg-accent text-white shadow-sm"
                  : "text-muted hover:bg-tint hover:text-ink",
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
              {badge != null && (
                <span
                  className={cn(
                    "rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums",
                    active ? "bg-white/20 text-white" : "bg-tint text-soft",
                  )}
                >
                  {badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <CardBody className="min-h-[280px] p-0">
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.18 }}
            className="p-5 sm:p-6"
          >
            {tab === "overview" && <OverviewPanel data={data} onNavigate={setTab} />}
            {tab === "diffbot" && <DiffbotPanel diffbot={data.diffbot} />}
            {tab === "parallel" && <ParallelPanel parallel={data.parallel} />}
            {tab === "exa" && <ExaPanel exa={data.exa} />}
            {tab === "links" && (
              <AllLinksPanel data={data} cardSources={cardSources} />
            )}
          </motion.div>
        </AnimatePresence>
      </CardBody>
    </Card>
  );
}

function tabBadge(id: TabId, data: CompanyEvidence): number | null {
  switch (id) {
    case "diffbot":
      return data.diffbot ? data.diffbot.field_count : null;
    case "parallel":
      return data.parallel?.signal_count || data.parallel?.source_count
        ? (data.parallel?.signal_count ?? 0) + (data.parallel?.source_count ?? 0)
        : null;
    case "exa":
      return data.exa.page_count || data.exa.search_count || null;
    case "links":
      return null;
    default:
      return null;
  }
}

function EvidenceMeta({ data }: { data: CompanyEvidence }) {
  const s = data.summary;
  return (
    <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
      {data.collected_at && (
        <span title={data.collected_at}>
          Collected{" "}
          {new Date(data.collected_at).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </span>
      )}
      {s.total_cost_usd > 0 && (
        <Pill variant="neutral">${s.total_cost_usd.toFixed(2)} engine cost</Pill>
      )}
      {data.run_id && (
        <span className="font-mono text-[10px] text-soft" title={data.run_id}>
          run {data.run_id.slice(0, 8)}
        </span>
      )}
    </div>
  );
}

function OverviewPanel({
  data,
  onNavigate,
}: {
  data: CompanyEvidence;
  onNavigate: (t: TabId) => void;
}) {
  const cards = [
    {
      id: "diffbot" as const,
      title: "Diffbot Knowledge Graph",
      stat: data.diffbot
        ? `${data.diffbot.field_count} fields · score ${(data.diffbot.score * 100).toFixed(0)}%`
        : "Not available",
      detail: data.diffbot?.identity.description?.slice(0, 140),
      ok: !!data.diffbot,
    },
    {
      id: "parallel" as const,
      title: "Parallel Web Research",
      stat: data.parallel
        ? `${data.parallel.signal_count} signals · ${data.parallel.source_count} sources`
        : "Not available",
      detail: data.parallel?.brief.summary?.slice(0, 140),
      ok: !!data.parallel,
    },
    {
      id: "exa" as const,
      title: "Exa Live Reads",
      stat: `${data.exa.page_count} pages · ${data.exa.search_count} searches`,
      detail:
        data.exa.pages[0]?.title ??
        data.exa.searches[0]?.query ??
        undefined,
      ok: data.exa.page_count > 0 || data.exa.search_count > 0,
    },
  ];

  return (
    <div className="space-y-5">
      <p className="text-sm leading-relaxed text-muted">
        Three independent research streams feed the synthesizer. This panel shows
        what each engine returned — including fields that may not appear in the
        intelligence brief above.
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        {cards.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => onNavigate(c.id)}
            className={cn(
              "group rounded-xl border p-4 text-left transition",
              c.ok
                ? "border-border bg-white hover:border-accent/40 hover:shadow-sm"
                : "border-dashed border-border/80 bg-tint/20 opacity-70",
            )}
          >
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-soft">
              {c.title}
            </div>
            <div className="text-sm font-semibold text-ink">{c.stat}</div>
            {c.detail && (
              <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-muted">
                {c.detail}
                {(c.detail.length ?? 0) >= 140 ? "…" : ""}
              </p>
            )}
            <span className="mt-3 inline-flex items-center gap-1 text-[11px] font-medium text-accent opacity-0 transition group-hover:opacity-100">
              View details
              <ExternalLink className="h-3 w-3" />
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function DiffbotPanel({ diffbot }: { diffbot: DiffbotEvidence | null }) {
  if (!diffbot) {
    return (
      <EmptyState
        icon={Database}
        title="No Diffbot data"
        description="Diffbot was skipped or returned no entity for this run."
      />
    );
  }

  const { identity, people, traction, finance, market, links, origins } = diffbot;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2">
        <Pill variant="success">Match {(diffbot.score * 100).toFixed(0)}%</Pill>
        <Pill variant="neutral">{diffbot.field_count} KG fields</Pill>
        <Pill variant="neutral">{diffbot.latency_ms.toFixed(0)} ms</Pill>
      </div>

      {identity.description && (
        <section>
          <SectionLabel>Description</SectionLabel>
          <p className="text-sm leading-relaxed text-ink">{identity.description}</p>
        </section>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <FieldGrid
          fields={[
            ["Name", identity.name],
            ["Also known as", identity.aka],
            ["HQ", identity.hq],
            ["Founded", identity.founded],
            ["Employees", traction.employees],
            ["Public", identity.is_public != null ? (identity.is_public ? "Yes" : "No") : null],
            ["Stock", identity.stock],
          ]}
        />

        {links.length > 0 && (
          <section>
            <SectionLabel>Official links</SectionLabel>
            <ul className="space-y-2">
              {links.map((l) => (
                <li key={l.url}>
                  <ExternalAnchor href={l.url} label={l.label} />
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      {(people.ceo || people.founders.length > 0 || people.executives.length > 0) && (
        <section>
          <SectionLabel>People</SectionLabel>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {people.ceo && <PersonCard person={people.ceo} badge="CEO" />}
            {people.founders.map((p) => (
              <PersonCard key={p.name} person={p} badge="Founder" />
            ))}
            {people.executives.map((p) => (
              <PersonCard key={`${p.name}-${p.title}`} person={p} badge="Executive" />
            ))}
          </div>
        </section>
      )}

      {finance.investments.length > 0 && (
        <section>
          <SectionLabel>Investments ({finance.investment_count})</SectionLabel>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[480px] text-left text-xs">
              <thead className="bg-tint/60 text-[10px] uppercase tracking-wider text-soft">
                <tr>
                  <th className="px-3 py-2 font-semibold">Date</th>
                  <th className="px-3 py-2 font-semibold">Series</th>
                  <th className="px-3 py-2 font-semibold">Amount</th>
                  <th className="px-3 py-2 font-semibold">Investors</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {finance.investments.map((inv, i) => (
                  <tr key={i} className="hover:bg-tint/40">
                    <td className="px-3 py-2 text-muted">{inv.date ?? "—"}</td>
                    <td className="px-3 py-2">{inv.series ?? "—"}</td>
                    <td className="px-3 py-2 tabular-nums">{fmtMoney(inv.amount_usd)}</td>
                    <td className="px-3 py-2 text-muted">
                      {inv.investors?.length ? inv.investors.join(", ") : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {(market.industries.length > 0 ||
        market.categories.length > 0 ||
        market.competitors.length > 0) && (
        <section className="grid gap-4 md:grid-cols-3">
          <TagList label="Industries" items={market.industries} />
          <TagList label="Categories" items={market.categories} />
          <TagList label="Competitors" items={market.competitors} />
        </section>
      )}

      {origins.length > 0 && (
        <section>
          <SectionLabel>Origins ({origins.length})</SectionLabel>
          <ul className="max-h-48 space-y-1 overflow-y-auto rounded-lg border border-border bg-tint/20 p-3">
            {origins.map((u) => (
              <li key={u}>
                <ExternalAnchor href={u} label={shortUrl(u)} mono />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function ParallelPanel({
  parallel,
}: {
  parallel: CompanyEvidence["parallel"];
}) {
  if (!parallel?.brief) {
    return (
      <EmptyState
        icon={Sparkles}
        title="No Parallel data"
        description="Parallel web research did not return a brief for this run."
      />
    );
  }

  const b = parallel.brief;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2">
        {parallel.processor && <Pill variant="neutral">{parallel.processor}</Pill>}
        <Pill variant="neutral">{parallel.signal_count} signals</Pill>
        <Pill variant="neutral">{parallel.source_count} sources</Pill>
        {parallel.cost_usd > 0 && (
          <Pill variant="neutral">${parallel.cost_usd.toFixed(3)}</Pill>
        )}
      </div>

      {b.summary && (
        <section>
          <SectionLabel>Summary</SectionLabel>
          <p className="text-sm leading-relaxed text-ink">{b.summary}</p>
        </section>
      )}

      <FieldGrid
        columns={3}
        fields={[
          ["Legal name", b.legal_entity_name],
          ["Domain", b.domain],
          ["Website", b.website],
          ["HQ", b.headquarters],
          ["Founded", b.founded_year],
          ["CEO", b.ceo],
          ["Status", b.status],
          ["Industry", b.industry],
          ["Category", b.category],
          ["Business type", b.business_type],
          ["Employees", b.employee_count_estimate],
          ["Hiring pace", b.hiring_pace],
          ["Revenue est.", b.revenue_estimate_usd],
          ["Total funding", fmtMoney(b.total_funding_usd)],
          ["Last round", b.last_round_type],
          ["Last round date", b.last_round_date],
          ["Last round $", fmtMoney(b.last_round_amount_usd)],
        ]}
      />

      {b.products && b.products.length > 0 && (
        <TagList label="Products" items={b.products} />
      )}
      {b.investors && b.investors.length > 0 && (
        <TagList label="Investors" items={b.investors} />
      )}
      {b.competitors && b.competitors.length > 0 && (
        <TagList label="Competitors" items={b.competitors} />
      )}
      {b.competitive_advantage && (
        <section>
          <SectionLabel>Competitive advantage</SectionLabel>
          <p className="text-sm leading-relaxed text-ink">{b.competitive_advantage}</p>
        </section>
      )}

      {b.signals && b.signals.length > 0 && (
        <section>
          <SectionLabel>Signals from Parallel ({b.signals.length})</SectionLabel>
          <ul className="space-y-3">
            {b.signals.map((sig, i) => (
              <ParallelSignalRow key={i} signal={sig} />
            ))}
          </ul>
        </section>
      )}

      {b.sources && b.sources.length > 0 && (
        <section>
          <SectionLabel>Parallel sources ({b.sources.length})</SectionLabel>
          <ul className="divide-y divide-border/60 rounded-lg border border-border">
            {b.sources.map((s) => (
              <li key={s.url} className="flex items-start gap-3 px-3 py-2.5 text-xs">
                <div className="min-w-0 flex-1">
                  <ExternalAnchor
                    href={s.url}
                    label={s.title ?? shortUrl(s.url)}
                  />
                  <div className="mt-0.5 truncate font-mono text-[10px] text-soft">
                    {s.url}
                  </div>
                </div>
                {s.trust_tier && (
                  <span className="shrink-0 rounded bg-tint px-1.5 py-0.5 text-[10px] font-semibold text-muted">
                    tier {s.trust_tier}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {parallel.basis && parallel.basis.length > 0 && (
        <section>
          <SectionLabel>
            Field provenance ({parallel.basis.length} fields)
          </SectionLabel>
          <p className="mb-3 text-xs text-muted">
            Per-field citations and reasoning from Parallel&apos;s research pass —
            useful when the brief and card disagree.
          </p>
          <ul className="space-y-3">
            {parallel.basis.map((item, i) => (
              <BasisFieldRow key={`${item.field}-${i}`} item={item} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function BasisFieldRow({ item }: { item: ParallelBasisField }) {
  const [open, setOpen] = useState(false);
  const cites = item.citations ?? [];
  return (
    <li className="rounded-lg border border-border bg-tint/10">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <span className="font-mono text-xs font-semibold text-ink">
          {item.field ?? "field"}
        </span>
        <span className="flex items-center gap-2 text-[10px] text-muted">
          {item.confidence && (
            <span className="rounded bg-white px-1.5 py-0.5 border border-border">
              {item.confidence}
            </span>
          )}
          {cites.length > 0 && <span>{cites.length} cites</span>}
          <span className="text-accent">{open ? "Hide" : "Show"}</span>
        </span>
      </button>
      {open && (
        <div className="border-t border-border/60 px-4 py-3 space-y-3">
          {item.reasoning && (
            <p className="text-xs leading-relaxed text-muted">{item.reasoning}</p>
          )}
          {cites.map((c, j) => (
            <div key={j} className="rounded-md bg-white border border-border/60 p-3 text-xs">
              {c.url && (
                <ExternalAnchor href={c.url} label={c.title ?? shortUrl(c.url)} />
              )}
              {(c.excerpts ?? []).map((ex, k) => (
                <p key={k} className="mt-1.5 text-muted leading-relaxed">
                  &ldquo;{ex}&rdquo;
                </p>
              ))}
            </div>
          ))}
        </div>
      )}
    </li>
  );
}

function ExaPanel({ exa }: { exa: CompanyEvidence["exa"] }) {
  if (exa.search_count === 0 && exa.page_count === 0) {
    return (
      <EmptyState
        icon={BookOpen}
        title="No Exa reads"
        description="Exa search and content fetch did not run or returned nothing."
      />
    );
  }

  return (
    <div className="space-y-6">
      {exa.searches.length > 0 && (
        <section>
          <SectionLabel>Search queries ({exa.searches.length})</SectionLabel>
          <ul className="space-y-2">
            {exa.searches.map((s, i) => (
              <li
                key={i}
                className="rounded-lg border border-border bg-tint/20 px-3 py-2.5 text-xs"
              >
                <div className="font-medium text-ink">&ldquo;{s.query}&rdquo;</div>
                <div className="mt-1 text-muted">
                  {s.count} URLs · {s.search_type ?? "search"}
                  {s.latency_ms ? ` · ${s.latency_ms.toFixed(0)} ms` : ""}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {exa.pages.length > 0 && (
        <section>
          <SectionLabel>Fetched pages ({exa.pages.length})</SectionLabel>
          <ul className="space-y-4">
            {exa.pages.map((p) => (
              <ExaPageCard key={p.url} page={p} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function ExaPageCard({ page }: { page: ExaPageRow }) {
  const [expanded, setExpanded] = useState(false);
  const preview = page.text_preview;
  const hasMore = (preview?.length ?? 0) > 400;

  return (
    <li className="rounded-xl border border-border bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <ExternalAnchor
            href={page.url}
            label={page.title ?? "Untitled page"}
            className="text-sm font-semibold"
          />
          <div className="mt-0.5 truncate font-mono text-[10px] text-soft">
            {page.url}
          </div>
        </div>
        <div className="shrink-0 text-right text-[10px] text-muted">
          {page.chars != null && <div>{page.chars.toLocaleString()} chars</div>}
          {page.published_date && <div>{page.published_date}</div>}
          {page.snippet_source && (
            <div className="text-soft">via card snippet</div>
          )}
        </div>
      </div>
      {preview && (
        <div className="mt-3">
          <p
            className={cn(
              "text-xs leading-relaxed text-muted",
              !expanded && hasMore && "line-clamp-6",
            )}
          >
            {preview}
          </p>
          {hasMore && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="mt-2 text-[11px] font-medium text-accent hover:underline"
            >
              {expanded ? "Show less" : "Show full preview"}
            </button>
          )}
        </div>
      )}
      {!preview && (
        <p className="mt-2 text-xs italic text-soft">
          Full page text was not stored for this run — only URL and title metadata.
        </p>
      )}
    </li>
  );
}

function AllLinksPanel({
  data,
  cardSources,
}: {
  data: CompanyEvidence;
  cardSources: SourceRow[];
}) {
  const links = useMemo(() => {
    const seen = new Set<string>();
    const out: { url: string; title?: string | null; source: string }[] = [];

    const add = (url: string, title: string | null | undefined, source: string) => {
      const norm = url.trim().toLowerCase();
      if (!norm.startsWith("http") || seen.has(norm)) return;
      seen.add(norm);
      out.push({ url, title, source });
    };

    for (const o of data.diffbot?.origins ?? []) add(o, null, "Diffbot");
    for (const l of data.diffbot?.links ?? []) add(l.url, l.label, "Diffbot");
    for (const s of data.parallel?.brief.sources ?? []) add(s.url, s.title, "Parallel");
    for (const p of data.exa.pages) add(p.url, p.title, "Exa");
    for (const s of cardSources) add(s.url, s.title, "Card");

    return out;
  }, [data, cardSources]);

  if (links.length === 0) {
    return (
      <EmptyState
        icon={Link2}
        title="No links collected"
        description="URLs from engines and the card will appear here after a research run."
      />
    );
  }

  const bySource = links.reduce<Record<string, typeof links>>((acc, l) => {
    (acc[l.source] ??= []).push(l);
    return acc;
  }, {});

  return (
    <div className="space-y-5">
      <p className="text-xs text-muted">
        {links.length} unique URLs deduplicated across Diffbot, Parallel, Exa, and
        the synthesized card.
      </p>
      {Object.entries(bySource).map(([source, items]) => (
        <section key={source}>
          <SectionLabel>
            {source} ({items.length})
          </SectionLabel>
          <ul className="divide-y divide-border/60 rounded-lg border border-border">
            {items.map((l) => (
              <li key={l.url} className="px-3 py-2.5">
                <ExternalAnchor href={l.url} label={l.title ?? shortUrl(l.url)} />
                <div className="truncate font-mono text-[10px] text-soft">{l.url}</div>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function ParallelSignalRow({ signal }: { signal: ParallelSignal }) {
  return (
    <li className="rounded-lg border border-border bg-white px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        {signal.type && (
          <span className="rounded-md bg-tint px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted">
            {signal.type}
          </span>
        )}
        {signal.date && (
          <span className="text-[10px] text-soft">{signal.date}</span>
        )}
        {signal.weight != null && (
          <span className="text-[10px] tabular-nums text-soft">
            weight {signal.weight}/10
          </span>
        )}
      </div>
      <div className="mt-1.5 text-sm font-medium text-ink">{signal.headline}</div>
      {signal.evidence && (
        <p className="mt-1 text-xs leading-relaxed text-muted">{signal.evidence}</p>
      )}
    </li>
  );
}

function PersonCard({
  person,
  badge,
}: {
  person: { name: string; title?: string; linkedInUri?: string };
  badge: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-tint/20 px-3 py-2.5">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-soft">
          {badge}
        </span>
      </div>
      <div className="mt-1 text-sm font-medium text-ink">{person.name}</div>
      {person.title && (
        <div className="text-xs text-muted">{person.title}</div>
      )}
      {person.linkedInUri && (
        <div className="mt-1">
          <ExternalAnchor href={person.linkedInUri} label="LinkedIn" />
        </div>
      )}
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-soft">
      {children}
    </h3>
  );
}

function FieldGrid({
  fields,
  columns = 2,
}: {
  fields: [string, unknown][];
  columns?: 2 | 3;
}) {
  const visible = fields.filter(([, v]) => v != null && v !== "");
  if (visible.length === 0) return null;
  return (
    <section>
      <dl
        className={cn(
          "grid gap-3",
          columns === 3 ? "sm:grid-cols-2 lg:grid-cols-3" : "sm:grid-cols-2",
        )}
      >
        {visible.map(([k, v]) => (
          <div key={k}>
            <dt className="text-[10px] font-medium uppercase tracking-[0.08em] text-soft">
              {k}
            </dt>
            <dd className="mt-0.5 text-sm font-medium text-ink">{String(v)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function TagList({ label, items }: { label: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <section>
      <SectionLabel>{label}</SectionLabel>
      <div className="flex flex-wrap gap-1.5">
        {items.map((t) => (
          <span
            key={t}
            className="rounded-md border border-border bg-white px-2 py-1 text-xs text-ink"
          >
            {t}
          </span>
        ))}
      </div>
    </section>
  );
}

function ExternalAnchor({
  href,
  label,
  mono,
  className,
}: {
  href: string;
  label: string;
  mono?: boolean;
  className?: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={cn(
        "inline-flex items-center gap-1 text-accent hover:underline",
        mono && "font-mono text-[11px]",
        className,
      )}
    >
      {label}
      <ExternalLink className="h-3 w-3 shrink-0 opacity-60" />
    </a>
  );
}

function shortUrl(url: string): string {
  try {
    const u = new URL(url);
    return u.hostname + u.pathname.slice(0, 40) + (u.pathname.length > 40 ? "…" : "");
  } catch {
    return url.slice(0, 48);
  }
}

function fmtMoney(v: unknown): string | null {
  if (v == null || v === "") return null;
  const n = typeof v === "number" ? v : Number(String(v).replace(/[^0-9.-]/g, ""));
  if (Number.isFinite(n)) {
    if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
    return `$${n.toLocaleString()}`;
  }
  return String(v);
}
