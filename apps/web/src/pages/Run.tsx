import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowRight,
  CheckCircle2,
  Loader2,
  Sparkles,
  XCircle,
} from "lucide-react";

import { RunFeed } from "@/components/discover/RunFeed";
import { Topbar } from "@/components/layout/Topbar";
import { Card, CardBody } from "@/components/ui/Card";
import { PageBody } from "@/components/ui/PageBody";
import { Pill } from "@/components/ui/Pill";
import { getResearchRun, type ResearchRunStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Live research run view. Polls /api/research/runs/:id every 2s and renders
 * the SSE feed in the right column. When the run completes successfully we
 * surface a CTA to jump straight to the resulting Company Card.
 */
export default function Run() {
  const { id } = useParams<{ id: string }>();

  const runQuery = useQuery({
    queryKey: ["research-run", id],
    queryFn: () => (id ? getResearchRun(id) : Promise.resolve(null)),
    enabled: !!id,
    refetchInterval: (q) => {
      const r = q.state.data as ResearchRunStatus | null | undefined;
      if (!r) return 2000;
      return r.status === "completed" || r.status === "failed" ? false : 2000;
    },
  });
  const run = runQuery.data ?? null;

  const subtitle = run ? labelFor(run) : `Live progress · ${id ?? "—"}`;

  return (
    <>
      <Topbar title={run?.query ?? "Research"} subtitle={subtitle} />
      <PageBody>
        <section className="grid gap-6 lg:grid-cols-[1fr_360px]">
          <div className="min-w-0">
            <Card>
              <CardBody>
                {!run && (
                  <div className="flex items-center gap-2 text-sm text-soft">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading run…
                  </div>
                )}
                {run && <RunHeader run={run} />}
              </CardBody>
            </Card>

            {run && <Stages run={run} />}
            {run && run.status === "completed" && run.company_id && (
              <SummaryCard run={run} />
            )}
          </div>

          <aside className="lg:sticky lg:top-6 lg:h-[calc(100vh-7rem)]">
            <RunFeed runId={id ?? null} pipeline="research" />
          </aside>
        </section>
      </PageBody>
    </>
  );
}

function RunHeader({ run }: { run: ResearchRunStatus }) {
  const isDone = run.status === "completed";
  const isFail = run.status === "failed";
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Pill
          variant={
            isDone ? "success" : isFail ? "warning" : "accent"
          }
        >
          {isDone ? (
            <CheckCircle2 className="h-3 w-3" />
          ) : isFail ? (
            <XCircle className="h-3 w-3" />
          ) : (
            <Loader2 className="h-3 w-3 animate-spin" />
          )}
          {run.status}
        </Pill>
        <Pill variant="neutral">{run.source_kind}</Pill>
        <span className="text-xs text-soft">
          run {run.id.slice(0, 8)}…
        </span>
      </div>

      <div>
        <div className="flex items-center gap-2 text-xs text-soft">
          <span>{run.progress_pct}%</span>
        </div>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-tint">
          <div
            className={cn(
              "h-full rounded-full transition-all",
              isFail ? "bg-red-500" : "bg-accent",
            )}
            style={{ width: `${run.progress_pct}%` }}
          />
        </div>
      </div>

      {run.error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {run.error}
        </div>
      )}

    </div>
  );
}

/**
 * Post-completion summary surface. Shows once the run lands and acts as the
 * user's hand-off into the full Company page. Intentionally large and
 * tappable — this is the moment of payoff for the whole pipeline.
 */
function SummaryCard({ run }: { run: ResearchRunStatus }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="mt-6"
    >
      <Link
        to={`/companies/${run.company_id}`}
        className={cn(
          "group block overflow-hidden rounded-xl border bg-white p-5 transition-all",
          "border-emerald-200/70 shadow-soft hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-lift",
        )}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-700">
              <Sparkles className="h-3 w-3" />
              Research complete
            </div>
            <h3 className="mt-2 truncate text-lg font-semibold text-ink">
              {run.query}
            </h3>
            <p className="mt-1 text-sm text-muted">
              The company profile is ready. Open it for the full breakdown —
              scores, signals, fit, risk, and sources.
            </p>
          </div>
          <span
            className={cn(
              "grid h-10 w-10 shrink-0 place-items-center rounded-full",
              "bg-accent text-white shadow-sm transition group-hover:scale-105",
            )}
            aria-hidden
          >
            <ArrowRight className="h-5 w-5" />
          </span>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-emerald-100 pt-3 text-[12px] text-soft">
          <span>View full company page</span>
          <ArrowRight className="h-3 w-3" />
        </div>
      </Link>
    </motion.div>
  );
}

function Stages({ run }: { run: ResearchRunStatus }) {
  const stages = useMemo(
    () => [
      { name: "Input", pct: 15 },
      { name: "Web research", pct: 55 },
      { name: "Synthesis", pct: 85 },
      { name: "Persist", pct: 100 },
    ],
    [],
  );
  return (
    <Card className="mt-6">
      <CardBody>
        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-soft">
          Pipeline
        </div>
        <ol className="mt-3 space-y-2 text-sm">
          {stages.map((s, i) => {
            const done = run.progress_pct >= s.pct;
            const active = !done && run.progress_pct >= (stages[i - 1]?.pct ?? 0);
            return (
              <li key={s.name} className="flex items-center gap-3">
                <span
                  className={cn(
                    "grid h-5 w-5 place-items-center rounded-full text-[10px] font-semibold",
                    done
                      ? "bg-emerald-500 text-white"
                      : active
                        ? "bg-accent text-white"
                        : "bg-tint text-soft",
                  )}
                >
                  {done ? "✓" : i + 1}
                </span>
                <span className={cn(done || active ? "text-ink" : "text-muted")}>
                  {s.name}
                </span>
              </li>
            );
          })}
        </ol>
      </CardBody>
    </Card>
  );
}

function labelFor(r: ResearchRunStatus): string {
  if (r.status === "completed") return "Profile ready — open the company page";
  if (r.status === "failed") return "Failed";
  if (r.status === "synthesizing") return "Synthesizing the company profile";
  if (r.status === "researching") return "Reading the web";
  return r.status;
}
