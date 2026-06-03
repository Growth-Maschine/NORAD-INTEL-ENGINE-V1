import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowLeft,
  ChevronRight,
  Globe2,
  Play,
  Plus,
  Settings,
  Sparkles,
  Target,
  Tags,
  Telescope,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { Topbar } from "@/components/layout/Topbar";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { PageBody } from "@/components/ui/PageBody";
import {
  getWebDiscoveryRun,
  getWebDiscoveryCluster,
  listWebDiscoveryClusterRuns,
  listWebDiscoveryQueries,
  startWebDiscoveryClusterRun,
  updateWebDiscoveryCluster,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const TABS = ["overview", "queries", "results", "settings"] as const;
type TabKey = (typeof TABS)[number];

export default function WebDiscoveryCluster() {
  const { clusterId = "" } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const runStorageKey = `web_discovery_active_run_${clusterId}`;
  const [tab, setTab] = useState<TabKey>("overview");
  const [activeRunId, setActiveRunId] = useState<string>("");
  const [confirmRunAll, setConfirmRunAll] = useState(false);

  const clusterQuery = useQuery({
    queryKey: ["web-discovery-cluster", clusterId],
    queryFn: () => getWebDiscoveryCluster(clusterId),
    enabled: !!clusterId,
  });
  const queriesQuery = useQuery({
    queryKey: ["web-discovery-queries", clusterId],
    queryFn: () => listWebDiscoveryQueries(clusterId),
    enabled: !!clusterId,
  });
  const runsQuery = useQuery({
    queryKey: ["web-discovery-runs", clusterId],
    queryFn: () => listWebDiscoveryClusterRuns(clusterId, 10),
    enabled: !!clusterId,
    refetchInterval: 5000,
  });
  const activeRunQuery = useQuery({
    queryKey: ["web-discovery-run", activeRunId],
    queryFn: () => getWebDiscoveryRun(activeRunId),
    enabled: !!activeRunId,
    refetchInterval: (q) => {
      const run = q.state.data;
      if (!run) return 5000;
      return ["queued", "researching", "synthesizing"].includes(run.status) ? 3000 : false;
    },
  });

  const cluster = clusterQuery.data;
  const queries = queriesQuery.data ?? [];
  const [edit, setEdit] = useState(false);
  const [includeDraft, setIncludeDraft] = useState("");
  const [excludeDraft, setExcludeDraft] = useState("");
  const [draft, setDraft] = useState({
    name: cluster?.name ?? "",
    description: cluster?.description ?? "",
    is_active: cluster?.is_active ?? true,
    include_keywords: cluster?.include_keywords ?? [],
    exclude_keywords: cluster?.exclude_keywords ?? [],
    geography_focus: cluster?.geography_focus ?? [],
    source_preferences: cluster?.source_preferences ?? [],
    signal_priorities: cluster?.signal_priorities ?? [],
  });

  const saveMut = useMutation({
    mutationFn: () =>
      updateWebDiscoveryCluster(clusterId, {
        name: draft.name,
        description: draft.description,
        is_active: draft.is_active,
        include_keywords: mergeTokens(draft.include_keywords, includeDraft),
        exclude_keywords: mergeTokens(draft.exclude_keywords, excludeDraft),
        geography_focus: draft.geography_focus,
        source_preferences: draft.source_preferences,
        signal_priorities: draft.signal_priorities,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["web-discovery-cluster", clusterId] });
      qc.invalidateQueries({ queryKey: ["web-discovery-clusters"] });
      setEdit(false);
      toast.success("Cluster updated");
    },
    onError: (err) => {
      toast.error("Failed to update cluster", { description: (err as Error).message });
    },
  });
  const runMut = useMutation({
    mutationFn: () => startWebDiscoveryClusterRun(clusterId),
    onSuccess: (created) => {
      setActiveRunId(created.run_id);
      if (clusterId) localStorage.setItem(runStorageKey, created.run_id);
      qc.invalidateQueries({ queryKey: ["web-discovery-runs", clusterId] });
      toast.success("Cluster run started", {
        description: "Run continues in background even if you leave this page.",
      });
      setTab("results");
    },
    onError: (err) => {
      toast.error("Failed to start run", { description: (err as Error).message });
    },
  });
  useEffect(() => {
    if (!cluster) return;
    setDraft({
      name: cluster.name,
      description: cluster.description ?? "",
      is_active: cluster.is_active,
        include_keywords: cluster.include_keywords,
        exclude_keywords: cluster.exclude_keywords,
        geography_focus: cluster.geography_focus,
        source_preferences: cluster.source_preferences,
        signal_priorities: cluster.signal_priorities,
    });
      setIncludeDraft("");
      setExcludeDraft("");
  }, [cluster]);

  useEffect(() => {
    if (!clusterId) return;
    const stored = localStorage.getItem(runStorageKey);
    if (stored) setActiveRunId(stored);
  }, [clusterId, runStorageKey]);

  useEffect(() => {
    const latest = runsQuery.data?.[0];
    if (!latest || activeRunId) return;
    if (["queued", "researching", "synthesizing"].includes(latest.status)) {
      setActiveRunId(latest.id);
      localStorage.setItem(runStorageKey, latest.id);
    }
  }, [runsQuery.data, activeRunId, runStorageKey]);

  useEffect(() => {
    const status = activeRunQuery.data?.status;
    if (!status) return;
    if (!["queued", "researching", "synthesizing"].includes(status)) {
      localStorage.removeItem(runStorageKey);
    }
  }, [activeRunQuery.data?.status, runStorageKey]);

  if (clusterQuery.isLoading) {
    return (
      <>
        <Topbar title="Web Discovery" subtitle="Loading cluster..." />
        <PageBody>
          <div className="rounded-xl border border-border bg-white p-6 text-sm text-soft">
            Loading cluster...
          </div>
        </PageBody>
      </>
    );
  }

  if (!cluster) {
    return (
      <>
        <Topbar title="Web Discovery" subtitle="Cluster not found." />
        <PageBody>
          <div className="rounded-xl border border-border bg-white p-6 text-sm text-soft">
            Cluster not found.
          </div>
        </PageBody>
      </>
    );
  }

  return (
    <>
      <Topbar title="Web Discovery" subtitle="Cluster command center for Exa query orchestration." />
      <PageBody>
        <div className="mb-4">
          <Link to="/discover-web" className="inline-flex items-center gap-2 text-sm text-muted hover:text-ink">
            <ArrowLeft className="h-4 w-4" />
            Back to Clusters
          </Link>
        </div>

        <section className="rounded-2xl border border-border bg-gradient-to-b from-white to-[#FCFCFB] p-5 shadow-soft sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#5E8E4A]">
                Cluster Command Center
              </p>
              <h1 className="mt-1 text-3xl font-semibold text-ink">{cluster.name}</h1>
              <div className="mt-2 flex items-center gap-2">
                <Badge active={cluster.is_active}>{cluster.is_active ? "Active" : "Paused"}</Badge>
              </div>
              <p className="mt-2 max-w-3xl text-sm text-muted">
                {cluster.description || "No description provided."}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                className="transition-all duration-200 hover:-translate-y-0.5"
                onClick={() => setConfirmRunAll(true)}
                disabled={runMut.isPending}
              >
                <Play className="h-4 w-4" />
                {runMut.isPending ? "Starting..." : "Run All Cluster Queries"}
              </Button>
              <Button
                className="transition-all duration-200 hover:-translate-y-0.5"
                onClick={() => navigate(`/discover-web/clusters/${cluster.id}/queries/new`)}
              >
                <Plus className="h-4 w-4" />
                Add Query
              </Button>
              <Button
                variant="secondary"
                className="transition-all duration-200 hover:-translate-y-0.5"
                onClick={() => setTab("settings")}
              >
                <Settings className="h-4 w-4" />
                Settings
              </Button>
            </div>
          </div>
          {activeRunQuery.data ? (
            <div className="mt-3 rounded-lg border border-border bg-white px-3 py-2">
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="inline-flex items-center gap-1.5 font-medium text-ink">
                  <Activity className="h-4 w-4 text-accent" />
                  Active run: {activeRunQuery.data.status}
                </span>
                <span className="text-xs text-soft">{activeRunQuery.data.progress_pct}%</span>
              </div>
              <div className="mt-2 h-1.5 w-full rounded-full bg-[#EFEDE8]">
                <div
                  className="h-1.5 rounded-full bg-accent transition-all"
                  style={{ width: `${Math.max(0, Math.min(100, activeRunQuery.data.progress_pct))}%` }}
                />
              </div>
            </div>
          ) : null}

          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <StatCard
              icon={Telescope}
              label="Queries"
              value={String(queries.length)}
              hint="Search definitions inside cluster"
            />
            <StatCard
              icon={Sparkles}
              label="Signals"
              value={String(cluster.signal_count)}
              hint="Detection outcomes"
            />
            <StatCard
              icon={Target}
              label="Status"
              value={cluster.is_active ? "Live" : "Paused"}
              hint="Run readiness"
            />
          </div>

          <div className="mt-5 inline-flex rounded-xl border border-border bg-[#FAFAFA] p-1">
            {TABS.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-sm capitalize transition-all duration-200",
                  tab === key
                    ? "bg-white shadow-soft text-ink"
                    : "text-muted hover:-translate-y-0.5 hover:text-ink",
                )}
              >
                {key}
              </button>
            ))}
          </div>

          {tab === "overview" && (
            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              <Box title="Included Keywords" values={cluster.include_keywords} icon={Tags} />
              <Box title="Excluded Keywords" values={cluster.exclude_keywords} icon={Tags} />
              <Box title="Target Geography" values={cluster.geography_focus} icon={Globe2} />
              <Box title="Source Preferences" values={cluster.source_preferences} icon={Telescope} />
              <div className="lg:col-span-2">
                <Box title="Signal Priorities" values={cluster.signal_priorities} icon={Sparkles} />
              </div>
            </div>
          )}

          {tab === "queries" && (
            <div className="mt-5">
              {queriesQuery.isLoading ? (
                <div className="text-sm text-soft">Loading queries...</div>
              ) : queries.length === 0 ? (
                <div className="rounded-xl border border-dashed border-border px-4 py-10 text-center">
                  <p className="text-sm font-medium text-ink">No search queries created yet.</p>
                  <p className="mt-1 text-xs text-soft">
                    Search queries define the specific Exa searches running inside this cluster.
                  </p>
                  <Button className="mt-4" onClick={() => navigate(`/discover-web/clusters/${cluster.id}/queries/new`)}>
                    <Plus className="h-4 w-4" />
                    Add Query
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  {queries.map((query) => (
                    <article
                      key={query.id}
                      className="group relative cursor-pointer overflow-hidden rounded-xl border border-border bg-gradient-to-br from-white to-[#FCFCFB] p-3 transition-all duration-200 hover:-translate-y-1 hover:border-accent/50 hover:shadow-lift"
                      onClick={() =>
                        navigate(`/discover-web/clusters/${cluster.id}/queries/${query.id}`)
                      }
                    >
                      <span className="pointer-events-none absolute inset-y-0 left-0 w-1 bg-accent/80 opacity-0 transition group-hover:opacity-100" />
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="font-semibold text-ink transition group-hover:text-accent">
                            {query.label}
                          </h3>
                          <p className="text-xs text-muted">{query.search_query}</p>
                        </div>
                        <div className="text-right text-xs text-soft">
                          <p>{query.search_type}</p>
                          <p>{query.num_results} results</p>
                          <span className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-accent opacity-0 transition group-hover:opacity-100">
                            Open query
                            <ChevronRight className="h-3.5 w-3.5" />
                          </span>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === "results" && (
            <div className="mt-5 space-y-3">
              {activeRunQuery.data ? (
                <article className="rounded-xl border border-border bg-white p-4 shadow-soft">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-ink">Live run status</p>
                    <Badge active={activeRunQuery.data.status === "completed"}>
                      {activeRunQuery.data.status}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-soft">
                    This run continues in background even if you switch pages.
                  </p>
                  <div className="mt-3 h-2 w-full rounded-full bg-[#EFEDE8]">
                    <div
                      className="h-2 rounded-full bg-accent transition-all"
                      style={{
                        width: `${Math.max(0, Math.min(100, activeRunQuery.data.progress_pct))}%`,
                      }}
                    />
                  </div>
                  <div className="mt-2 text-xs text-muted">
                    Progress: {activeRunQuery.data.progress_pct}% · Started{" "}
                    {activeRunQuery.data.started_at
                      ? new Date(activeRunQuery.data.started_at).toLocaleString()
                      : "pending"}
                  </div>
                </article>
              ) : null}
              <article className="rounded-xl border border-border bg-[#FCFCFB] p-4">
                <p className="text-sm font-semibold text-ink">Queries</p>
                {!queries.length ? (
                  <p className="mt-2 text-xs text-soft">No queries yet.</p>
                ) : (
                  <div className="mt-2 space-y-2">
                    {queries.map((query) => (
                      <button
                        key={query.id}
                        type="button"
                        onClick={() =>
                          navigate(
                            `/discover-web/clusters/${cluster.id}/queries/${query.id}/results`,
                          )
                        }
                        className="group flex w-full items-center justify-between rounded-lg border border-border bg-white px-3 py-2.5 text-left text-xs transition hover:-translate-y-0.5 hover:border-accent/50 hover:shadow-soft"
                      >
                        <div>
                          <p className="font-medium text-ink transition group-hover:text-accent">
                            {query.label}
                          </p>
                          <p className="text-soft">
                            {query.search_type} · {query.num_results} results
                          </p>
                        </div>
                        <span className="inline-flex items-center gap-1 font-medium text-accent">
                          View results
                          <ChevronRight className="h-3.5 w-3.5" />
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </article>
            </div>
          )}

          {tab === "settings" && (
            <div className="mt-5 space-y-4">
              <section className="rounded-xl border border-border bg-[#FCFCFB] p-4 shadow-soft">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-ink">Basic Information</h3>
                  <span className="text-xs text-soft">Name, description, and status</span>
                </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="md:col-span-2">
                  <Label>Cluster Name</Label>
                  <input
                    value={draft.name}
                    onChange={(e) => setDraft((prev) => ({ ...prev, name: e.target.value }))}
                    disabled={!edit}
                    className="h-10 w-full rounded-lg border border-border bg-white px-3 text-sm outline-none"
                  />
                </div>
                <div className="md:col-span-2">
                  <Label>Description</Label>
                  <textarea
                    rows={3}
                    value={draft.description}
                    onChange={(e) =>
                      setDraft((prev) => ({ ...prev, description: e.target.value }))
                    }
                    disabled={!edit}
                    className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm outline-none"
                  />
                </div>
                <div className="md:col-span-2 flex items-center justify-between rounded-lg border border-border bg-white px-3 py-2">
                  <span className="text-sm text-muted">Active</span>
                  <input
                    type="checkbox"
                    checked={draft.is_active}
                    disabled={!edit}
                    onChange={(e) =>
                      setDraft((prev) => ({ ...prev, is_active: e.target.checked }))
                    }
                    className="h-4 w-4 accent-[#0E9F6E]"
                  />
                </div>
              </div>
              </section>

              <section className="rounded-xl border border-border bg-[#FCFCFB] p-4 shadow-soft">
                <h3 className="mb-3 text-sm font-semibold text-ink">Cluster Rules</h3>
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <Label>Include Keywords</Label>
                    <KeywordEditor
                      values={draft.include_keywords}
                      draft={includeDraft}
                      setDraft={setIncludeDraft}
                      onChange={(values) => setDraft((prev) => ({ ...prev, include_keywords: values }))}
                      disabled={!edit}
                    />
                  </div>
                  <div>
                    <Label>Exclusion Keywords</Label>
                    <KeywordEditor
                      values={draft.exclude_keywords}
                      draft={excludeDraft}
                      setDraft={setExcludeDraft}
                      onChange={(values) => setDraft((prev) => ({ ...prev, exclude_keywords: values }))}
                      disabled={!edit}
                    />
                  </div>
                  <div>
                    <Label>Geography Focus</Label>
                    <SelectChips
                      options={["United States", "Canada", "United Kingdom", "Europe", "Middle East", "Asia Pacific"]}
                      selected={draft.geography_focus}
                      onToggle={(value) =>
                        setDraft((prev) => ({
                          ...prev,
                          geography_focus: toggleInArray(prev.geography_focus, value),
                        }))
                      }
                      disabled={!edit}
                    />
                  </div>
                  <div>
                    <Label>Source Preferences</Label>
                    <SelectChips
                      options={["News", "Company Websites", "Scientific Papers", "Industry Blogs", "Social"]}
                      selected={draft.source_preferences}
                      onToggle={(value) =>
                        setDraft((prev) => ({
                          ...prev,
                          source_preferences: toggleInArray(prev.source_preferences, value),
                        }))
                      }
                      disabled={!edit}
                    />
                  </div>
                </div>
              </section>

              <section className="rounded-xl border border-border bg-[#FCFCFB] p-4 shadow-soft">
                <h3 className="mb-3 text-sm font-semibold text-ink">Signal Detection</h3>
                <div className="grid gap-2 sm:grid-cols-2">
                  {[
                    "New product launches",
                    "Funding announcements",
                    "Acquisitions / partnerships",
                    "Regulatory updates",
                    "Scientific studies",
                    "Patent activity",
                    "Retail expansion",
                    "Consumer traction",
                  ].map((signal) => {
                    const active = draft.signal_priorities.includes(signal);
                    return (
                      <button
                        key={signal}
                        type="button"
                        disabled={!edit}
                        onClick={() =>
                          setDraft((prev) => ({
                            ...prev,
                            signal_priorities: toggleInArray(prev.signal_priorities, signal),
                          }))
                        }
                        className={cn(
                          "rounded-lg border px-3 py-2 text-left text-sm transition-all duration-200",
                          active
                            ? "border-[#BDE6D3] bg-[#ECF8F1] text-[#155A3E]"
                            : "border-border bg-white text-ink hover:border-soft",
                          !edit && "cursor-not-allowed opacity-70",
                        )}
                      >
                        {signal}
                      </button>
                    );
                  })}
                </div>
              </section>

              <div className="mt-4 flex justify-end gap-2">
                {!edit ? (
                  <Button variant="secondary" onClick={() => setEdit(true)}>
                    Edit
                  </Button>
                ) : (
                  <>
                    <Button
                      variant="secondary"
                      onClick={() => {
                        if (!cluster) return;
                        setDraft({
                          name: cluster.name,
                          description: cluster.description ?? "",
                          is_active: cluster.is_active,
                          include_keywords: cluster.include_keywords,
                          exclude_keywords: cluster.exclude_keywords,
                          geography_focus: cluster.geography_focus,
                          source_preferences: cluster.source_preferences,
                          signal_priorities: cluster.signal_priorities,
                        });
                        setIncludeDraft("");
                        setExcludeDraft("");
                        setEdit(false);
                      }}
                    >
                      Cancel
                    </Button>
                    <Button onClick={() => saveMut.mutate()} disabled={saveMut.isPending}>
                      {saveMut.isPending ? "Saving..." : "Save Changes"}
                    </Button>
                  </>
                )}
              </div>
            </div>
          )}
        </section>
      </PageBody>
      <ConfirmDialog
        open={confirmRunAll}
        onOpenChange={setConfirmRunAll}
        title="Run all active queries in this cluster?"
        description="This starts a cluster-wide run and executes all active queries. You can monitor each query from its own query page."
        confirmText={runMut.isPending ? "Starting..." : "Run all queries"}
        cancelText="Cancel"
        busy={runMut.isPending}
        onConfirm={() => runMut.mutate()}
      />
    </>
  );
}

function Badge({
  children,
  active,
}: {
  children: React.ReactNode;
  active?: boolean;
}) {
  return (
    <span
      className={cn(
        "rounded-full border px-2 py-0.5 text-xs",
        active
          ? "border-[#CFE8C6] bg-[#ECF8E8] text-[#2F7A33]"
          : "border-[#E8D7DC] bg-[#FFF0F5] text-[#8F4358]",
      )}
    >
      {children}
    </span>
  );
}

function Box({
  title,
  values,
  icon: Icon,
}: {
  title: string;
  values: string[];
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <section className="rounded-xl border border-border bg-[#FCFCFB] p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-soft">
      <div className="flex items-center gap-1.5">
        <Icon className="h-4 w-4 text-soft" />
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
      </div>
      {values.length ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {values.map((value) => (
            <span
              key={value}
              className="rounded-full border border-border bg-white px-2 py-1 text-xs text-ink"
            >
              {value}
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-1 text-xs text-soft">Not set.</p>
      )}
    </section>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <article className="rounded-lg border border-border bg-white px-3 py-2 shadow-soft">
      <div className="flex items-center gap-1.5 text-soft">
        <Icon className="h-3.5 w-3.5" />
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em]">{label}</p>
      </div>
      <p className="mt-1 text-lg font-semibold text-ink">{value}</p>
      <p className="text-[11px] text-soft">{hint}</p>
    </article>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <p className="mb-1 text-[12px] font-semibold text-muted">{children}</p>;
}

function KeywordEditor({
  values,
  draft,
  setDraft,
  onChange,
  disabled,
}: {
  values: string[];
  draft: string;
  setDraft: (v: string) => void;
  onChange: (values: string[]) => void;
  disabled: boolean;
}) {
  const commitDraft = () => {
    const next = mergeTokens(values, draft);
    if (next.length !== values.length) onChange(next);
    setDraft("");
  };
  return (
    <div className="rounded-lg border border-border bg-white p-2">
      <div className="mb-2 flex flex-wrap gap-1.5">
        {values.map((value) => (
          <button
            key={value}
            type="button"
            disabled={disabled}
            onClick={() => onChange(values.filter((v) => v !== value))}
            className={cn(
              "rounded-full border border-border bg-tint px-2 py-0.5 text-xs text-ink transition hover:scale-[1.02] hover:bg-soft/30",
              disabled && "cursor-not-allowed opacity-70",
            )}
          >
            {value} ×
          </button>
        ))}
      </div>
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commitDraft}
        disabled={disabled}
        onKeyDown={(e) => {
          if (!["Enter", "Tab", ",", " "].includes(e.key)) return;
          e.preventDefault();
          commitDraft();
        }}
        placeholder="Type and press Space"
        className="h-9 w-full rounded-md border border-border px-2.5 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15 disabled:opacity-60"
      />
    </div>
  );
}

function SelectChips({
  options,
  selected,
  onToggle,
  disabled,
}: {
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2 rounded-lg border border-border bg-white p-2">
      {options.map((option) => {
        const active = selected.includes(option);
        return (
          <button
            key={option}
            type="button"
            disabled={disabled}
            onClick={() => onToggle(option)}
            className={cn(
              "rounded-full border px-2.5 py-1 text-xs transition-all duration-200 hover:-translate-y-0.5",
              active
                ? "border-[#BDE6D3] bg-[#ECF8F1] text-[#155A3E] shadow-soft"
                : "border-border bg-[#FAFAFA] text-muted hover:border-soft",
              disabled && "cursor-not-allowed opacity-70",
            )}
          >
            {option}
          </button>
        );
      })}
    </div>
  );
}

function tokenizeDraft(input: string): string[] {
  return input
    .split(/[\s,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function mergeTokens(values: string[], draft: string): string[] {
  const existing = new Set(values.map((item) => item.toLowerCase()));
  const out = [...values];
  tokenizeDraft(draft).forEach((token) => {
    const key = token.toLowerCase();
    if (existing.has(key)) return;
    existing.add(key);
    out.push(token);
  });
  return out;
}

function toggleInArray(values: string[], value: string): string[] {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}
