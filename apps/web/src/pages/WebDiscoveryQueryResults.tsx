import { useMemo, useState, type ComponentType, type ReactNode } from "react";
import {
  ArrowLeft,
  Calendar,
  ChevronDown,
  Copy,
  ExternalLink,
  FileText,
  Globe2,
  Highlighter,
  LayoutList,
  Search,
  Sparkles,
  User,
} from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { Topbar } from "@/components/layout/Topbar";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { PageBody } from "@/components/ui/PageBody";
import {
  getWebDiscoveryCluster,
  getWebDiscoveryQuery,
  getWebDiscoveryQueryResults,
  listWebDiscoveryClusterRuns,
  type WebDiscoveryQueryResultsPayload,
  type WebDiscoveryResultItem,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type SortKey = "rank" | "score" | "date";
type ContentSection = "summary" | "excerpts" | "page";

export default function WebDiscoveryQueryResults() {
  const { clusterId = "", queryId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const runId = searchParams.get("run") ?? undefined;
  const navigate = useNavigate();

  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState<SortKey>("rank");
  const [expandAll, setExpandAll] = useState(false);
  const [openSections, setOpenSections] = useState<Record<string, ContentSection[]>>({});
  const [confirmRunAgain, setConfirmRunAgain] = useState(false);

  const clusterQuery = useQuery({
    queryKey: ["web-discovery-cluster", clusterId],
    queryFn: () => getWebDiscoveryCluster(clusterId),
    enabled: !!clusterId,
  });
  const queryDetail = useQuery({
    queryKey: ["web-discovery-query", queryId],
    queryFn: () => getWebDiscoveryQuery(queryId),
    enabled: !!queryId,
  });
  const runsQuery = useQuery({
    queryKey: ["web-discovery-runs", clusterId],
    queryFn: () => listWebDiscoveryClusterRuns(clusterId, 15),
    enabled: !!clusterId,
  });
  const resultsQuery = useQuery({
    queryKey: ["web-discovery-query-results", queryId, runId],
    queryFn: () => getWebDiscoveryQueryResults(queryId, runId),
    enabled: !!queryId,
    retry: 1,
  });

  const payload = resultsQuery.data;
  const label = payload?.query_label ?? queryDetail.data?.label ?? "Query";
  const searchQuery = payload?.search_query ?? queryDetail.data?.search_query ?? "";

  const processedResults = useMemo(() => {
    const rows = payload?.results ?? [];
    const q = filter.trim().toLowerCase();
    let list = q
      ? rows.filter((item) => {
          const hay = [
            item.title,
            item.url,
            item.summary,
            item.snippet,
            item.author,
            ...(item.highlights ?? []),
          ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();
          return hay.includes(q);
        })
      : [...rows];

    if (sort === "score") {
      list = [...list].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
    } else if (sort === "date") {
      list = [...list].sort((a, b) => {
        const ta = a.published_date ? Date.parse(a.published_date) : 0;
        const tb = b.published_date ? Date.parse(b.published_date) : 0;
        return tb - ta;
      });
    }
    return list;
  }, [payload?.results, filter, sort]);

  const contentModes = payload?.content_modes ?? [];
  const statusTone =
    payload?.status === "ok" || payload?.status === "completed" ? "success" : "error";

  const toggleSection = (url: string, section: ContentSection) => {
    setOpenSections((prev) => {
      const current =
        prev[url] ??
        defaultSectionsForItem(processedResults.find((r) => r.url === url));
      const has = current.includes(section);
      const next = has ? current.filter((s) => s !== section) : [...current, section];
      return { ...prev, [url]: next };
    });
  };

  const sectionsFor = (item: WebDiscoveryResultItem) => {
    if (expandAll) {
      const all: ContentSection[] = [];
      if (item.summary) all.push("summary");
      if (curateInsights(item).featured.length > 0) all.push("excerpts");
      if (item.text || item.snippet) all.push("page");
      return all.length > 0 ? all : (["excerpts"] as ContentSection[]);
    }
    return (
      openSections[item.url] ??
      defaultSectionsForItem(item)
    );
  };

  return (
    <>
      <Topbar
        title="Discovery Results"
        subtitle="Every Exa field for this run — summaries, excerpts, and source pages."
      />
      <PageBody>
        <nav className="mb-4 flex flex-wrap items-center gap-2 text-sm text-muted">
          <Link to="/discover-web" className="hover:text-ink">
            Clusters
          </Link>
          <span>›</span>
          <Link to={`/discover-web/clusters/${clusterId}`} className="hover:text-ink">
            {clusterQuery.data?.name ?? "Cluster"}
          </Link>
          <span>›</span>
          <Link
            to={`/discover-web/clusters/${clusterId}/queries/${queryId}`}
            className="hover:text-ink"
          >
            {label}
          </Link>
          <span>›</span>
          <span className="font-medium text-ink">Results</span>
        </nav>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
          <div className="min-w-0 space-y-5">
            <header className="rounded-2xl border border-border bg-gradient-to-br from-white via-white to-[#F5F2EC] p-5 shadow-soft sm:p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#5E8E4A]">
                    Exa discovery
                  </p>
                  <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink">
                    {label}
                  </h1>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{searchQuery}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {payload?.search_type ? (
                      <Chip>{payload.search_type}</Chip>
                    ) : null}
                    {payload?.num_results != null ? (
                      <Chip>{payload.num_results} requested</Chip>
                    ) : null}
                    {contentModes.map((mode) => (
                      <Chip key={mode}>{mode}</Chip>
                    ))}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    onClick={() =>
                      navigate(`/discover-web/clusters/${clusterId}/queries/${queryId}`)
                    }
                  >
                    <ArrowLeft className="h-4 w-4" />
                    Edit query
                  </Button>
                  <Button onClick={() => setConfirmRunAgain(true)}>
                    <Sparkles className="h-4 w-4" />
                    Run again
                  </Button>
                </div>
              </div>

              {payload ? (
                <div className="mt-5 grid gap-3 sm:grid-cols-3">
                  <MetricCard
                    label="Sources"
                    value={String(payload.result_count)}
                    sub="from this run"
                  />
                  <MetricCard
                    label="Status"
                    value={payload.status}
                    tone={statusTone}
                  />
                  <MetricCard
                    label="Duration"
                    value={formatLatency(payload.latency_ms)}
                    sub="end-to-end"
                  />
                </div>
              ) : null}
            </header>

            <div className="flex flex-col gap-3 rounded-xl border border-border bg-white p-3 shadow-soft sm:flex-row sm:items-center sm:justify-between">
              <div className="relative min-w-0 flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-soft" />
                <input
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                  placeholder="Filter sources by title, URL, summary, or excerpt…"
                  className="h-10 w-full rounded-lg border border-border bg-[#FCFCFB] pl-9 pr-3 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
                />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value as SortKey)}
                  className="h-10 rounded-lg border border-border bg-white px-3 text-sm outline-none focus:border-accent"
                >
                  <option value="rank">Exa rank</option>
                  <option value="score">Relevance score</option>
                  <option value="date">Published date</option>
                </select>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setExpandAll((v) => !v)}
                >
                  <LayoutList className="h-4 w-4" />
                  {expandAll ? "Collapse all" : "Expand all"}
                </Button>
              </div>
            </div>

            {resultsQuery.isLoading ? (
              <ResultsSkeleton />
            ) : resultsQuery.isError ? (
              <EmptyState
                title="No stored results yet"
                body="Run this query again to capture full Exa payloads (summary, highlights, and page text)."
                actionLabel="Run query"
                onAction={() =>
                  navigate(`/discover-web/clusters/${clusterId}/queries/${queryId}`)
                }
              />
            ) : processedResults.length === 0 ? (
              <EmptyState
                title={filter ? "No sources match your filter" : "No sources returned"}
                body={
                  filter
                    ? "Try a different keyword or clear the filter."
                    : "Broaden the query or adjust Exa filters, then run again."
                }
                actionLabel={filter ? "Clear filter" : "Edit query"}
                onAction={() => (filter ? setFilter("") : navigate(
                  `/discover-web/clusters/${clusterId}/queries/${queryId}`,
                ))}
              />
            ) : (
              <div className="space-y-4">
                <p className="text-xs text-soft">
                  Showing {processedResults.length} of {payload?.results.length ?? 0} sources
                  {filter ? ` matching “${filter}”` : ""}
                </p>
                {processedResults.map((item, index) => (
                  <SourceCard
                    key={`${item.url}-${index}`}
                    item={item}
                    rank={sort === "rank" ? index + 1 : undefined}
                    openSections={sectionsFor(item)}
                    onToggleSection={(section) => toggleSection(item.url, section)}
                  />
                ))}
              </div>
            )}
          </div>

          <aside className="space-y-3 xl:sticky xl:top-4 xl:self-start">
            <RunIntelPanel payload={payload} runs={runsQuery.data} runId={runId} />
            <div className="rounded-xl border border-border bg-[#FCFCFB] p-4 text-xs leading-relaxed text-muted">
              <p className="font-semibold text-ink">Reading guide</p>
              <ul className="mt-2 list-inside list-disc space-y-1.5">
                <li>
                  <span className="font-medium text-ink">Summary</span> — Exa-generated
                  abstract when enabled.
                </li>
                <li>
                  <span className="font-medium text-ink">Insights</span> — curated,
                  query-relevant passages (UI noise filtered out).
                </li>
                <li>
                  <span className="font-medium text-ink">Page</span> — crawled body text
                  when full-text mode is on.
                </li>
              </ul>
            </div>
          </aside>
        </div>

        {payload?.error ? (
          <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {payload.error}
          </p>
        ) : null}
      </PageBody>

      <ConfirmDialog
        open={confirmRunAgain}
        onOpenChange={setConfirmRunAgain}
        title="Run this query again?"
        description="Starts a fresh Exa search. You will land back here when it completes."
        confirmText="Run again"
        onConfirm={() => {
          setConfirmRunAgain(false);
          navigate(`/discover-web/clusters/${clusterId}/queries/${queryId}`);
        }}
      />
    </>
  );
}

function SourceCard({
  item,
  rank,
  openSections,
  onToggleSection,
}: {
  item: WebDiscoveryResultItem;
  rank?: number;
  openSections: ContentSection[];
  onToggleSection: (section: ContentSection) => void;
}) {
  const host = hostFromUrl(item.url);
  const published = formatDate(item.published_date);
  const insights = useMemo(() => curateInsights(item), [item]);
  const [showAllInsights, setShowAllInsights] = useState(false);
  const visibleInsights = showAllInsights
    ? [...insights.featured, ...insights.overflow]
    : insights.featured;
  const hasSummary = Boolean(item.summary?.trim());
  const hasExcerpts = insights.featured.length > 0;
  const hasPage = Boolean(item.text?.trim() || item.snippet?.trim());
  const scorePct =
    item.score != null ? Math.min(100, Math.max(0, Math.round(item.score * 100))) : null;

  return (
    <article className="overflow-hidden rounded-2xl border border-border bg-white shadow-soft transition hover:border-accent/25">
      {item.image ? (
        <div className="relative h-36 w-full overflow-hidden border-b border-border bg-[#F4F1EA] sm:h-44">
          <img
            src={item.image}
            alt=""
            className="h-full w-full object-cover"
            onError={(e) => {
              (e.target as HTMLImageElement).parentElement!.style.display = "none";
            }}
          />
        </div>
      ) : null}

      <div className="p-4 sm:p-5">
        <div className="flex gap-3">
          {rank != null ? (
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#E8F5E9] to-[#D4EBD8] text-sm font-bold text-[#2D6A3E]">
              {rank}
            </div>
          ) : null}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-start gap-3">
              <SourceAvatar favicon={item.favicon} image={item.image} />
              <div className="min-w-0 flex-1">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group inline text-lg font-semibold leading-snug text-ink hover:text-accent"
                >
                  {item.title || host}
                  <ExternalLink className="ml-1.5 inline h-4 w-4 opacity-50 group-hover:opacity-100" />
                </a>
                <p className="mt-0.5 text-xs text-soft">{host}</p>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              {published ? (
                <MetaPill icon={Calendar}>{published}</MetaPill>
              ) : null}
              {item.author ? <MetaPill icon={User}>{item.author}</MetaPill> : null}
              {scorePct != null ? (
                <span className="inline-flex items-center gap-2 rounded-full border border-[#BDE6D3] bg-[#ECF8F1] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-[#155A3E]">
                  Relevance
                  <span className="inline-block h-1.5 w-16 overflow-hidden rounded-full bg-white/80">
                    <span
                      className="block h-full rounded-full bg-[#2D9B5E]"
                      style={{ width: `${scorePct}%` }}
                    />
                  </span>
                  {item.score!.toFixed(2)}
                </span>
              ) : null}
            </div>

            <div className="mt-4 flex flex-wrap gap-2 border-b border-border/80 pb-3">
              {hasSummary ? (
                <SectionTab
                  active={openSections.includes("summary")}
                  onClick={() => onToggleSection("summary")}
                  icon={Sparkles}
                  label="Summary"
                />
              ) : null}
              {hasExcerpts ? (
                <SectionTab
                  active={openSections.includes("excerpts")}
                  onClick={() => onToggleSection("excerpts")}
                  icon={Highlighter}
                  label={`Insights (${insights.featured.length})`}
                />
              ) : null}
              {hasPage ? (
                <SectionTab
                  active={openSections.includes("page")}
                  onClick={() => onToggleSection("page")}
                  icon={FileText}
                  label="Page"
                />
              ) : null}
            </div>

            {openSections.includes("summary") && hasSummary ? (
              <div className="mt-4 rounded-xl border border-[#D4E8D0] bg-gradient-to-b from-[#F3FBF5] to-white px-4 py-3.5">
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#3D7A4E]">
                  Exa summary
                </p>
                <p className="mt-2 text-sm leading-[1.65] text-ink">{item.summary}</p>
              </div>
            ) : null}

            {openSections.includes("excerpts") && hasExcerpts ? (
              <div className="mt-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-soft">
                    Key insights
                  </p>
                  {insights.rawCount > insights.featured.length ? (
                    <p className="text-[11px] text-soft">
                      Top {insights.featured.length} of {insights.rawCount} passages
                    </p>
                  ) : null}
                </div>
                <ul className="mt-3 space-y-3">
                  {visibleInsights.map((excerpt, i) => (
                    <li
                      key={`${i}-${excerpt.slice(0, 24)}`}
                      className="relative rounded-xl border border-[#E8E4DC]/90 bg-gradient-to-r from-[#FFFCF8] to-white py-3.5 pl-5 pr-4 shadow-[inset_3px_0_0_0_rgba(200,120,60,0.55)]"
                    >
                      <p className="text-sm leading-[1.7] text-ink">
                        {formatExcerptText(excerpt)}
                      </p>
                    </li>
                  ))}
                </ul>
                {insights.overflow.length > 0 ? (
                  <button
                    type="button"
                    onClick={() => setShowAllInsights((v) => !v)}
                    className="mt-3 text-xs font-medium text-accent hover:underline"
                  >
                    {showAllInsights
                      ? "Show fewer passages"
                      : `Show ${insights.overflow.length} more passages`}
                  </button>
                ) : null}
              </div>
            ) : null}

            {openSections.includes("page") && hasPage ? (
              <div className="mt-4">
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-soft">
                  Page content
                </p>
                {item.snippet && item.snippet !== item.text ? (
                  <p className="mt-2 text-sm leading-relaxed text-muted">{item.snippet}</p>
                ) : null}
                {item.text ? (
                  <div className="mt-2 max-h-80 overflow-y-auto rounded-lg border border-border bg-[#FAFAF8] p-3">
                    <pre className="whitespace-pre-wrap font-sans text-xs leading-relaxed text-muted">
                      {item.text}
                    </pre>
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border/60 pt-3">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => window.open(item.url, "_blank", "noopener,noreferrer")}
              >
                <ExternalLink className="h-3.5 w-3.5" />
                Open source
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => copyText(item.url, "Link copied")}
              >
                <Copy className="h-3.5 w-3.5" />
                Copy URL
              </Button>
              {item.summary ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => copyText(item.summary!, "Summary copied")}
                >
                  <Copy className="h-3.5 w-3.5" />
                  Copy summary
                </Button>
              ) : null}
              <span className="min-w-0 flex-1 truncate text-[11px] text-soft" title={item.url}>
                {item.url}
              </span>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}

function RunIntelPanel({
  payload,
  runs,
  runId,
}: {
  payload: WebDiscoveryQueryResultsPayload | undefined;
  runs: { id: string; created_at: string; status: string }[] | undefined;
  runId: string | undefined;
}) {
  const navigate = useNavigate();
  const { clusterId = "", queryId = "" } = useParams();
  const [, setSearchParams] = useSearchParams();

  return (
    <div className="rounded-xl border border-border bg-white p-4 shadow-soft">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-soft">
        Run snapshot
      </p>
      {payload?.completed_at ? (
        <p className="mt-2 text-sm font-medium text-ink">
          {new Date(payload.completed_at).toLocaleString()}
        </p>
      ) : (
        <p className="mt-2 text-sm text-soft">—</p>
      )}
      {payload?.run_id ? (
        <p className="mt-1 font-mono text-[10px] text-soft">ID {payload.run_id.slice(0, 8)}…</p>
      ) : null}

      {runs && runs.length > 1 ? (
        <div className="mt-4">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-soft">
            Other runs
          </label>
          <select
            className="mt-1 h-9 w-full rounded-lg border border-border bg-[#FCFCFB] px-2 text-xs"
            value={runId ?? payload?.run_id ?? ""}
            onChange={(e) => {
              const id = e.target.value;
              if (id) setSearchParams({ run: id });
            }}
          >
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                {run.status} · {new Date(run.created_at).toLocaleString()}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      <Button
        className="mt-4 w-full"
        variant="secondary"
        size="sm"
        onClick={() =>
          navigate(`/discover-web/clusters/${clusterId}/queries/${queryId}`)
        }
      >
        Edit query settings
      </Button>
    </div>
  );
}

function SectionTab({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: ComponentType<{ className?: string }>;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition",
        active
          ? "border-accent/40 bg-accent/10 text-accent"
          : "border-border bg-white text-muted hover:text-ink",
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
      <ChevronDown
        className={cn("h-3 w-3 transition", active && "rotate-180")}
      />
    </button>
  );
}

function SourceAvatar({
  favicon,
  image,
}: {
  favicon: string | null;
  image: string | null;
}) {
  const src = favicon || image;
  if (src) {
    return (
      <img
        src={src}
        alt=""
        className="h-10 w-10 shrink-0 rounded-xl border border-border bg-white object-cover"
        onError={(e) => {
          (e.target as HTMLImageElement).style.display = "none";
        }}
      />
    );
  }
  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-[#FCFCFB]">
      <Globe2 className="h-5 w-5 text-soft" />
    </div>
  );
}

function MetaPill({
  icon: Icon,
  children,
}: {
  icon: ComponentType<{ className?: string }>;
  children: ReactNode;
}) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-border bg-[#FCFCFB] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-soft">
      <Icon className="h-3 w-3" />
      {children}
    </span>
  );
}

function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full border border-border bg-white px-2.5 py-0.5 text-[11px] font-medium text-muted">
      {children}
    </span>
  );
}

function MetricCard({
  label,
  value,
  sub,
  tone = "neutral",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "neutral" | "success" | "error";
}) {
  return (
    <div className="rounded-xl border border-border bg-white/90 px-3 py-2.5 shadow-soft">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-soft">
        {label}
      </p>
      <p
        className={cn(
          "mt-1 text-xl font-semibold capitalize",
          tone === "success" && "text-[#155A3E]",
          tone === "error" && "text-red-700",
          tone === "neutral" && "text-ink",
        )}
      >
        {value}
      </p>
      {sub ? <p className="text-[11px] text-soft">{sub}</p> : null}
    </div>
  );
}

function ResultsSkeleton() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 3 }).map((_, i) => (
        <div
          key={i}
          className="h-48 animate-pulse rounded-2xl border border-border bg-white"
        />
      ))}
    </div>
  );
}

function EmptyState({
  title,
  body,
  actionLabel,
  onAction,
}: {
  title: string;
  body: string;
  actionLabel: string;
  onAction: () => void;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-[#FCFCFB] px-6 py-14 text-center">
      <p className="text-base font-semibold text-ink">{title}</p>
      <p className="mx-auto mt-2 max-w-md text-sm text-soft">{body}</p>
      <Button className="mt-5" onClick={onAction}>
        {actionLabel}
      </Button>
    </div>
  );
}

function defaultSectionsForItem(item: WebDiscoveryResultItem | undefined): ContentSection[] {
  if (!item) return ["summary"];
  const sections: ContentSection[] = [];
  if (item.summary?.trim()) sections.push("summary");
  if (curateInsights(item).featured.length > 0) sections.push("excerpts");
  else if (item.snippet?.trim() || item.text?.trim()) sections.push("page");
  if (!sections.length) sections.push("summary");
  return sections;
}

const NOISE_EXCERPT =
  /^(slide\s*\d+|\d+\s*of\s*\d+|\(\d+[\s,]*reviews?\)|free\s+shipping|add\s+to\s+cart|shop\s+now|skip\s+to|read\s+more|subscribe|sign\s+up|cookie|menu|home|search|cart|checkout|work\s+better\.?|play\s+better\.?|think\s+better\.?|feel\s+better\.?)$/i;

type CuratedInsights = {
  featured: string[];
  overflow: string[];
  rawCount: number;
};

const FEATURED_INSIGHT_LIMIT = 6;
const OVERFLOW_INSIGHT_LIMIT = 12;

function curateInsights(item: WebDiscoveryResultItem): CuratedInsights {
  const titleNorm = normalizeExcerptKey(item.title ?? "");
  const candidates = collectExcerptCandidates(item);
  const filtered = candidates.filter((text) => {
    const norm = normalizeExcerptKey(text);
    if (!norm || norm.length < 12) return false;
    if (NOISE_EXCERPT.test(norm)) return false;
    if (titleNorm && (norm === titleNorm || norm.includes(titleNorm) && norm.length < titleNorm.length + 20)) {
      return false;
    }
    if (norm.split(/\s+/).length < 4 && !/[★"“]/.test(text)) return false;
    return true;
  });

  const unique = dedupeExcerpts(filtered);
  const ranked = unique
    .map((text) => ({ text, score: scoreExcerpt(text) }))
    .sort((a, b) => b.score - a.score);

  const featured = ranked
    .slice(0, FEATURED_INSIGHT_LIMIT)
    .map((row) => row.text);
  const overflow = ranked
    .slice(FEATURED_INSIGHT_LIMIT, FEATURED_INSIGHT_LIMIT + OVERFLOW_INSIGHT_LIMIT)
    .map((row) => row.text);

  return {
    featured,
    overflow,
    rawCount: candidates.length,
  };
}

function collectExcerptCandidates(item: WebDiscoveryResultItem): string[] {
  const out: string[] = [];
  const highlights = item.highlights?.filter((h) => h?.trim()) ?? [];

  if (highlights.length > 0) {
    for (const chunk of highlights) {
      out.push(...splitLongPassage(chunk.trim()));
    }
    return out;
  }

  if (item.snippet?.trim()) {
    out.push(...splitLongPassage(item.snippet.trim()));
  }
  return out;
}

/** Only split very long passages by paragraph — never sentence-chop UI crumbs. */
function splitLongPassage(text: string): string[] {
  const trimmed = text.trim();
  if (trimmed.length <= 700) return [trimmed];
  const paras = trimmed.split(/\n\n+/).map((p) => p.trim()).filter(Boolean);
  return paras.length > 1 ? paras : [trimmed];
}

function normalizeExcerptKey(text: string): string {
  return text.toLowerCase().replace(/\s+/g, " ").replace(/[^\w\s★"'“”.,!?-]/g, "").trim();
}

function dedupeExcerpts(items: string[]): string[] {
  const out: string[] = [];
  const norms: string[] = [];
  for (const text of items) {
    const norm = normalizeExcerptKey(text);
    if (!norm) continue;
    const dup = norms.some(
      (existing) => existing === norm || existing.includes(norm) || norm.includes(existing),
    );
    if (dup) continue;
    norms.push(norm);
    out.push(text.trim());
  }
  return out;
}

function scoreExcerpt(text: string): number {
  const words = text.split(/\s+/).filter(Boolean).length;
  let score = 0;
  if (words >= 18) score += 5;
  else if (words >= 10) score += 3;
  else if (words >= 6) score += 1;
  else score -= 4;

  if (text.length >= 90) score += 2;
  if (/★|review|rating|customer|launch|announced|report|study|ingredient|nicotine|cognitive/i.test(text)) {
    score += 3;
  }
  if (/[.!?]["']?\s*$/.test(text.trim())) score += 1;
  if (NOISE_EXCERPT.test(normalizeExcerptKey(text))) score -= 10;
  if (words <= 3) score -= 6;
  return score;
}

function formatExcerptText(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

function hostFromUrl(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function formatDate(value: string | null): string | null {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatLatency(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms)}ms`;
}

async function copyText(text: string, message: string) {
  try {
    await navigator.clipboard.writeText(text);
    toast.success(message);
  } catch {
    toast.error("Could not copy to clipboard");
  }
}
