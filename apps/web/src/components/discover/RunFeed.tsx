import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Award,
  BookOpen,
  Building2,
  CheckCircle2,
  CircleDot,
  CircleDollarSign,
  CircleX,
  GitMerge,
  Newspaper,
  Radio,
  Rocket,
  Search,
  PackageOpen,
  TrendingUp,
} from "lucide-react";

import { clockTime, formatCost } from "@/lib/format";
import { recentRunEvents, subscribeRunEvents, type RunEvent } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Live SSE feed of run_events for a single run.
 *
 * Design philosophy:
 *   - The feed is for *humans watching their money work*, not for engineers
 *     debugging the backend. So we never expose raw event kinds like
 *     `ARTICLE_DISCOVERED` or `STAGE_STARTED`. Every row gets a short,
 *     warm human sentence and a contextual icon.
 *   - Costs are rendered as a tinted chip with the dollar coin glyph.
 *   - Stage rows get a stage chip ("Stage 3") so you can map back to the
 *     funnel without us shouting at you.
 */
/**
 * Which backend pipeline this run came from. The stage numbers (1, 2, 3…)
 * mean completely different things between the two — discovery's stage 1 is
 * "search TrendHunter" while research's stage 1 is "build the prompt" — so
 * we can't share a single label table without lying to the user about what
 * just happened.
 */
export type RunPipeline = "discovery" | "research";

export function RunFeed({
  runId,
  historical = false,
  pipeline = "discovery",
}: {
  runId: string | null;
  /**
   * When true, the run is complete/past — we only fetch the saved events and
   * skip the SSE subscription. The header reflects this so users know they're
   * looking at a historical log, not a live stream.
   */
  historical?: boolean;
  pipeline?: RunPipeline;
}) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [initialFetched, setInitialFetched] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!runId) {
      setEvents([]);
      setConnected(false);
      setInitialFetched(false);
      return;
    }
    let cancelled = false;
    setEvents([]);
    setConnected(false);
    setInitialFetched(false);

    recentRunEvents(runId, 200)
      .then((rows) => {
        if (cancelled) return;
        setEvents((prev) => {
          const seen = new Set(prev.map((p) => p.id));
          const merged = [...rows.filter((r) => !seen.has(r.id)), ...prev];
          merged.sort(
            (a, b) =>
              new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
          );
          return merged.length > 200 ? merged.slice(-200) : merged;
        });
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setInitialFetched(true);
      });

    if (historical) {
      return () => {
        cancelled = true;
      };
    }

    const unsubscribe = subscribeRunEvents(
      runId,
      (ev) => {
        setConnected(true);
        setEvents((prev) => {
          if (prev.some((p) => p.id === ev.id)) return prev;
          const next = [...prev, ev];
          return next.length > 200 ? next.slice(-200) : next;
        });
      },
      () => setConnected(false),
      () => setConnected(true),
    );

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [runId, historical]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [events.length]);

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-border bg-white shadow-soft">
      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-1.5 text-sm font-semibold text-ink">
            <Radio className="h-3.5 w-3.5 text-accent" />
            Activity
          </h3>
          <p className="mt-0.5 text-[11px] text-soft">
            {!runId
              ? "Start a run to see the funnel fire"
              : historical
                ? "Saved log from this run"
                : "Streaming live from the funnel"}
          </p>
        </div>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
            !runId
              ? "border-border text-soft"
              : historical
                ? "border-border bg-slate-50 text-soft"
                : connected
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-amber-200 bg-amber-50 text-amber-700",
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              !runId
                ? "bg-soft"
                : historical
                  ? "bg-soft"
                  : connected
                    ? "bg-emerald-500 animate-pulse"
                    : "bg-amber-500",
            )}
          />
          {!runId
            ? "Idle"
            : historical
              ? "Archive"
              : connected
                ? "Live"
                : "Connecting"}
        </span>
      </header>

      <div
        ref={scrollRef}
        className="scrollbar-thin min-h-0 flex-1 overflow-y-auto"
      >
        {events.length === 0 ? (
          !runId ? (
            <div className="px-3 py-12 text-center text-xs text-soft">
              <CircleDot className="mx-auto mb-2 h-4 w-4 text-soft/60" />
              No active run.
            </div>
          ) : !initialFetched ? (
            // Still fetching the saved log — show skeleton rows that mirror
            // EventRow's geometry (timeline rail circle + headline + sub + chip)
            // so the panel doesn't pop when real events arrive.
            <RunFeedSkeleton rows={5} />
          ) : historical ? (
            <div className="px-3 py-12 text-center text-xs text-soft">
              <CircleDot className="mx-auto mb-2 h-4 w-4 text-soft/60" />
              No events recorded for this run.
            </div>
          ) : (
            // Live run, fetch returned 0 — first event hasn't fired yet.
            // Still show skeleton so the user sees the funnel "coming."
            <RunFeedSkeleton rows={5} pulsing />
          )
        ) : (
          <ol className="relative pl-0">
            <AnimatePresence initial={false}>
              {events.map((ev, i) => (
                <EventRow
                  key={ev.id}
                  ev={ev}
                  isLast={i === events.length - 1}
                  pipeline={pipeline}
                />
              ))}
            </AnimatePresence>
          </ol>
        )}
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Skeleton — mirrors EventRow geometry exactly so swapping in real rows
// doesn't cause layout pop. Used while the saved log is loading (Companies
// page entering an existing run) AND while a live run is waiting for its
// first event to fire (Today page after kickoff).
// ──────────────────────────────────────────────────────────────────────────

function RunFeedSkeleton({
  rows = 5,
  pulsing = false,
}: {
  rows?: number;
  pulsing?: boolean;
}) {
  // Fixed widths per row so the skeleton has visual rhythm instead of looking
  // like a striped table. Mirrors a typical funnel: short headline, then
  // longer details, then another short one, etc.
  const widths = [
    { head: "w-24", sub: "w-40" },
    { head: "w-32", sub: "w-48" },
    { head: "w-44", sub: "w-56" },
    { head: "w-28", sub: "w-36" },
    { head: "w-36", sub: "w-52" },
    { head: "w-40", sub: "w-44" },
  ];
  return (
    <ol className="relative pl-0" aria-busy="true" aria-label="Loading activity">
      {Array.from({ length: rows }).map((_, i) => {
        const w = widths[i % widths.length];
        const isLast = i === rows - 1;
        return (
          <li
            key={i}
            className={cn(
              "group relative flex items-start gap-3 px-4 py-2.5",
              pulsing && "animate-pulse",
            )}
          >
            {/* Timeline rail — same dimensions as the real one */}
            <div className="relative flex w-6 shrink-0 justify-center">
              <div className="z-[1] h-6 w-6 rounded-full border border-border bg-tint/60" />
              {!isLast && (
                <span
                  aria-hidden
                  className="absolute left-1/2 top-6 h-[calc(100%+8px)] w-px -translate-x-1/2 bg-border/70"
                />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-3">
                <span className={cn("block h-3 rounded bg-tint/80", w.head)} />
                <span className="block h-2.5 w-10 rounded bg-tint/60" />
              </div>
              <span className={cn("mt-1.5 block h-2.5 rounded bg-tint/50", w.sub)} />
              {i % 2 === 0 && (
                <span className="mt-2 block h-3.5 w-14 rounded-full bg-tint/60" />
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Event row
// ──────────────────────────────────────────────────────────────────────────

function EventRow({
  ev,
  isLast,
  pipeline,
}: {
  ev: RunEvent;
  isLast: boolean;
  pipeline: RunPipeline;
}) {
  const meta = ev.meta || {};
  const stage = typeof meta.stage === "number" ? (meta.stage as number) : null;
  const cost =
    typeof meta.cost_usd === "number" ? (meta.cost_usd as number) : null;
  const score = typeof meta.score === "number" ? (meta.score as number) : null;
  const companies = Array.isArray(meta.companies)
    ? (meta.companies as unknown[]).filter(Boolean).length
    : null;

  const { headline, sub } = humanize(ev, { stage, score, companies, pipeline });
  const Icon = iconFor(ev, stage);
  const tone = toneFor(ev);

  return (
    <motion.li
      layout
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      className="group relative flex items-start gap-3 border-b border-border/40 px-4 py-3 last:border-b-0"
    >
      {/* Timeline rail */}
      <div className="relative flex w-6 shrink-0 justify-center">
        <div
          className={cn(
            "z-[1] grid h-6 w-6 place-items-center rounded-full border bg-white",
            tone.ring,
          )}
        >
          <Icon className={cn("h-3 w-3", tone.icon)} />
        </div>
        {!isLast && (
          <span
            aria-hidden
            className="absolute left-1/2 top-6 h-[calc(100%+8px)] w-px -translate-x-1/2 bg-border/70"
          />
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <p className="truncate text-[13px] font-medium leading-snug text-ink">
            {headline}
          </p>
          <time className="shrink-0 font-mono text-[10px] tabular-nums text-soft">
            {clockTime(ev.created_at)}
          </time>
        </div>
        {sub && (
          <p className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-muted">
            {sub}
          </p>
        )}
        {(stage != null || cost != null) && (
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            {stage != null && (
              <span className="inline-flex items-center gap-1 rounded-full bg-tint/60 px-1.5 py-0.5 text-[10px] font-medium text-muted">
                Stage {stage}
              </span>
            )}
            {cost != null && cost > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 ring-1 ring-emerald-100">
                <CircleDollarSign className="h-2.5 w-2.5" />
                {formatCost(cost)}
              </span>
            )}
          </div>
        )}
      </div>
    </motion.li>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Humanizer — turn raw events into clean copy
// ──────────────────────────────────────────────────────────────────────────

function humanize(
  ev: RunEvent,
  ctx: {
    stage: number | null;
    score: number | null;
    companies: number | null;
    pipeline: RunPipeline;
  },
): { headline: string; sub?: string } {
  const meta = ev.meta || {};
  const k = ev.kind;

  if (k === "run_started") {
    const cat = String(meta.category || "").trim();
    const kw = String(meta.keyword || "").trim();
    const bits = [cat && cap(cat), kw && `“${kw}”`].filter(Boolean);
    return {
      headline: "Run started",
      sub: bits.length ? bits.join(" · ") : undefined,
    };
  }

  if (k === "run_completed") {
    const result = (meta.result as Record<string, unknown>) || {};
    const extracted = num(result.extracted);
    const candidates = num(result.candidates_found);
    return {
      headline: "Run complete",
      sub:
        extracted != null && candidates != null
          ? `${extracted} companies from ${candidates} candidates`
          : undefined,
    };
  }

  if (k === "run_failed" || ev.level === "error") {
    return { headline: "Run failed", sub: ev.message };
  }

  if (k === "stage_started") {
    return { headline: stageStartedCopy(ctx.stage, ctx.pipeline), sub: stageDetail(ev, ctx.stage, ctx.pipeline) };
  }

  if (k === "stage_completed") {
    return {
      headline: stageCompletedCopy(ev, ctx.stage, ctx.pipeline),
      sub: stageCompletedSub(ev, ctx.stage, ctx.pipeline),
    };
  }

  if (k === "article_discovered") {
    return { headline: ev.message || "New candidate", sub: "Candidate surfaced" };
  }

  if (k === "article_ranked") {
    // Backend message format: "{title} — {score}/100"
    const title = stripTrailingScore(ev.message);
    return {
      headline: title,
      sub: ctx.score != null ? `Ranked ${ctx.score}/100` : "Ranked",
    };
  }

  if (k === "article_extracted") {
    // Backend message: "{title} — {n} company(ies)"
    const title = stripTrailingCompanies(ev.message);
    const n = ctx.companies;
    return {
      headline: title,
      sub: n != null ? `Extracted ${n} compan${n === 1 ? "y" : "ies"}` : "Extracted",
    };
  }

  if (k === "log") {
    return { headline: sanitize(ev.message) };
  }

  if (k === "synthesis_retry") {
    const sigs = num(meta.signals_returned);
    return {
      headline: "Profile draft was thin — expanding signals",
      sub: sigs != null ? `Only ${sigs} signal${sigs === 1 ? "" : "s"} on first pass` : undefined,
    };
  }

  if (k === "synthesis_retry_done") {
    const sigs = num(meta.signals_final);
    const srcs = num(meta.sources_final);
    return {
      headline: "Expansion pass complete",
      sub:
        sigs != null && srcs != null
          ? `${sigs} signal${sigs === 1 ? "" : "s"} · ${srcs} source${srcs === 1 ? "" : "s"}`
          : undefined,
    };
  }

  if (k === "signals_harvested") {
    const n = num(meta.harvested);
    return {
      headline: n != null ? `Added ${n} signal${n === 1 ? "" : "s"} from research brief` : "Signals added from research brief",
    };
  }

  if (k === "sources_backfilled") {
    const n = num(meta.backfilled);
    return {
      headline: n != null ? `Attached ${n} verified source${n === 1 ? "" : "s"}` : "Sources attached",
    };
  }

  if (k === "diffbot_lookup_started") {
    return { headline: "Knowledge graph lookup", sub: "Matching company in Diffbot" };
  }

  if (k === "diffbot_lookup_completed") {
    const score = ctx.score;
    const hits = num(meta.hits);
    const ok = meta.has_entity === true;
    return {
      headline: ok ? "Knowledge graph match" : "No knowledge graph match",
      sub:
        score != null && hits != null
          ? `Score ${(score * 100).toFixed(0)}% · ${hits} hit${hits === 1 ? "" : "s"}`
          : undefined,
    };
  }

  if (k === "diffbot_lookup_skipped") {
    return { headline: "Knowledge graph skipped", sub: "Disabled in settings" };
  }

  if (k === "diffbot_domain_derived") {
    const d = String(meta.derived_domain || "").trim();
    return {
      headline: "Domain inferred from search",
      sub: d || undefined,
    };
  }

  return { headline: sanitize(ev.message) || "Event" };
}

/**
 * Strip any tool / engine / stage jargon that may have leaked through from
 * the backend. The activity log is for humans, not for engineers — they
 * shouldn't see "Exa", "Claude", "Sonnet", "Haiku", "Stage 3 — …", etc.
 */
function sanitize(msg: string): string {
  if (!msg) return msg;
  let s = msg;
  // Drop leading "Stage N — " / "Stage N - " prefix.
  s = s.replace(/^\s*Stage\s+\d+\s*[—–-]\s*/iu, "");
  // Replace tool / model proper-names.
  s = s.replace(/\bExa(?:\s+search|\s+\/?contents)?\b/gi, "search");
  s = s.replace(/\bClaude\s+(Haiku|Sonnet|Opus)\b/gi, (_, m) =>
    m.toLowerCase() === "haiku" ? "the ranker" : "the extractor",
  );
  s = s.replace(/\bHaiku\b/g, "the ranker");
  s = s.replace(/\bSonnet\b/g, "the extractor");
  s = s.replace(/\bAnthropic\b/gi, "model");
  // "Parallel + Exa" / "Parallel and Exa" / standalone "Parallel" (the
  // research-engine proper noun, not the english word "parallel" in a
  // sentence like "running in parallel" — we keep the lowercase form).
  s = s.replace(/\bParallel\s*(?:\+|and|&)\s*search\b/gi, "research engines");
  s = s.replace(/\bParallel\s+Task\s+API\b/gi, "research engine");
  s = s.replace(/\bParallel\b/g, "research engine");
  // Collapse any double spaces left over.
  s = s.replace(/\s{2,}/g, " ").trim();
  // Capitalize the first letter so sanitized fragments still read like copy.
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

function stageStartedCopy(stage: number | null, pipeline: RunPipeline): string {
  if (pipeline === "research") {
    switch (stage) {
      case 1: return "Building research brief";
      case 2: return "Querying research engines";
      case 3: return "Synthesizing the profile";
      case 4: return "Saving the profile";
      default: return "Stage started";
    }
  }
  // discovery pipeline (default)
  switch (stage) {
    case 1: return "Searching TrendHunter";
    case 2: return "Deduplicating";
    case 3: return "Ranking by relevance";
    case 4: return "Reading article bodies";
    case 5: return "Extracting companies";
    default: return "Stage started";
  }
}

function stageCompletedCopy(
  ev: RunEvent,
  stage: number | null,
  pipeline: RunPipeline,
): string {
  const m = ev.meta || {};
  const n = (k: string) => (typeof m[k] === "number" ? (m[k] as number) : null);

  if (pipeline === "research") {
    switch (stage) {
      case 1:
        return m.has_article_ctx ? "Brief ready (article attached)" : "Brief ready";
      case 2: {
        const reads = n("exa_reads");
        const pOk = m.parallel_ok === true;
        const pFail = m.parallel_ok === false;
        if (pOk && reads != null)
          return `Research engines done · ${reads} source${reads === 1 ? "" : "s"}`;
        if (pFail && reads != null)
          return `Engines partial · ${reads} source${reads === 1 ? "" : "s"} (main engine failed)`;
        return "Research engines done";
      }
      case 3: {
        const sigs = n("signal_count");
        const srcs = n("source_count");
        if (sigs != null && srcs != null)
          return `Profile drafted · ${sigs} signal${sigs === 1 ? "" : "s"} · ${srcs} source${srcs === 1 ? "" : "s"}`;
        return "Profile drafted";
      }
      case 4:
        return "Profile saved";
      default:
        return "Stage complete";
    }
  }

  // discovery pipeline (default)
  switch (stage) {
    case 1: {
      const c = n("count");
      return c != null ? `Found ${c} candidate${c === 1 ? "" : "s"}` : "Search complete";
    }
    case 2: {
      const fresh = n("new");
      const dupes = n("dupes");
      if (fresh != null && dupes != null)
        return `${fresh} new · ${dupes} already seen`;
      return "Dedup complete";
    }
    case 3: {
      const k = n("kept");
      return k != null ? `Kept top ${k}` : "Ranking complete";
    }
    case 4: {
      const r = n("read");
      return r != null ? `Read ${r} bod${r === 1 ? "y" : "ies"}` : "Reading complete";
    }
    case 5: {
      const e = n("extracted");
      return e != null ? `Pulled ${e} compan${e === 1 ? "y" : "ies"}` : "Extraction complete";
    }
    default:
      return "Stage complete";
  }
}

function stageCompletedSub(
  ev: RunEvent,
  stage: number | null,
  pipeline: RunPipeline,
): string | undefined {
  const m = ev.meta || {};
  if (pipeline === "research") {
    const pCost =
      typeof m.parallel_cost === "number" ? (m.parallel_cost as number) : null;
    const eCost = typeof m.exa_cost === "number" ? (m.exa_cost as number) : null;
    if (stage === 2 && (pCost != null || eCost != null)) {
      const parts: string[] = [];
      if (pCost != null) parts.push(`engine ${formatCost(pCost)}`);
      if (eCost != null) parts.push(`search ${formatCost(eCost)}`);
      return parts.join(" · ");
    }
    if (stage === 3 && typeof m.cost === "number")
      return `extractor ${formatCost(m.cost as number)}`;
  }
  return undefined;
}

function stageDetail(
  ev: RunEvent,
  stage: number | null,
  pipeline: RunPipeline,
): string | undefined {
  const m = ev.meta || {};
  if (pipeline === "research") {
    if (stage === 2) return "engines running in parallel";
    if (stage === 3) return "writing the company card";
    return undefined;
  }
  if (stage === 1 && typeof m.query === "string") return `Query: ${m.query}`;
  if ((stage === 2 || stage === 3 || stage === 4 || stage === 5) &&
      typeof m.count === "number")
    return `${m.count} article${m.count === 1 ? "" : "s"} in scope`;
  return undefined;
}

function stripTrailingScore(msg: string): string {
  // "Title — 88/100"  → "Title"
  return msg.replace(/\s*[—-]\s*\d+\s*\/\s*100\s*$/u, "");
}

function stripTrailingCompanies(msg: string): string {
  // "Title — 2 company(ies)" → "Title"
  return msg.replace(/\s*[—-]\s*\d+\s*compan(y|ies|y\(ies\))\s*$/iu, "");
}

function num(v: unknown): number | null {
  return typeof v === "number" ? v : null;
}

function cap(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

// ──────────────────────────────────────────────────────────────────────────
// Icon + tone routing
// ──────────────────────────────────────────────────────────────────────────

function iconFor(ev: RunEvent, stage: number | null) {
  if (ev.level === "error" || ev.kind === "run_failed") return CircleX;
  if (ev.kind === "run_completed") return CheckCircle2;
  if (ev.kind === "run_started") return Rocket;
  if (ev.kind === "article_discovered") return Newspaper;
  if (ev.kind === "article_ranked") return TrendingUp;
  if (ev.kind === "article_extracted") return Building2;
  if (ev.level === "warn") return AlertTriangle;
  if (ev.kind === "stage_started" || ev.kind === "stage_completed") {
    if (stage === 1) return Search;
    if (stage === 2) return GitMerge;
    if (stage === 3) return Award;
    if (stage === 4) return BookOpen;
    if (stage === 5) return PackageOpen;
  }
  return CircleDot;
}

type Tone = { icon: string; ring: string };
function toneFor(ev: RunEvent): Tone {
  if (ev.level === "error" || ev.kind === "run_failed")
    return { icon: "text-red-600", ring: "border-red-200 bg-red-50" };
  if (ev.level === "warn")
    return { icon: "text-amber-600", ring: "border-amber-200 bg-amber-50" };
  if (ev.kind === "run_completed")
    return { icon: "text-emerald-600", ring: "border-emerald-200 bg-emerald-50" };
  if (ev.kind === "run_started")
    return { icon: "text-accent", ring: "border-accent/30 bg-accent/5" };
  if (ev.kind === "stage_completed")
    return { icon: "text-emerald-600", ring: "border-emerald-200 bg-emerald-50" };
  if (ev.kind === "stage_started")
    return { icon: "text-accent", ring: "border-accent/30 bg-accent/5" };
  if (ev.kind === "article_extracted")
    return { icon: "text-navy", ring: "border-navy/20 bg-navy/5" };
  if (ev.kind === "article_ranked")
    return { icon: "text-violet-600", ring: "border-violet-200 bg-violet-50" };
  if (ev.kind === "article_discovered")
    return { icon: "text-slate-500", ring: "border-slate-200 bg-slate-50" };
  return { icon: "text-soft", ring: "border-border bg-tint" };
}
