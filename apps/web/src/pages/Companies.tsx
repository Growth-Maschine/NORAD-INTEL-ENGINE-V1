import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Loader2,
  Radio,
  XCircle,
  XOctagon,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Topbar } from "@/components/layout/Topbar";
import { RunFeed } from "@/components/discover/RunFeed";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageBody } from "@/components/ui/PageBody";
import { Pill } from "@/components/ui/Pill";
import {
  cancelResearchRun,
  getCompany,
  listCompanyFeed,
  type CompanyDetail,
  type CompanyFeedRow,
} from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Companies — research command center.
 *
 * Layout: Activity log on the LEFT (matches the user's mental model — the
 * log is the *origin* of what they're looking at; the company list is the
 * result). Each row collapses to a one-liner and expands to show the engine
 * summary + top signals. The Activity panel always tracks whichever row the
 * user is paying attention to (the most-recently expanded one) so logs stay
 * attached to their run instead of disappearing when the run finishes.
 *
 * Sort: live runs first (amber pulse), then by latest-run recency desc.
 */
export default function Companies() {
  const feedQuery = useQuery({
    queryKey: ["company-feed"],
    queryFn: () => listCompanyFeed(50),
    refetchInterval: (q) => {
      const rows = q.state.data as CompanyFeedRow[] | undefined;
      if (!rows) return 8000;
      return rows.some((r) => r.is_live) ? 3000 : 15000;
    },
  });
  const rows = feedQuery.data ?? [];

  // Track which rows are expanded. Default: the topmost live row expanded so
  // the user lands looking at the action.
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  // Seed expansion for new rows (first live row by default).
  useMemo(() => {
    if (rows.length === 0) return;
    setExpanded((prev) => {
      if (Object.keys(prev).length > 0) return prev;
      const firstLive = rows.find((r) => r.is_live) ?? rows[0];
      return firstLive ? { [firstLive.bucket_key]: true } : prev;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows.length]);

  const toggle = (k: string) =>
    setExpanded((s) => ({ ...s, [k]: !s[k] }));

  // The feed panel follows whichever expanded row is highest in the list.
  // Defensive: if no expanded row matches (e.g. a row's bucket key changed
  // server-side mid-poll), fall back to the top live row so the Activity
  // rail keeps showing real work instead of going idle. If nothing is live
  // and nothing matched, we sit idle on purpose — no silent fallbacks.
  const focusedRow: CompanyFeedRow | null = useMemo(() => {
    const matched = rows.find((r) => expanded[r.bucket_key]);
    if (matched) return matched;
    const hasAnyExpanded = Object.values(expanded).some(Boolean);
    if (hasAnyExpanded) {
      const topLive = rows.find((r) => r.is_live);
      if (topLive) return topLive;
    }
    return null;
  }, [rows, expanded]);

  const focusedRunId = focusedRow?.latest_run.id ?? null;
  const focusedIsLive =
    !!focusedRow &&
    focusedRow.is_live &&
    focusedRow.latest_run.status !== "completed" &&
    focusedRow.latest_run.status !== "failed" &&
    focusedRow.latest_run.status !== "cancelled";

  return (
    <>
      <Topbar
        title="Companies"
        subtitle={
          rows.length === 0
            ? "Click Profile on a Today card to start your first research run."
            : `${rows.length} profile${rows.length === 1 ? "" : "s"} · ${rows.filter((r) => r.is_live).length} running`
        }
      />
      <PageBody>
        {feedQuery.isLoading && (
          <div className="rounded-xl border border-dashed border-border bg-white px-6 py-16 text-center text-sm text-soft">
            <Loader2 className="mx-auto mb-3 h-5 w-5 animate-spin" />
            Loading the feed…
          </div>
        )}

        {!feedQuery.isLoading && rows.length === 0 && (
          <EmptyState
            icon={Building2}
            title="No profiles yet"
            description="Click 'Profile' on any extracted company in the Today feed to start your first research run. It'll show up here, live."
          />
        )}

        {rows.length > 0 && (
          <section className="grid gap-6 lg:grid-cols-[340px_1fr]">
            {/* Activity log — left rail, sticky */}
            <aside className="lg:sticky lg:top-4 lg:h-[calc(100vh-6rem)]">
              <RunFeed
                runId={focusedRunId}
                historical={!focusedIsLive}
                pipeline="research"
              />
            </aside>

            {/* Company list — main column */}
            <div className="min-w-0 space-y-3">
              {rows.map((r) => (
                <CompanyRow
                  key={r.bucket_key}
                  row={r}
                  open={!!expanded[r.bucket_key]}
                  onToggle={() => toggle(r.bucket_key)}
                />
              ))}
            </div>
          </section>
        )}
      </PageBody>
    </>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Row
// ──────────────────────────────────────────────────────────────────────────

function CompanyRow({
  row,
  open,
  onToggle,
}: {
  row: CompanyFeedRow;
  open: boolean;
  onToggle: () => void;
}) {
  const initials = (row.company_name || "?")
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();

  const status = row.latest_run.status;
  const isLive = row.is_live;
  const isFail = status === "failed" || status === "cancelled";
  const isDone = status === "completed";

  const dotTone = isLive
    ? "bg-amber-500 animate-pulse"
    : isFail
      ? "bg-red-500"
      : isDone
        ? "bg-emerald-500"
        : "bg-soft";

  const stamp = formatStamp(
    row.latest_run.started_at ?? row.latest_run.created_at,
  );

  return (
    <Card className={cn("overflow-hidden", isLive && "ring-1 ring-amber-300/60")}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-4 px-4 py-3 text-left transition hover:bg-tint/30"
      >
        <span
          aria-hidden
          className={cn("h-2 w-2 shrink-0 rounded-full", dotTone)}
        />
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-accent text-xs font-bold text-white">
          {initials}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-sm font-semibold text-ink">
              {row.company_name}
            </h3>
            {row.industry && <Pill variant="navy">{row.industry}</Pill>}
            {isLive ? (
              <Pill variant="warning">
                <Radio className="h-3 w-3" />
                Profiling… {row.latest_run.progress_pct}%
              </Pill>
            ) : isFail ? (
              <Pill variant="warning">
                <XCircle className="h-3 w-3" />
                {status}
              </Pill>
            ) : isDone ? (
              <Pill variant="success">
                <CheckCircle2 className="h-3 w-3" />
                Done
              </Pill>
            ) : (
              <Pill variant="neutral">{status}</Pill>
            )}
            {row.run_count > 1 && (
              <span className="text-[10px] font-semibold uppercase tracking-[0.06em] text-soft">
                {row.run_count} runs
              </span>
            )}
          </div>
          <div className="mt-0.5 truncate text-xs text-muted">
            {row.domain ?? "—"} · {stamp}
          </div>
        </div>

        <div className="text-right">
          <div className="text-lg font-semibold text-ink">
            {row.score_overall ?? "—"}
          </div>
          <div className="text-[10px] uppercase tracking-wider text-soft">
            overall
          </div>
        </div>

        <ChevronDown
          className={cn(
            "ml-1 h-4 w-4 shrink-0 text-soft transition",
            open && "rotate-180 text-ink",
          )}
        />
      </button>

      {open && <CompanyRowDetail row={row} />}
    </Card>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Expanded detail — engine summary + top signals + open page CTA
// ──────────────────────────────────────────────────────────────────────────

function CompanyRowDetail({ row }: { row: CompanyFeedRow }) {
  const companyId = row.company_id;
  const qc = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);

  // Lazy-load the full card only when expanded. If the run hasn't resolved a
  // company yet (in-flight first time), we just show progress.
  const detailQuery = useQuery({
    queryKey: ["company", companyId],
    queryFn: () => (companyId ? getCompany(companyId) : Promise.resolve(null)),
    enabled: !!companyId,
    refetchInterval: row.is_live ? 5000 : false,
  });
  const detail = detailQuery.data ?? null;

  const cancelMut = useMutation({
    mutationFn: () => cancelResearchRun(row.latest_run.id),
    onSuccess: () => {
      // Refresh the companies feed (this row will flip to cancelled) and any
      // run-log query.
      qc.invalidateQueries({ queryKey: ["company-feed"] });
      qc.invalidateQueries({ queryKey: ["run", row.latest_run.id] });
    },
  });

  return (
    <div className="border-t border-border bg-tint/20 px-4 py-4">
      {!companyId ? (
        <div className="flex items-center gap-2 text-xs text-muted">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-600" />
          Resolving company… the profile will fill in here as the engines
          finish.
        </div>
      ) : detailQuery.isLoading ? (
        <div className="flex items-center gap-2 text-xs text-soft">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Loading profile…
        </div>
      ) : !detail ? (
        <div className="text-xs text-soft">Profile not available yet.</div>
      ) : (
        <ProfileExcerpt detail={detail} companyId={companyId} />
      )}

      <div className="mt-3 flex items-center justify-between border-t border-border/70 pt-3 text-[11px] text-soft">
        <div className="flex items-center gap-3">
          <Link
            to={`/runs/${row.latest_run.id}`}
            className="inline-flex items-center gap-1 hover:text-ink"
          >
            View run log →
          </Link>
          {row.is_live && (
            <button
              type="button"
              onClick={() => setConfirmOpen(true)}
              disabled={cancelMut.isPending}
              className="inline-flex items-center gap-1 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-[11px] font-semibold text-red-700 transition hover:bg-red-100 disabled:opacity-60"
            >
              <XOctagon className="h-3 w-3" />
              {cancelMut.isPending ? "Cancelling…" : "Cancel run"}
            </button>
          )}
        </div>
        {companyId && (
          <Link
            to={`/companies/${companyId}`}
            className="inline-flex items-center gap-1 font-semibold text-accent hover:text-accent/80"
          >
            Open full page
            <ChevronRight className="h-3 w-3" />
          </Link>
        )}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Cancel this research run?"
        description={
          `"${row.company_name}" is currently profiling. Cancelling will stop ` +
          `the pipeline at the next checkpoint — engine calls already in ` +
          `flight may still finish, but no company / card / signals will be ` +
          `saved from this run.`
        }
        confirmText="Cancel run"
        cancelText="Keep running"
        variant="danger"
        busy={cancelMut.isPending}
        onConfirm={() => cancelMut.mutate()}
      />
    </div>
  );
}

function ProfileExcerpt({
  detail,
  companyId,
}: {
  detail: CompanyDetail;
  companyId: string;
}) {
  const { card, signals } = detail;
  const c = card?.card ?? {};
  const fit = c.strategic_fit ?? {};
  const fitSummary: string | undefined = fit.fit_summary?.value;
  const recAction: string | undefined = fit.recommended_next_action?.value;
  const topSignals = signals.slice(0, 2);

  if (!fitSummary && topSignals.length === 0) {
    return (
      <Link
        to={`/companies/${companyId}`}
        className="text-xs text-muted underline-offset-2 hover:underline"
      >
        Profile is ready — open the full page for the breakdown.
      </Link>
    );
  }

  return (
    <div className="space-y-3 text-sm">
      {fitSummary && (
        <div>
          <div className="mb-1.5 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-soft">
            Strategic fit
            {recAction && (
              <Pill variant="accent">{recAction.replace(/_/g, " ")}</Pill>
            )}
          </div>
          <p className="line-clamp-3 text-[13px] leading-relaxed text-muted">
            {fitSummary}
          </p>
        </div>
      )}

      {topSignals.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-soft">
            Top signals
          </div>
          <ul className="space-y-1.5">
            {topSignals.map((s) => (
              <li key={s.id} className="flex items-start gap-2 text-[13px]">
                <span className="mt-0.5 shrink-0 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-emerald-700">
                  {s.type}
                </span>
                <span className="line-clamp-1 text-muted">{s.headline}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────────────────

function formatStamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const now = new Date();
  const ms = now.getTime() - d.getTime();
  const sec = Math.round(ms / 1000);
  if (sec < 60) return "just now";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 7) return `${day}d ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
