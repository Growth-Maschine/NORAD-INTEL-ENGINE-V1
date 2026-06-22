import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Loader2,
  Radio,
  Search,
  XCircle,
  XOctagon,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Topbar } from "@/components/layout/Topbar";
import { RunFeed } from "@/components/runs/RunFeed";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageBody } from "@/components/ui/PageBody";
import { Pill } from "@/components/ui/Pill";
import {
  cancelResearchRun,
  getCompany,
  listCompanyFeed,
  listDiscoveredCompanies,
  listWebDiscoveryClusters,
  startResearchRun,
  type CompanyDetail,
  type CompanyFeedRow,
  type DiscoveredCompanyRow,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type CompaniesTab = "profiles" | "discovered";

/**
 * Companies — research command center.
 *
 * Layout: Activity log on the LEFT (matches the user's mental model — the
 * log is the *origin* of what they're looking at; the company list is the
 * result). Each row collapses to a one-liner and expands to show the engine
 * summary. The Activity panel always tracks whichever row the
 * user is paying attention to (the most-recently expanded one) so logs stay
 * attached to their run instead of disappearing when the run finishes.
 *
 * Sort: live runs first (amber pulse), then by latest-run recency desc.
 */
export default function Companies() {
  const [tab, setTab] = useState<CompaniesTab>("profiles");

  return (
    <>
      <Topbar
        title="Companies"
        subtitle={
          tab === "profiles"
            ? "Deep research profiles and live run activity."
            : "Companies extracted from Web Discovery articles."
        }
      />
      <PageBody>
        <div className="mb-5 flex flex-wrap gap-2">
          <TabButton active={tab === "profiles"} onClick={() => setTab("profiles")}>
            Profiles
          </TabButton>
          <TabButton active={tab === "discovered"} onClick={() => setTab("discovered")}>
            Discovered
          </TabButton>
        </div>

        {tab === "profiles" ? <ProfilesTab /> : <DiscoveredTab />}
      </PageBody>
    </>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-lg border px-3 py-1.5 text-sm font-medium transition",
        active
          ? "border-ink bg-ink text-white"
          : "border-border bg-white text-muted hover:border-ink/30 hover:text-ink",
      )}
    >
      {children}
    </button>
  );
}

function ProfilesTab() {
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
          description="Run Deep research on a company from Web Discovery results or the Discovered tab. Completed runs show up here."
        />
      )}

      {rows.length > 0 && (
        <section className="grid gap-6 lg:grid-cols-[340px_1fr]">
          <aside className="lg:sticky lg:top-4 lg:h-[calc(100vh-6rem)]">
            <RunFeed runId={focusedRunId} historical={!focusedIsLive} />
          </aside>

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
    </>
  );
}

function DiscoveredTab() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [clusterId, setClusterId] = useState("");
  const [profileFilter, setProfileFilter] = useState<"all" | "yes" | "no">("all");
  const [profilingId, setProfilingId] = useState<string | null>(null);

  const clustersQuery = useQuery({
    queryKey: ["web-discovery-clusters"],
    queryFn: listWebDiscoveryClusters,
  });
  const clusters = clustersQuery.data?.clusters ?? [];

  const discoveredQuery = useQuery({
    queryKey: ["discovered-companies", search, clusterId, profileFilter],
    queryFn: () =>
      listDiscoveredCompanies({
        limit: 100,
        search: search.trim() || undefined,
        cluster_id: clusterId || undefined,
        has_profile:
          profileFilter === "all"
            ? undefined
            : profileFilter === "yes",
      }),
    refetchInterval: 15000,
  });
  const rows = discoveredQuery.data ?? [];

  const onProfile = async (row: DiscoveredCompanyRow) => {
    setProfilingId(row.id);
    try {
      const run = await startResearchRun({
        company_name: row.company_name,
        domain_hint: row.website ?? undefined,
        company_id: row.id,
      });
      toast.success(`Research started for ${row.company_name}`);
      navigate(`/runs/${run.run_id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start research");
    } finally {
      setProfilingId(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-soft" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search company name…"
            className="w-full rounded-lg border border-border bg-white py-2 pl-9 pr-3 text-sm outline-none ring-ink/20 focus:ring-2"
          />
        </label>
        <select
          value={clusterId}
          onChange={(e) => setClusterId(e.target.value)}
          className="rounded-lg border border-border bg-white px-3 py-2 text-sm outline-none ring-ink/20 focus:ring-2"
        >
          <option value="">All clusters</option>
          {clusters.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <select
          value={profileFilter}
          onChange={(e) =>
            setProfileFilter(e.target.value as "all" | "yes" | "no")
          }
          className="rounded-lg border border-border bg-white px-3 py-2 text-sm outline-none ring-ink/20 focus:ring-2"
        >
          <option value="all">All mentions</option>
          <option value="no">Not profiled</option>
          <option value="yes">Has profile</option>
        </select>
      </div>

      {discoveredQuery.isLoading && (
        <div className="rounded-xl border border-dashed border-border bg-white px-6 py-16 text-center text-sm text-soft">
          <Loader2 className="mx-auto mb-3 h-5 w-5 animate-spin" />
          Loading discovered companies…
        </div>
      )}

      {!discoveredQuery.isLoading && rows.length === 0 && (
        <EmptyState
          icon={Building2}
          title="No discovered companies yet"
          description="Run Web Discovery queries with Sonnet enrich enabled. Companies mentioned in articles appear here with a stable ID linked to the source story."
        />
      )}

      {rows.length > 0 && (
        <ul className="space-y-3">
          {rows.map((row) => (
            <li
              key={row.id}
              className="rounded-xl border border-border/80 bg-white px-4 py-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-ink">{row.company_name}</p>
                    {row.canonical_card_id ? (
                      <Pill variant="accent">Profiled</Pill>
                    ) : null}
                    {row.cluster_name ? (
                      <Pill>{row.cluster_name}</Pill>
                    ) : null}
                  </div>
                  {row.discovery_role ? (
                    <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-wider text-soft">
                      {row.discovery_role}
                    </p>
                  ) : null}
                  {row.discovery_context ? (
                    <p className="mt-1.5 text-sm leading-relaxed text-muted">
                      {row.discovery_context}
                    </p>
                  ) : null}
                  {(row.industry || row.headquarters_country) && (
                    <p className="mt-1 text-xs text-soft">
                      {[row.industry, row.headquarters_country]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  )}
                  {row.article_title && row.article_url ? (
                    <a
                      href={row.article_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2 inline-flex items-center gap-1 text-xs text-muted underline-offset-2 hover:underline"
                    >
                      <ExternalLink className="h-3 w-3" />
                      {row.article_title}
                    </a>
                  ) : row.article_title ? (
                    <p className="mt-2 text-xs text-soft">{row.article_title}</p>
                  ) : null}
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2">
                  {row.canonical_card_id ? (
                    <Link
                      to={`/companies/${row.id}`}
                      className="text-xs font-medium text-ink underline-offset-2 hover:underline"
                    >
                      Open profile
                    </Link>
                  ) : (
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      disabled={profilingId === row.id}
                      onClick={() => onProfile(row)}
                    >
                      {profilingId === row.id ? "Starting…" : "Deep research"}
                    </Button>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
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
// Expanded detail — strategic fit excerpt + open page CTA
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
          `flight may still finish, but no company / card will be ` +
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
  const c = detail.card?.card ?? {};
  const fit = c.strategic_fit ?? {};
  const fitSummary: string | undefined = fit.fit_summary?.value;

  if (!fitSummary) {
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
      <div>
        <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-soft">
          Strategic fit
        </div>
        <p className="line-clamp-3 text-[13px] leading-relaxed text-muted">
          {fitSummary}
        </p>
      </div>
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
