import { useEffect, useMemo, useState, type ComponentType, type ReactNode } from "react";
import {
  ArrowLeft,
  Building2,
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
  getArticle,
  getWebDiscoveryCluster,
  getWebDiscoveryQuery,
  getWebDiscoveryQueryResults,
  getWebDiscoveryRun,
  listWebDiscoveryClusterRuns,
  startResearchRun,
  type MentionedCompany,
  type WebDiscoveryQueryRun,
  type WebDiscoveryRun,
  type WebDiscoveryQueryResultsPayload,
  type WebDiscoveryResultItem,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type SortKey = "rank" | "score" | "date";

export default function WebDiscoveryQueryResults() {
  const { clusterId = "", queryId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const runId = searchParams.get("run") ?? undefined;
  const navigate = useNavigate();

  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState<SortKey>("rank");
  const [expandAll, setExpandAll] = useState(false);
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
  const clusterRunsQuery = useQuery({
    queryKey: ["web-discovery-runs", clusterId],
    queryFn: () => listWebDiscoveryClusterRuns(clusterId, 30),
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

  const runOptions = useMemo((): WebDiscoveryQueryRun[] => {
    if (payload?.available_runs?.length) {
      return payload.available_runs;
    }
    if (clusterRunsQuery.data?.length && queryId) {
      return buildQueryRunOptionsFromClusterRuns(
        clusterRunsQuery.data,
        queryId,
        label,
      );
    }
    return [];
  }, [payload?.available_runs, clusterRunsQuery.data, queryId, label]);

  const processedResults = useMemo(() => {
    const rows = payload?.results ?? [];
    const q = filter.trim().toLowerCase();
    let list = q
      ? rows.filter((item) => {
          const hay = [
            item.title,
            item.url,
            item.summary,
            item.executive_summary,
            item.snippet,
            item.author,
            ...(item.highlights ?? []),
            ...(item.mentioned_companies ?? []).flatMap((c) => [c.name, c.context]),
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
                    expandPage={expandAll}
                  />
                ))}
              </div>
            )}
          </div>

          <aside className="space-y-3 xl:sticky xl:top-4 xl:self-start">
            <RunIntelPanel payload={payload} runs={runOptions} runId={runId} />
            <div className="rounded-xl border border-border bg-[#FCFCFB] p-4 text-xs leading-relaxed text-muted">
              <p className="font-semibold text-ink">Reading guide</p>
              <ul className="mt-2 list-inside list-disc space-y-1.5">
                <li>
                  <span className="font-medium text-ink">Executive summary</span> — NORAD
                  analysis tied to your search query.
                </li>
                <li>
                  <span className="font-medium text-ink">Companies</span> — entities
                  mentioned in this story — use Deep research for a full company profile.
                </li>
                <li>
                  <span className="font-medium text-ink">Full article</span> — original
                  crawled content from the source URL.
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
  expandPage = false,
}: {
  item: WebDiscoveryResultItem;
  rank?: number;
  expandPage?: boolean;
}) {
  const host = hostFromUrl(item.url);
  const published = formatDate(item.published_date);
  const presentation = useMemo(() => buildSourcePresentation(item), [item]);
  const [pageOpen, setPageOpen] = useState(expandPage);

  useEffect(() => {
    setPageOpen(expandPage);
  }, [expandPage]);
  const scorePct =
    item.score != null ? Math.min(100, Math.max(0, Math.round(item.score * 100))) : null;

  const hasBrief = presentation.briefParagraphs.length > 0;
  const hasQuotes = presentation.quotes.length > 0;
  const hasFaq = presentation.faqPairs.length > 0;
  const hasPage = presentation.pageParagraphs.length > 0;
  const hasNoradAnalysis = Boolean(item.executive_summary?.trim());
  const showExaExcerpts = !hasNoradAnalysis && (hasBrief || hasQuotes || hasFaq);
  const showExaPage = !hasNoradAnalysis && hasPage;

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
              {item.ingest_status === "duplicate" ? (
                <span className="inline-flex rounded-full border border-border bg-tint px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted">
                  Previously ingested
                </span>
              ) : item.enriched ? (
                <span className="inline-flex rounded-full border border-[#BDE6D3] bg-[#ECF8F1] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-[#155A3E]">
                  Analyzed
                </span>
              ) : null}
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

            {!hasNoradAnalysis && !hasBrief && !hasQuotes && !hasFaq ? (
              <div className="mt-4 rounded-lg border border-amber-200/80 bg-amber-50/60 px-3 py-2.5 text-xs text-amber-900">
                Limited content for this URL. Enable{" "}
                <span className="font-semibold">Highlights</span> or{" "}
                <span className="font-semibold">Full text</span> on the query, then run
                again.
              </div>
            ) : null}

            {item.executive_summary ? (
              <section className="mt-5 rounded-2xl border border-[#D4E8D0]/80 bg-gradient-to-b from-[#F6FBF7] to-white px-4 py-4 sm:px-5">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-[#3D7A4E]" />
                  <h3 className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#3D7A4E]">
                    Executive summary
                  </h3>
                </div>
                <p className="mt-3 text-[15px] leading-[1.8] tracking-[0.01em] text-ink">
                  {item.executive_summary}
                </p>
              </section>
            ) : null}

            {item.mentioned_companies && item.mentioned_companies.length > 0 ? (
              <CompaniesSection companies={item.mentioned_companies} />
            ) : null}

            {hasBrief && showExaExcerpts ? (
              <section className="mt-5 rounded-2xl border border-border/80 bg-[#FAFAF8] px-4 py-4 sm:px-5">
                <div className="flex items-center gap-2">
                  <Highlighter className="h-4 w-4 text-soft" />
                  <h3 className="text-[11px] font-bold uppercase tracking-[0.14em] text-soft">
                    Source excerpts (Exa)
                  </h3>
                </div>
                <div className="mt-3 max-w-none space-y-3.5">
                  {presentation.briefParagraphs.map((paragraph, i) => (
                    <p
                      key={i}
                      className="text-[15px] leading-[1.8] tracking-[0.01em] text-ink"
                    >
                      {paragraph}
                    </p>
                  ))}
                </div>
              </section>
            ) : null}

            {hasQuotes && showExaExcerpts ? (
              <section className="mt-5">
                <div className="mb-3 flex items-center gap-2">
                  <Highlighter className="h-4 w-4 text-soft" />
                  <h3 className="text-[11px] font-bold uppercase tracking-[0.14em] text-soft">
                    Supporting evidence
                  </h3>
                </div>
                <div className="space-y-4">
                  {presentation.quotes.map((quote, i) => (
                    <figure
                      key={i}
                      className="rounded-xl border border-[#E8E4DC]/90 bg-[#FDFCFA] px-5 py-4"
                    >
                      <blockquote className="border-l-[3px] border-accent/60 pl-4 text-[15px] leading-[1.75] text-ink">
                        {quote}
                      </blockquote>
                    </figure>
                  ))}
                </div>
              </section>
            ) : null}

            {hasFaq && showExaExcerpts ? (
              <section className="mt-5">
                <h3 className="text-[11px] font-bold uppercase tracking-[0.14em] text-soft">
                  Key Q&amp;A from page
                </h3>
                <dl className="mt-3 space-y-3">
                  {presentation.faqPairs.map((pair, i) => (
                    <div
                      key={i}
                      className="rounded-xl border border-border/80 bg-white px-4 py-3"
                    >
                      <dt className="text-sm font-semibold text-ink">{pair.question}</dt>
                      <dd className="mt-1.5 text-sm leading-relaxed text-muted">
                        {pair.answer}
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            ) : null}

            {showExaPage ? (
              <details
                className="mt-5 group rounded-xl border border-border/80 bg-[#FAFAF8]"
                open={pageOpen}
                onToggle={(e) => setPageOpen((e.target as HTMLDetailsElement).open)}
              >
                <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3 text-sm font-medium text-ink [&::-webkit-details-marker]:hidden">
                  <span className="inline-flex items-center gap-2">
                    <FileText className="h-4 w-4 text-soft" />
                    Full page text (Exa)
                    <span className="text-xs font-normal text-soft">
                      ({presentation.pageParagraphs.length} paragraphs)
                    </span>
                  </span>
                  <ChevronDown className="h-4 w-4 text-soft transition group-open:rotate-180" />
                </summary>
                <div className="max-h-[28rem] overflow-y-auto border-t border-border/60 px-4 py-4 sm:px-5">
                  <div className="space-y-3.5">
                    {presentation.pageParagraphs.map((paragraph, i) => (
                      <p
                        key={i}
                        className="text-sm leading-[1.75] text-muted"
                      >
                        {paragraph}
                      </p>
                    ))}
                  </div>
                </div>
              </details>
            ) : null}

            <ArticleBodySection item={item} expandDefault={expandPage} />

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
              {item.executive_summary ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => copyText(item.executive_summary!, "Summary copied")}
                >
                  <Copy className="h-3.5 w-3.5" />
                  Copy summary
                </Button>
              ) : item.summary ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => copyText(item.summary!, "Summary copied")}
                >
                  <Copy className="h-3.5 w-3.5" />
                  Copy Exa summary
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

function CompaniesSection({ companies }: { companies: MentionedCompany[] }) {
  const navigate = useNavigate();
  const [profiling, setProfiling] = useState<string | null>(null);

  const onProfile = async (company: MentionedCompany) => {
    setProfiling(company.name);
    try {
      const run = await startResearchRun({
        company_name: company.name,
        domain_hint: company.hint_url ?? undefined,
        company_id: company.company_id ?? undefined,
      });
      toast.success(`Research started for ${company.name}`);
      navigate(`/runs/${run.run_id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start research");
    } finally {
      setProfiling(null);
    }
  };

  return (
    <section className="mt-5">
      <div className="mb-3 flex items-center gap-2">
        <Building2 className="h-4 w-4 text-soft" />
        <h3 className="text-[11px] font-bold uppercase tracking-[0.14em] text-soft">
          Companies in this story
        </h3>
      </div>
      <ul className="space-y-3">
        {companies.map((company) => (
          <li
            key={company.company_id ?? company.name}
            className="rounded-xl border border-border/80 bg-white px-4 py-3"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-ink">{company.name}</p>
                {company.role_in_story ? (
                  <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-wider text-soft">
                    {company.role_in_story}
                  </p>
                ) : null}
                <p className="mt-1.5 text-sm leading-relaxed text-muted">
                  {company.context}
                </p>
                {(company.industry || company.hq_or_market) && (
                  <p className="mt-1 text-xs text-soft">
                    {[company.industry, company.hq_or_market].filter(Boolean).join(" · ")}
                  </p>
                )}
              </div>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={profiling === company.name}
                onClick={() => onProfile(company)}
              >
                {profiling === company.name ? "Starting…" : "Deep research"}
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ArticleBodySection({
  item,
  expandDefault = false,
}: {
  item: WebDiscoveryResultItem;
  expandDefault?: boolean;
}) {
  const [open, setOpen] = useState(expandDefault);
  const articleQuery = useQuery({
    queryKey: ["article-body", item.article_id],
    queryFn: () => getArticle(item.article_id!),
    enabled: !!item.article_id,
  });

  const rawBody =
    (articleQuery.data?.body_text ?? "").trim() ||
    (item.text ?? "").trim() ||
    (item.highlights ?? []).join("\n\n").trim();

  const body = useMemo(() => formatArticleBody(rawBody), [rawBody]);

  useEffect(() => {
    setOpen(expandDefault);
  }, [expandDefault]);

  if (!body && !articleQuery.isLoading) return null;

  const paragraphs = body
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);

  return (
    <details
      className="mt-5 group rounded-xl border border-[#E8E4DC]/90 bg-[#FDFCFA]"
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3 text-sm font-medium text-ink [&::-webkit-details-marker]:hidden">
        <span className="inline-flex items-center gap-2">
          <FileText className="h-4 w-4 text-soft" />
          Full article
          <span className="text-xs font-normal text-soft">
            {paragraphs.length > 0
              ? `(${paragraphs.length} section${paragraphs.length === 1 ? "" : "s"})`
              : "(loading…)"}
          </span>
        </span>
        <ChevronDown className="h-4 w-4 text-soft transition group-open:rotate-180" />
      </summary>
      <div className="max-h-[32rem] overflow-y-auto border-t border-border/60 px-4 py-4 sm:px-5">
        {articleQuery.isLoading && paragraphs.length === 0 ? (
          <p className="text-sm text-soft">Loading article…</p>
        ) : (
          <div className="space-y-3.5">
            {paragraphs.map((paragraph, i) => (
              <p key={i} className="text-[15px] leading-[1.8] text-ink">
                {paragraph}
              </p>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}

/** Clean Exa highlight crumbs into readable paragraphs. */
function formatArticleBody(text: string): string {
  const raw = (text ?? "").trim();
  if (!raw) return "";

  const lines: string[] = [];
  for (const line of raw.split(/\r?\n/)) {
    const stripped = line.trim();
    if (!stripped) {
      lines.push("");
      continue;
    }
    if (/^#{1,6}\s/.test(stripped)) continue;
    if (/^[\|\-\s:]+$/.test(stripped)) continue;
    const cleaned = stripped
      .replace(/\s*\.\.\.\s*/g, " ")
      .replace(/\s{2,}/g, " ")
      .trim();
    if (cleaned.length < 3) continue;
    lines.push(cleaned);
  }

  const merged: string[] = [];
  let buf: string[] = [];
  const flush = () => {
    if (buf.length) {
      merged.push(buf.join(" "));
      buf = [];
    }
  };
  for (const line of lines) {
    if (!line) {
      flush();
      continue;
    }
    buf.push(line);
  }
  flush();

  return merged.join("\n\n");
}

function RunIntelPanel({
  payload,
  runs,
  runId,
}: {
  payload: WebDiscoveryQueryResultsPayload | undefined;
  runs: WebDiscoveryQueryRun[] | undefined;
  runId: string | undefined;
}) {
  const navigate = useNavigate();
  const { clusterId = "", queryId = "" } = useParams();
  const [, setSearchParams] = useSearchParams();

  const activeRunId = runId ?? payload?.run_id;
  const runDetailQuery = useQuery({
    queryKey: ["web-discovery-run-detail", activeRunId],
    queryFn: () => getWebDiscoveryRun(activeRunId!),
    enabled: !!activeRunId,
  });
  const runOutputs = runDetailQuery.data?.engine_outputs as
    | {
        new_articles?: number;
        enriched?: number;
        duplicates_skipped?: number;
        total_cost_usd?: number;
      }
    | undefined;

  const matchedRun = runs?.find((run) => run.id === activeRunId) ?? runs?.[0];
  const queryLabel = payload?.query_label ?? "Query";
  const currentRun: WebDiscoveryQueryRun | undefined =
    matchedRun ??
    (activeRunId && payload
      ? {
          id: activeRunId,
          display_name: `${queryLabel} · ${new Date(
            payload.completed_at ?? Date.now(),
          ).toLocaleString()}`,
          status: payload.status,
          result_count: payload.result_count,
          completed_at: payload.completed_at,
          created_at: payload.completed_at ?? new Date().toISOString(),
          run_scope: null,
        }
      : undefined);
  const when = payload?.completed_at ?? currentRun?.completed_at ?? currentRun?.created_at;

  return (
    <div className="rounded-xl border border-border bg-white p-4 shadow-soft">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-soft">
        Run snapshot
      </p>
      {currentRun ? (
        <p className="mt-2 text-base font-semibold leading-snug text-ink">
          {currentRun.display_name}
        </p>
      ) : (
        <p className="mt-2 text-sm text-soft">—</p>
      )}
      {when ? (
        <p className="mt-1 text-xs text-muted">{new Date(when).toLocaleString()}</p>
      ) : null}
      {currentRun ? (
        <p className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-soft">
          <span
            className={cn(
              "rounded-full px-2 py-0.5 font-semibold uppercase tracking-wider",
              currentRun.status === "completed"
                ? "bg-[#E8F5E9] text-[#2D6A3E]"
                : "bg-[#F4F1EA] text-muted",
            )}
          >
            {currentRun.status}
          </span>
          {currentRun.result_count > 0 ? (
            <span>{currentRun.result_count} sources</span>
          ) : null}
          {runOutputs?.new_articles != null ? (
            <span>{runOutputs.new_articles} new articles</span>
          ) : null}
          {runOutputs?.enriched != null ? (
            <span>{runOutputs.enriched} analyzed</span>
          ) : null}
          {runOutputs?.duplicates_skipped ? (
            <span>{runOutputs.duplicates_skipped} skipped (dup)</span>
          ) : null}
          {activeRunId ? (
            <span className="font-mono">ID {activeRunId.slice(0, 8)}…</span>
          ) : null}
        </p>
      ) : null}

      {runs && runs.length > 1 ? (
        <div className="mt-4">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-soft">
            Switch run
          </label>
          <select
            className="mt-1 h-10 w-full rounded-lg border border-border bg-[#FCFCFB] px-2.5 text-sm font-medium text-ink"
            value={activeRunId ?? ""}
            onChange={(e) => {
              const id = e.target.value;
              if (id) setSearchParams({ run: id });
            }}
          >
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                {run.display_name}
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

const NOISE_EXCERPT =
  /^(slide\s*\d+|\d+\s*of\s*\d+|\(\d+[\s,]*reviews?\)|free\s+shipping|add\s+to\s+cart|shop\s+now|skip\s+to|read\s+more|subscribe|sign\s+up|cookie|menu|home|search|cart|checkout|work\s+better\.?|play\s+better\.?|think\s+better\.?|feel\s+better\.?)$/i;

const MARKETING_PHRASE =
  /\b(free shipping|no questions asked|money.?back|try .{0,40} for \d+ days|return it)\b/i;

type SourcePresentation = {
  briefParagraphs: string[];
  quotes: string[];
  faqPairs: Array<{ question: string; answer: string }>;
  pageParagraphs: string[];
};

const MAX_QUOTES = 3;
const MAX_FAQ = 2;

function buildSourcePresentation(item: WebDiscoveryResultItem): SourcePresentation {
  const briefParagraphs = splitIntoParagraphs(item.summary ?? "");
  const candidates = collectExcerptCandidates(item);
  const titleNorm = normalizeExcerptKey(item.title ?? "");

  const filtered = candidates
    .map((text) => polishPassage(text))
    .filter((text) => {
      const norm = normalizeExcerptKey(text);
      if (!norm || norm.length < 20) return false;
      if (NOISE_EXCERPT.test(norm)) return false;
      if (MARKETING_PHRASE.test(norm)) return false;
      if (
        titleNorm &&
        (norm === titleNorm ||
          (norm.includes(titleNorm) && norm.length < titleNorm.length + 24))
      ) {
        return false;
      }
      return true;
    });

  const unique = dedupeExcerpts(filtered);
  const ranked = unique
    .map((text) => ({ text, score: scoreExcerpt(text) }))
    .sort((a, b) => b.score - a.score)
    .map((row) => row.text);

  const { pairs: faqPairs, rest } = extractFaqPairs(ranked);
  const quotes = rest
    .filter((text) => isCompleteThought(text))
    .slice(0, MAX_QUOTES);

  let pageParagraphs = splitIntoParagraphs(
    item.text?.trim() || (item.snippet?.trim() !== item.summary?.trim() ? item.snippet ?? "" : ""),
  );
  if (pageParagraphs.length === 0 && briefParagraphs.length === 0 && quotes.length > 0) {
    pageParagraphs = [];
  }

  if (briefParagraphs.length === 0 && quotes.length > 0) {
    return {
      briefParagraphs: quotes.slice(0, 1).map((q) => polishPassage(q)),
      quotes: quotes.slice(1, MAX_QUOTES),
      faqPairs: faqPairs.slice(0, MAX_FAQ),
      pageParagraphs,
    };
  }

  return {
    briefParagraphs,
    quotes,
    faqPairs: faqPairs.slice(0, MAX_FAQ),
    pageParagraphs,
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
  if (words >= 22) score += 6;
  else if (words >= 14) score += 4;
  else if (words >= 10) score += 2;
  else score -= 5;

  if (text.length >= 120) score += 2;
  if (/★|review|rating|customer|testimonial|launch|announced|report|study|ingredient|nicotine|cognitive|clinical/i.test(text)) {
    score += 4;
  }
  if (/[.!?]["']?\s*$/.test(text.trim())) score += 2;
  if (text.trim().endsWith("?")) score -= 2;
  if (MARKETING_PHRASE.test(text)) score -= 12;
  if (NOISE_EXCERPT.test(normalizeExcerptKey(text))) score -= 12;
  if (words <= 6) score -= 8;
  return score;
}

function isCompleteThought(text: string): boolean {
  const t = polishPassage(text);
  const words = t.split(/\s+/).filter(Boolean).length;
  if (words < 10) return false;
  if (MARKETING_PHRASE.test(t)) return false;
  if (/★/.test(t)) return true;
  if (t.endsWith("?")) return false;
  return /[.!?]["']?\s*$/.test(t);
}

function extractFaqPairs(passages: string[]): {
  pairs: Array<{ question: string; answer: string }>;
  rest: string[];
} {
  const pairs: Array<{ question: string; answer: string }> = [];
  const rest: string[] = [];
  let i = 0;
  while (i < passages.length) {
    const cur = passages[i];
    const next = passages[i + 1];
    if (
      cur.trim().endsWith("?") &&
      next &&
      !next.trim().endsWith("?") &&
      isCompleteThought(next) &&
      next.split(/\s+/).length >= 8
    ) {
      pairs.push({
        question: polishPassage(cur),
        answer: polishPassage(next),
      });
      i += 2;
    } else {
      rest.push(cur);
      i += 1;
    }
  }
  return { pairs, rest };
}

function splitIntoParagraphs(text: string): string[] {
  const cleaned = polishPassage(text);
  if (!cleaned) return [];

  const byBreak = cleaned
    .split(/\n\n+/)
    .map((p) => polishPassage(p))
    .filter((p) => p.length >= 40);
  if (byBreak.length > 0) return byBreak;

  const sentences = cleaned.match(/[^.!?]+[.!?]+(?:\s|$)/g) ?? [cleaned];
  const out: string[] = [];
  let buf = "";
  for (const sentence of sentences) {
    const next = buf + sentence;
    if (next.length > 380) {
      if (buf.trim()) out.push(polishPassage(buf));
      buf = sentence;
    } else {
      buf = next;
    }
  }
  if (buf.trim()) out.push(polishPassage(buf));
  return out.length ? out : [cleaned];
}

function polishPassage(text: string): string {
  let t = text.replace(/\s+/g, " ").trim();
  t = t.replace(/^["'“”]+|["'“”]+$/g, "").trim();
  t = t.replace(/\s+([,.;:!?])/g, "$1");
  if (t && /^[a-z]/.test(t)) {
    t = t.charAt(0).toUpperCase() + t.slice(1);
  }
  return t;
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

function querySliceFromClusterRun(
  run: WebDiscoveryRun,
  queryId: string,
): { result_count?: number } | null {
  const queries = run.engine_outputs?.queries;
  if (!Array.isArray(queries)) return null;
  const slice = queries.find(
    (item) =>
      item &&
      typeof item === "object" &&
      String((item as { query_id?: string }).query_id) === queryId,
  );
  return slice && typeof slice === "object"
    ? (slice as { result_count?: number })
    : null;
}

function buildQueryRunOptionsFromClusterRuns(
  runs: WebDiscoveryRun[],
  queryId: string,
  queryLabel: string,
): WebDiscoveryQueryRun[] {
  const chronological = [...runs].sort(
    (a, b) => Date.parse(a.created_at) - Date.parse(b.created_at),
  );
  const matched: Array<{ run: WebDiscoveryRun; slice: { result_count?: number }; n: number }> =
    [];
  let runNumber = 0;
  for (const run of chronological) {
    const slice = querySliceFromClusterRun(run, queryId);
    if (!slice) continue;
    runNumber += 1;
    matched.push({ run, slice, n: runNumber });
  }

  return [...matched].reverse().map(({ run, slice, n }) => {
    const engines = run.engines ?? {};
    const stored = engines.display_name;
    const rc = Number(slice.result_count ?? 0);
    const scope = engines.run_scope as string | undefined;
    let display_name =
      typeof stored === "string" && stored.trim()
        ? stored.trim()
        : scope === "cluster_all"
          ? `${queryLabel} · Cluster batch · ${n}`
          : `${queryLabel} · Run ${n}`;
    if (rc > 0 && !display_name.includes("sources")) {
      display_name = `${display_name} · ${rc} sources`;
    }
    return {
      id: run.id,
      display_name,
      status: run.status,
      result_count: rc,
      completed_at: run.completed_at,
      created_at: run.created_at,
      run_scope: typeof scope === "string" ? scope : null,
    };
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
