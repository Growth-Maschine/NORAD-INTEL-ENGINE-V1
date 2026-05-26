import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarRange, Compass, Loader2, Play } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { ArticleCardSkeleton } from "@/components/discover/ArticleCardSkeleton";
import { CategoryPicker } from "@/components/discover/CategoryPicker";
import { KeywordPicker } from "@/components/discover/KeywordPicker";
import { ResearchCountdown } from "@/components/discover/ResearchCountdown";
import { RunFeed } from "@/components/discover/RunFeed";
import { RunGroup, type RunGroupData } from "@/components/discover/RunGroup";
import { Topbar } from "@/components/layout/Topbar";
import { WATCHLIST } from "@/lib/watchlist";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { PageBody } from "@/components/ui/PageBody";
import { HoverTip } from "@/components/ui/Tooltip";
import {
  getRun,
  listArticles,
  listRuns,
  startDiscoveryRun,
  startResearchRun,
  type Article,
  type RunStatus,
} from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Today page — the home of the Discovery funnel.
 *
 * Layout: two-column grid on desktop. The left column is a list of
 * **discovery runs** — each one is a collapsible session showing the
 * articles that survived the funnel. The active (currently streaming) run
 * sits at the top auto-expanded; previous runs sit below in chronological
 * order so the operator can scroll back through past discovery sessions.
 *
 * The right column is the live SSE event feed.
 */
type DateRange = { from: string; to: string; label: string; hint: string };

const RANGE_PRESETS: DateRange[] = [
  { label: "3 days", hint: "3d", ...rangeFromDays(3) },
  { label: "7 days", hint: "1w", ...rangeFromDays(7) },
  { label: "1 month", hint: "30d", ...rangeFromDays(30) },
  { label: "3 months", hint: "90d", ...rangeFromDays(90) },
  { label: "6 months", hint: "6mo", ...rangeFromDays(182) },
  { label: "1 year", hint: "1y", ...rangeFromDays(365) },
  { label: "All time", hint: "∞", from: "", to: "" },
];

/**
 * Premium-feeling date field. Wraps the native date input so it sits nicely
 * inside the custom-range strip with a calendar glyph and rounded chrome,
 * without losing the browser's accessible native picker.
 */
function DateField({
  value,
  onChange,
  min,
  max,
}: {
  value: string;
  onChange: (v: string) => void;
  min?: string;
  max?: string;
}) {
  return (
    <div
      className={cn(
        "group relative inline-flex h-8 items-center rounded-md border bg-white",
        "border-border transition focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/15",
        !value && "text-soft",
      )}
    >
      <input
        type="date"
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(e.target.value)}
        className="h-full bg-transparent px-2.5 text-[12px] font-medium text-ink outline-none placeholder:text-soft"
      />
    </div>
  );
}

function rangeFromDays(days: number): { from: string; to: string } {
  const fmt = (d: Date) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  };
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - days);
  return { from: fmt(from), to: fmt(to) };
}

export default function Discover() {
  const [category, setCategory] = useState("food");
  const [keyword, setKeyword] = useState("");
  const initial = RANGE_PRESETS[2];
  const [dateFrom, setDateFrom] = useState<string>(initial.from);
  const [dateTo, setDateTo] = useState<string>(initial.to);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [confirmCancel, setConfirmCancel] = useState(false);

  // Which run groups are expanded. Active + latest run default expanded; older
  // ones collapsed. Tracked by run id (or "orphan" for the legacy bucket).
  const [expandedRuns, setExpandedRuns] = useState<Record<string, boolean>>({});

  const qc = useQueryClient();
  const navigate = useNavigate();

  // Two-stage research flow:
  //   1. Profile click → `pendingResearch` opens the confirmation modal.
  //   2. User confirms → mutation fires → on success we set `countdown` to
  //      show a 3s cancelable banner before auto-navigating to /runs/:id.
  //      The research itself is already running — the banner only gates the
  //      navigation, so cancelling keeps the user on Today.
  const [pendingResearch, setPendingResearch] = useState<{
    article: Article;
    company: string;
  } | null>(null);
  const [countdown, setCountdown] = useState<{
    runId: string;
    company: string;
  } | null>(null);

  const researchMut = useMutation({
    mutationFn: ({
      article,
      company,
    }: {
      article: Article;
      company: string;
    }) =>
      startResearchRun({
        company_name: company,
        trend_article_id: article.id,
      }),
    onSuccess: (r, vars) => {
      // The ResearchCountdown banner is the sole confirmation — skip a
      // Sonner toast here or the two stack at the bottom and overlap.
      setPendingResearch(null);
      setCountdown({ runId: r.run_id, company: vars.company });
    },
    onError: (err) => {
      toast.error("Failed to start research", {
        description: (err as Error).message,
      });
    },
  });

  const onResearch = (article: Article, company: string) => {
    if (researchMut.isPending || countdown) return;
    setPendingResearch({ article, company });
  };

  // Poll active run state while one is in flight.
  const runQuery = useQuery({
    queryKey: ["discovery-run", activeRunId],
    queryFn: () => (activeRunId ? getRun(activeRunId) : Promise.resolve(null)),
    enabled: !!activeRunId,
    refetchInterval: (q) => {
      const r = q.state.data as RunStatus | null | undefined;
      if (!r) return 3000;
      return r.status === "completed" || r.status === "failed" ? false : 2000;
    },
  });

  const runStatus = runQuery.data ?? null;
  const runActive =
    !!activeRunId &&
    (!runStatus ||
      (runStatus.status !== "completed" &&
        runStatus.status !== "failed" &&
        runStatus.status !== "cancelled"));

  // Recent discovery runs (for grouping articles into sessions).
  const runsQuery = useQuery({
    queryKey: ["discovery-runs"],
    queryFn: () => listRuns(15, "discovery"),
    refetchInterval: runActive ? 4000 : 30000,
  });

  // Articles for the current category.
  const articlesQuery = useQuery({
    queryKey: ["articles", category],
    queryFn: () =>
      listArticles({ category, status: "extracted", limit: 100 }),
    refetchInterval: runActive ? 4000 : 30000,
  });

  // After a run completes, refresh articles + toast.
  useEffect(() => {
    if (runStatus?.status === "completed") {
      qc.invalidateQueries({ queryKey: ["articles"] });
      qc.invalidateQueries({ queryKey: ["discovery-runs"] });
      toast.success("Discovery run complete", {
        description: `${runStatus.progress_pct}% — articles ready to review.`,
      });
    } else if (runStatus?.status === "failed") {
      toast.error("Discovery run failed", {
        description: runStatus.error ?? "Unknown error",
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runStatus?.status]);

  const startMut = useMutation({
    mutationFn: () =>
      startDiscoveryRun({
        category,
        keyword: keyword.trim() || null,
        date_from: dateFrom || null,
        date_to: dateTo || null,
        max_articles: 10,
      }),
    onSuccess: (r) => {
      setActiveRunId(r.run_id);
      // Auto-expand the new active run, collapse everything else so user's
      // attention is focused on what's happening now.
      setExpandedRuns({ [r.run_id]: true });
      qc.invalidateQueries({ queryKey: ["discovery-runs"] });
      toast.message("Discovery run started", {
        description: `Category: ${category}${keyword ? ` · "${keyword}"` : ""}`,
      });
    },
    onError: (err) => {
      toast.error("Failed to start run", {
        description: (err as Error).message,
      });
    },
  });

  const activePreset = RANGE_PRESETS.find(
    (p) => p.from === dateFrom && p.to === dateTo,
  )?.label;

  const articles = articlesQuery.data ?? [];
  const runs = runsQuery.data ?? [];

  // ── Group articles into runs ───────────────────────────────────────────
  const groups: RunGroupData[] = useMemo(() => {
    const runsById = new Map<string, RunStatus>(runs.map((r) => [r.id, r]));

    // Make sure the active run is represented even if listRuns hasn't caught up.
    if (runStatus && !runsById.has(runStatus.id)) {
      runsById.set(runStatus.id, runStatus);
    }

    // Bucket articles by their discovery_run_id.
    const buckets = new Map<string, Article[]>();
    for (const a of articles) {
      const k = a.discovery_run_id ?? "orphan";
      const arr = buckets.get(k);
      if (arr) arr.push(a);
      else buckets.set(k, [a]);
    }

    // Build groups. Include all known runs (even if no articles yet — the
    // active run starts empty and fills as extraction completes).
    const seen = new Set<string>();
    const out: RunGroupData[] = [];

    // First — the active run, always on top.
    if (runStatus) {
      out.push({
        key: runStatus.id,
        run: runStatus,
        articles: buckets.get(runStatus.id) ?? [],
        active: runActive,
      });
      seen.add(runStatus.id);
    }

    // Then — recent discovery runs, sorted by started_at desc.
    const sortedRuns = [...runs]
      .filter((r) => !seen.has(r.id))
      .sort((a, b) => {
        const ta = new Date(a.started_at ?? a.created_at).getTime();
        const tb = new Date(b.started_at ?? b.created_at).getTime();
        return tb - ta;
      });
    for (const r of sortedRuns) {
      const arts = buckets.get(r.id);
      if (!arts || arts.length === 0) continue; // hide empty completed runs
      out.push({ key: r.id, run: r, articles: arts });
      seen.add(r.id);
    }

    // Finally — orphan articles (no run id), grouped as a legacy bucket.
    const orphans = buckets.get("orphan");
    if (orphans && orphans.length) {
      out.push({ key: "orphan", run: null, articles: orphans });
    }

    return out;
  }, [articles, runs, runStatus, runActive]);

  // Default expansion: active run + first non-active group expanded once we
  // know the data shape. Runs into stale state? We seed only when the entry
  // first appears.
  useEffect(() => {
    setExpandedRuns((prev) => {
      const next = { ...prev };
      let changed = false;
      groups.forEach((g, i) => {
        if (next[g.key] === undefined) {
          next[g.key] = g.active || i === 0;
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [groups]);

  const toggleRun = (key: string) =>
    setExpandedRuns((s) => ({ ...s, [key]: !s[key] }));

  // Which run's log feed to show in the Activity panel. We follow the user's
  // attention: the active (live) run wins; otherwise the topmost expanded
  // run group. If nothing is expanded and nothing is running we sit idle —
  // no silent fallback — so the user explicitly chose which log they're
  // looking at by expanding that run.
  const focusedRunId: string | null = useMemo(() => {
    if (activeRunId) return activeRunId;
    const expanded = groups.find(
      (g) => g.run && (expandedRuns[g.key] ?? false),
    );
    return expanded?.run?.id ?? null;
  }, [activeRunId, groups, expandedRuns]);

  // Live = the focused run is the active one AND it's still in flight.
  // Once a run completes/fails/cancels we flip into archive mode so the feed
  // header reads "Saved log" instead of "Live" and we skip resubscribing SSE.
  const focusedRunIsLive = runActive && focusedRunId === activeRunId;

  const clearRun = () => {
    setActiveRunId(null);
    setConfirmCancel(false);
  };

  const hasAnything = groups.length > 0;

  return (
    <>
      <Topbar
        title="Today"
        subtitle="Fresh signal, ranked and ready to research."
      />
      <PageBody>
        {/* Control bar */}
        <section className="mb-6 rounded-xl border border-border bg-white p-4 shadow-soft sm:p-5">
          <div className="grid gap-3 md:grid-cols-[260px_1fr_auto]">
            <CategoryPicker
              value={category}
              onChange={setCategory}
              activeKeyword={keyword}
              onKeyword={setKeyword}
              watchlist={WATCHLIST}
            />
            <KeywordPicker
              value={keyword}
              onChange={setKeyword}
              onSubmit={() => {
                if (!runActive && !startMut.isPending) startMut.mutate();
              }}
              disabled={startMut.isPending || runActive}
            />
            <HoverTip
              label={runActive ? "A run is already in progress" : "Start a discovery run (Enter)"}
            >
              <span tabIndex={0} className="inline-flex">
                <Button
                  onClick={() => startMut.mutate()}
                  disabled={startMut.isPending || runActive}
                  className="min-w-[120px]"
                >
                  {startMut.isPending || runActive ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                  {runActive ? "Running…" : "Discover"}
                </Button>
              </span>
            </HoverTip>
          </div>

          {/* Date range — quick presets on top, custom picker below. */}
          <div className="mt-5 border-t border-border pt-5">
            <div className="mb-2.5 flex items-baseline justify-between">
              <div className="flex items-center gap-2">
                <CalendarRange className="h-3.5 w-3.5 text-soft" />
                <span className="text-[10.5px] font-bold uppercase tracking-[0.18em] text-muted">
                  Published window
                </span>
              </div>
              <span className="text-[11px] text-soft">
                {activePreset ?? (dateFrom || dateTo ? "Custom range" : "Any time")}
              </span>
            </div>

            {/* Preset pills */}
            <div className="flex flex-wrap gap-1.5">
              {RANGE_PRESETS.map((p) => {
                const active = activePreset === p.label;
                return (
                  <button
                    key={p.label}
                    type="button"
                    onClick={() => {
                      setDateFrom(p.from);
                      setDateTo(p.to);
                    }}
                    className={cn(
                      "group relative inline-flex h-8 items-center gap-1.5 rounded-lg border px-3 text-[12.5px] font-medium transition-all",
                      active
                        ? "border-ink bg-ink text-white shadow-soft"
                        : "border-border bg-white text-ink hover:border-ink/30 hover:bg-tint/60",
                    )}
                  >
                    <span>{p.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Custom range row */}
            <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-dashed border-border bg-tint/30 px-3 py-2">
              <span className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-soft">
                Custom
              </span>
              <DateField value={dateFrom} max={dateTo || undefined} onChange={setDateFrom} />
              <span className="text-soft">→</span>
              <DateField value={dateTo} min={dateFrom || undefined} onChange={setDateTo} />
              {(dateFrom || dateTo) && (
                <button
                  type="button"
                  onClick={() => {
                    setDateFrom("");
                    setDateTo("");
                  }}
                  className="ml-auto inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-soft transition hover:bg-white hover:text-ink"
                  title="Clear range"
                >
                  Clear
                </button>
              )}
            </div>
          </div>
        </section>

        {/* Two-column body */}
        <section className="grid gap-6 lg:grid-cols-[1fr_360px]">
          <div className="min-w-0 space-y-4">
            {!hasAnything ? (
              <EmptyState loading={articlesQuery.isLoading} hasRun={runActive} />
            ) : (
              groups.map((g, i) => (
                <RunGroup
                  key={g.key}
                  group={g}
                  index={i}
                  expanded={expandedRuns[g.key] ?? (g.active || i === 0)}
                  onToggle={() => toggleRun(g.key)}
                  onResearch={onResearch}
                  isResearching={researchMut.isPending}
                  onDismissRun={
                    g.active
                      ? runStatus?.status === "completed" ||
                        runStatus?.status === "failed"
                        ? clearRun
                        : () => setConfirmCancel(true)
                      : undefined
                  }
                />
              ))
            )}
          </div>
          <aside className="lg:sticky lg:top-4 lg:h-[calc(100vh-6rem)]">
            <RunFeed
              runId={focusedRunId}
              historical={!focusedRunIsLive}
            />
          </aside>
        </section>
      </PageBody>

      <ConfirmDialog
        open={confirmCancel}
        onOpenChange={setConfirmCancel}
        title="Detach from this run?"
        description="The run will keep executing in the background — you'll just stop seeing live updates on this page. You can find completed runs under Companies later."
        confirmText="Detach"
        cancelText="Keep watching"
        onConfirm={clearRun}
      />

      {/* Profile-button confirmation — opened by `onResearch`. Confirm fires
          the mutation; on success the countdown banner takes over. */}
      <ConfirmDialog
        open={!!pendingResearch}
        onOpenChange={(v) => !v && setPendingResearch(null)}
        title={
          pendingResearch
            ? `Build profile of ${pendingResearch.company}?`
            : "Build profile?"
        }
        description="We'll kick off a research run on this company — reading the web, scoring fit, and assembling a company card. You'll be taken to the live progress page once it starts."
        confirmText="Start research"
        cancelText="Not now"
        busy={researchMut.isPending}
        onConfirm={() => {
          if (pendingResearch) researchMut.mutate(pendingResearch);
        }}
      />

      {/* 3-second cancelable countdown — shown after the research run was
          successfully kicked off. If the user cancels, they stay on Today
          (the run keeps running in the background). */}
      {countdown && (
        <ResearchCountdown
          companyName={countdown.company}
          onNavigate={() => {
            // Send the user to the Companies command-center page where they
            // can watch this run's log live alongside every other in-flight
            // profile + past profiles. /runs/:id is still reachable from any
            // expanded row's history.
            setCountdown(null);
            navigate(`/companies`);
          }}
          onCancel={() => {
            toast.message("Stayed on Today", {
              description: `Research on ${countdown.company} is still running in the background.`,
            });
            setCountdown(null);
          }}
        />
      )}
    </>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Empty state
// ──────────────────────────────────────────────────────────────────────────

function EmptyState({
  loading,
  hasRun,
}: {
  loading: boolean;
  hasRun: boolean;
}) {
  if (loading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        {[0, 1].map((i) => (
          <ArticleCardSkeleton key={i} />
        ))}
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-dashed border-border bg-white px-6 py-20 text-center">
      <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-full bg-tint/60">
        <Compass className="h-5 w-5 text-soft" />
      </div>
      <p className="text-sm font-medium text-ink">
        {hasRun ? "Run in progress…" : "No runs yet"}
      </p>
      <p className="mx-auto mt-1 max-w-xs text-xs leading-relaxed text-soft">
        {hasRun
          ? "Articles appear here as they're ranked and extracted."
          : "Pick a category, set a date range, and click Discover to surface fresh signal from TrendHunter."}
      </p>
    </div>
  );
}
