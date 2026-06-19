import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Award,
  BookOpen,
  CheckCircle2,
  CircleDot,
  CircleDollarSign,
  CircleX,
  GitMerge,
  Radio,
  Rocket,
  Search,
} from "lucide-react";

import { clockTime, formatCost } from "@/lib/format";
import { recentRunEvents, subscribeRunEvents, type RunEvent } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Live SSE feed of run_events for a single research run. */
export function RunFeed({
  runId,
  historical = false,
}: {
  runId: string | null;
  historical?: boolean;
  /** @deprecated pipeline prop removed — feed is research-only */
  pipeline?: "research";
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
            <RunFeedSkeleton rows={5} />
          ) : historical ? (
            <div className="px-3 py-12 text-center text-xs text-soft">
              <CircleDot className="mx-auto mb-2 h-4 w-4 text-soft/60" />
              No events recorded for this run.
            </div>
          ) : (
            <RunFeedSkeleton rows={5} pulsing />
          )
        ) : (
          <ol className="relative pl-0">
            <AnimatePresence initial={false}>
              {events.map((ev, i) => (
                <EventRow key={ev.id} ev={ev} isLast={i === events.length - 1} />
              ))}
            </AnimatePresence>
          </ol>
        )}
      </div>
    </div>
  );
}

function RunFeedSkeleton({
  rows = 5,
  pulsing = false,
}: {
  rows?: number;
  pulsing?: boolean;
}) {
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

function EventRow({ ev, isLast }: { ev: RunEvent; isLast: boolean }) {
  const meta = ev.meta || {};
  const stage = typeof meta.stage === "number" ? (meta.stage as number) : null;
  const cost =
    typeof meta.cost_usd === "number" ? (meta.cost_usd as number) : null;

  const { headline, sub } = humanize(ev, stage);
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

function humanize(
  ev: RunEvent,
  stage: number | null,
): { headline: string; sub?: string } {
  const meta = ev.meta || {};
  const k = ev.kind;

  if (k === "run_started") {
    return { headline: "Run started" };
  }

  if (k === "run_completed") {
    return { headline: "Run complete" };
  }

  if (k === "run_failed" || ev.level === "error") {
    return { headline: "Run failed", sub: ev.message };
  }

  if (k === "stage_started") {
    return { headline: stageStartedCopy(stage), sub: stageDetail(stage) };
  }

  if (k === "stage_completed") {
    return {
      headline: stageCompletedCopy(ev, stage),
      sub: stageCompletedSub(ev, stage),
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

  return { headline: sanitize(ev.message) || "Event" };
}

function sanitize(msg: string): string {
  if (!msg) return msg;
  let s = msg.replace(/^\s*Stage\s+\d+\s*[—–-]\s*/iu, "");
  s = s.replace(/\bExa(?:\s+search|\s+\/?contents)?\b/gi, "search");
  s = s.replace(/\bParallel\s*(?:\+|and|&)\s*search\b/gi, "research engines");
  s = s.replace(/\bParallel\b/g, "research engine");
  s = s.replace(/\s{2,}/g, " ").trim();
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

function stageStartedCopy(stage: number | null): string {
  switch (stage) {
    case 1: return "Building research brief";
    case 2: return "Querying research engines";
    case 3: return "Synthesizing the profile";
    case 4: return "Saving the profile";
    default: return "Stage started";
  }
}

function stageCompletedCopy(ev: RunEvent, stage: number | null): string {
  const m = ev.meta || {};
  const n = (k: string) => (typeof m[k] === "number" ? (m[k] as number) : null);

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

function stageCompletedSub(ev: RunEvent, stage: number | null): string | undefined {
  const m = ev.meta || {};
  const pCost = typeof m.parallel_cost === "number" ? (m.parallel_cost as number) : null;
  const eCost = typeof m.exa_cost === "number" ? (m.exa_cost as number) : null;
  if (stage === 2 && (pCost != null || eCost != null)) {
    const parts: string[] = [];
    if (pCost != null) parts.push(`engine ${formatCost(pCost)}`);
    if (eCost != null) parts.push(`search ${formatCost(eCost)}`);
    return parts.join(" · ");
  }
  if (stage === 3 && typeof m.cost === "number")
    return `extractor ${formatCost(m.cost as number)}`;
  return undefined;
}

function stageDetail(stage: number | null): string | undefined {
  if (stage === 2) return "engines running in parallel";
  if (stage === 3) return "writing the company card";
  return undefined;
}

function num(v: unknown): number | null {
  return typeof v === "number" ? v : null;
}

function iconFor(ev: RunEvent, stage: number | null) {
  if (ev.level === "error" || ev.kind === "run_failed") return CircleX;
  if (ev.kind === "run_completed") return CheckCircle2;
  if (ev.kind === "run_started") return Rocket;
  if (ev.level === "warn") return AlertTriangle;
  if (ev.kind === "stage_started" || ev.kind === "stage_completed") {
    if (stage === 1) return Search;
    if (stage === 2) return GitMerge;
    if (stage === 3) return Award;
    if (stage === 4) return BookOpen;
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
  return { icon: "text-soft", ring: "border-border bg-tint" };
}
