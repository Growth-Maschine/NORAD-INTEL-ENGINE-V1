import { AnimatePresence, motion } from "framer-motion";
import {
  Building2,
  CheckCircle2,
  ChevronDown,
  CircleX,
  Clock,
  Layers,
  Loader2,
  Timer,
  X,
} from "lucide-react";

import { ArticleCard } from "@/components/discover/ArticleCard";
import { ArticleCardSkeleton } from "@/components/discover/ArticleCardSkeleton";
import { ResearchTrigger } from "@/components/discover/ResearchTrigger";
import { StageProgress } from "@/components/discover/StageProgress";
import { Button } from "@/components/ui/Button";
import { HoverTip } from "@/components/ui/Tooltip";
import { type Article, type RunStatus } from "@/lib/api";
import { dateTimeShort, durationBetween, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

export interface RunGroupData {
  /** Run id (or "orphan" for ungrouped articles). */
  key: string;
  /** Run metadata — null for orphans / unknown runs. */
  run: RunStatus | null;
  articles: Article[];
  /** When this is the run currently streaming. */
  active?: boolean;
}

export function RunGroup({
  group,
  expanded,
  onToggle,
  onResearch,
  isResearching,
  onDismissRun,
  index,
}: {
  group: RunGroupData;
  expanded: boolean;
  onToggle: () => void;
  onResearch: (article: Article, company: string) => void;
  isResearching: boolean;
  /** Detach/clear callback (only used for the active run). */
  onDismissRun?: () => void;
  /** 0 for the most-recent run — used for the label. */
  index: number;
}) {
  const { run, articles, active } = group;
  const extracted = articles.filter((a) => a.status === "extracted");
  const companyCount = extracted.reduce(
    (n, a) => n + (a.extracted_companies?.length ?? 0),
    0,
  );
  const status = run?.status ?? "completed";
  const isFailed = status === "failed";
  const isDone = !active && (status === "completed" || status === "failed");

  // Sort articles by relevance score desc, then by title.
  const sortedArticles = [...articles]
    .filter((a) => a.status !== "dismissed")
    .sort((a, b) => {
      const sa = a.relevance_score ?? -1;
      const sb = b.relevance_score ?? -1;
      if (sa !== sb) return sb - sa;
      return (a.title || "").localeCompare(b.title || "");
    });

  const scoreRange = (() => {
    const scores = sortedArticles
      .map((a) => a.relevance_score)
      .filter((s): s is number => typeof s === "number" && s > 0);
    if (!scores.length) return null;
    const hi = Math.max(...scores);
    const lo = Math.min(...scores);
    return hi === lo ? `${hi}` : `${lo}–${hi}`;
  })();

  const label =
    active
      ? "Active run"
      : index === 0
        ? "Latest run"
        : `Run · ${run?.started_at ? timeAgo(run.started_at) : "earlier"}`;

  return (
    <section
      className={cn(
        "overflow-hidden rounded-xl border bg-white shadow-soft",
        active ? "border-accent/40 ring-1 ring-accent/15" : "border-border",
      )}
    >
      {/* ── Header ─────────────────────────────────────────────── */}
      <header
        className={cn(
          "flex flex-col gap-3 border-b px-4 py-3 sm:px-5",
          active ? "border-accent/20 bg-accent/[0.04]" : "border-border bg-tint/30",
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <button
            type="button"
            onClick={onToggle}
            className="group flex min-w-0 flex-1 items-center gap-3 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
            aria-expanded={expanded}
            aria-controls={`run-body-${group.key}`}
          >
            <StatusDot status={status} active={active} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-soft">
                  {label}
                </span>
                {run?.started_at && (
                  <HoverTip label={`Started ${dateTimeShort(run.started_at)}`}>
                    <span className="font-mono text-[11px] tabular-nums text-muted">
                      {dateTimeShort(run.started_at)}
                    </span>
                  </HoverTip>
                )}
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-muted">
                {run?.query && (
                  <span className="truncate font-medium text-ink">
                    {prettifyQuery(run.query)}
                  </span>
                )}
                <Stat icon={Layers} label={`${sortedArticles.length} articles`} />
                <Stat
                  icon={Building2}
                  label={`${companyCount} compan${companyCount === 1 ? "y" : "ies"}`}
                />
                {scoreRange && (
                  <Stat icon={null} label={`Score ${scoreRange}`} />
                )}
                {run?.started_at && (
                  <Stat
                    icon={active ? Timer : Clock}
                    label={durationBetween(
                      run.started_at,
                      active ? null : run.completed_at,
                    )}
                  />
                )}
              </div>
            </div>
            <ChevronDown
              className={cn(
                "h-4 w-4 shrink-0 text-soft transition-transform duration-200",
                expanded && "rotate-180",
                "group-hover:text-ink",
              )}
            />
          </button>
          {onDismissRun && active && (
            <HoverTip label={isDone ? "Clear this run" : "Detach from this run"}>
              <Button
                variant="ghost"
                size="sm"
                onClick={onDismissRun}
                className="h-7 shrink-0 px-2 text-xs"
              >
                <X className="h-3.5 w-3.5" />
                {isDone ? "Clear" : "Detach"}
              </Button>
            </HoverTip>
          )}
        </div>

        {/* Stage progress (only while active or showing the latest run that
            just finished — gives context to what each stat means). */}
        {run && (active || (status !== "completed" && status !== "failed" && status !== "cancelled")) && (
          <div>
            <StageProgress progressPct={run.progress_pct} status={status} />
          </div>
        )}
        {run?.error && isFailed && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {run.error}
          </div>
        )}
      </header>

      {/* ── Body ───────────────────────────────────────────────── */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            id={`run-body-${group.key}`}
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="p-4 sm:p-5">
              {active && sortedArticles.length === 0 ? (
                <div className="grid gap-4 sm:grid-cols-2">
                  {[0, 1, 2, 3].map((i) => (
                    <ArticleCardSkeleton key={i} />
                  ))}
                </div>
              ) : sortedArticles.length === 0 ? (
                <EmptyRun />
              ) : (
                <motion.div
                  layout
                  className="grid gap-4 sm:grid-cols-2"
                >
                  <AnimatePresence initial={false}>
                    {sortedArticles.map((a) => {
                      const primary = a.extracted_companies[0]?.name ?? null;
                      return (
                        <div
                          key={a.id}
                          className="flex items-center gap-3 sm:gap-4"
                        >
                          {/* Card flexes — golden trigger sits *beside* it
                              (not absolutely positioned, so it can never be
                              clipped by an ancestor's overflow-hidden). */}
                          <div className="min-w-0 flex-1">
                            <ArticleCard article={a} />
                          </div>
                          <ResearchTrigger
                            companyName={primary}
                            disabled={!primary}
                            busy={isResearching}
                            onClick={() => {
                              if (primary) onResearch(a, primary);
                            }}
                          />
                        </div>
                      );
                    })}
                  </AnimatePresence>
                </motion.div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

function StatusDot({
  status,
  active,
}: {
  status: string;
  active?: boolean;
}) {
  if (active && status !== "completed" && status !== "failed") {
    return (
      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-accent/10 text-accent">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-red-50 text-red-600">
        <CircleX className="h-4 w-4" />
      </span>
    );
  }
  return (
    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-emerald-50 text-emerald-600">
      <CheckCircle2 className="h-4 w-4" />
    </span>
  );
}

function Stat({
  icon: Icon,
  label,
}: {
  icon: React.ComponentType<{ className?: string }> | null;
  label: string;
}) {
  return (
    <span className="inline-flex items-center gap-1 text-[12px] text-muted">
      {Icon && <Icon className="h-3 w-3 text-soft" />}
      {label}
    </span>
  );
}

function EmptyRun() {
  return (
    <div className="rounded-md border border-dashed border-border bg-tint/30 px-4 py-8 text-center text-xs text-soft">
      No surviving articles in this run.
    </div>
  );
}

/** "discover:food" / "trending Food" / "protein bars" → "Food" / "Protein bars". */
function prettifyQuery(query: string): string {
  if (!query) return "";
  let s = query.trim();
  s = s.replace(/^discover:\s*/i, "");
  s = s.replace(/^trending\s+/i, "");
  s = s.replace(/[-_]+/g, " ").trim();
  if (!s) return query;
  return s[0].toUpperCase() + s.slice(1);
}
