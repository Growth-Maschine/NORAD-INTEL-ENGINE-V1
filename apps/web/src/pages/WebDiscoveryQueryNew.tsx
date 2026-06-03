import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowLeft, ChevronDown, Info, Search } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { Topbar } from "@/components/layout/Topbar";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { PageBody } from "@/components/ui/PageBody";
import {
  createWebDiscoveryQuery,
  getWebDiscoveryRun,
  getWebDiscoveryCluster,
  getWebDiscoveryQuery,
  listWebDiscoveryClusterRuns,
  recentRunEvents,
  startWebDiscoveryClusterRun,
  subscribeRunEvents,
  type RunEvent,
  type WebDiscoveryQueryInput,
  type WebDiscoveryRun,
  updateWebDiscoveryQuery,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const SEARCH_TYPES: Array<{
  value: NonNullable<WebDiscoveryQueryInput["search_type"]>;
  label: string;
  hint: string;
}> = [
  { value: "instant", label: "Instant", hint: "~200ms" },
  { value: "fast", label: "Fast", hint: "~450ms" },
  { value: "auto", label: "Auto", hint: "~1s" },
  { value: "deep-lite", label: "Deep Lite", hint: "2-6s" },
  { value: "deep", label: "Deep", hint: "4-18s" },
  { value: "deep-reasoning", label: "Deep Reasoning", hint: "12-40s" },
];

type PresetKey = "fast_monitor" | "balanced_auto" | "deep_research";
type LivecrawlAgeKey = "cache_only" | "2h" | "24h" | "72h" | "7d";
type LivecrawlTimeoutKey = "7s" | "10s" | "20s" | "30s";

const RESULT_CATEGORY_OPTIONS = [
  { value: "", label: "No category filter" },
  { value: "company", label: "Company" },
  { value: "news", label: "News" },
  { value: "research_paper", label: "Research Paper" },
  { value: "pdf", label: "PDF" },
  { value: "github", label: "GitHub" },
  { value: "tweet", label: "Tweet" },
] as const;

const LIVECRAWL_AGE_OPTIONS: Array<{ value: LivecrawlAgeKey; label: string; hours: number | null }> = [
  { value: "cache_only", label: "Cache only", hours: null },
  { value: "2h", label: "Last 2 hours", hours: 2 },
  { value: "24h", label: "Last 24 hours", hours: 24 },
  { value: "72h", label: "Last 72 hours", hours: 72 },
  { value: "7d", label: "Last 7 days", hours: 168 },
];

const LIVECRAWL_TIMEOUT_OPTIONS: Array<{ value: LivecrawlTimeoutKey; label: string; ms: number }> = [
  { value: "7s", label: "7 seconds", ms: 7000 },
  { value: "10s", label: "10 seconds", ms: 10000 },
  { value: "20s", label: "20 seconds", ms: 20000 },
  { value: "30s", label: "30 seconds", ms: 30000 },
];

const PRESETS: Array<{
  key: PresetKey;
  label: string;
  hint: string;
  apply: (curr: QueryFormState) => QueryFormState;
}> = [
  {
    key: "fast_monitor",
    label: "Fast Monitor",
    hint: "high refresh, low latency, compact content",
    apply: (curr) => ({
      ...curr,
      search_type: "fast",
      num_results: 12,
      content_highlights: true,
      highlights_max_chars: 2500,
      content_text: false,
      content_summary: false,
      max_age_hours: 2,
      livecrawl_timeout_ms: 7000,
      stream_response: false,
    }),
  },
  {
    key: "balanced_auto",
    label: "Balanced",
    hint: "recommended default for most discovery clusters",
    apply: (curr) => ({
      ...curr,
      search_type: "auto",
      num_results: 10,
      content_highlights: true,
      highlights_max_chars: 4000,
      content_text: false,
      content_summary: true,
      summary_max_chars: 1200,
      max_age_hours: 24,
      livecrawl_timeout_ms: 10000,
      stream_response: false,
    }),
  },
  {
    key: "deep_research",
    label: "Deep Research",
    hint: "slower, richer output, broader crawl depth",
    apply: (curr) => ({
      ...curr,
      search_type: "deep",
      num_results: 20,
      content_highlights: true,
      highlights_max_chars: 6000,
      content_text: true,
      text_max_chars: 12000,
      content_summary: true,
      summary_max_chars: 2000,
      max_age_hours: 168,
      livecrawl_timeout_ms: 20000,
      stream_response: false,
    }),
  },
];

type QueryFormState = {
  label: string;
  search_query: string;
  search_type: NonNullable<WebDiscoveryQueryInput["search_type"]>;
  num_results: number;
  category: string;
  user_location: string;
  content_highlights: boolean;
  highlights_max_chars: number | null;
  highlights_guiding_query: string;
  content_text: boolean;
  text_max_chars: number | null;
  text_main_content_only: boolean;
  content_summary: boolean;
  summary_max_chars: number | null;
  max_age_hours: number | null;
  livecrawl_timeout_ms: number;
  content_moderation: boolean;
  stream_response: boolean;
  published_after: string;
  published_before: string;
  crawled_after: string;
  crawled_before: string;
  system_prompt: string;
};

export default function WebDiscoveryQueryNew() {
  const { clusterId = "", queryId = "" } = useParams();
  const isEditMode = !!queryId;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const activeRunStorageKey = isEditMode
    ? `web_discovery_active_run_${clusterId}_${queryId}`
    : "";
  const autoPrefillAppliedRef = useRef(false);
  const redirectedRunRef = useRef<string | null>(null);
  const [userInitiatedRun, setUserInitiatedRun] = useState(false);
  const [includeDomains, setIncludeDomains] = useState<string[]>([]);
  const [excludeDomains, setExcludeDomains] = useState<string[]>([]);
  const [additionalQueries, setAdditionalQueries] = useState<string[]>([]);
  const [activeRunId, setActiveRunId] = useState("");
  const [runLaunching, setRunLaunching] = useState(false);
  const [confirmRunQuery, setConfirmRunQuery] = useState(false);
  const [feedEvents, setFeedEvents] = useState<RunEvent[]>([]);
  const [feedConnected, setFeedConnected] = useState(false);
  const [lastCreatedLabel, setLastCreatedLabel] = useState("");
  const [preset, setPreset] = useState<PresetKey>("balanced_auto");

  const [form, setForm] = useState<QueryFormState>({
    label: "",
    search_query: "",
    search_type: "auto",
    num_results: 10,
    category: "",
    user_location: "",
    content_highlights: true,
    highlights_max_chars: 4000,
    highlights_guiding_query: "",
    content_text: false,
    text_max_chars: 5000,
    text_main_content_only: true,
    content_summary: false,
    summary_max_chars: 1200,
    max_age_hours: null,
    livecrawl_timeout_ms: 10000,
    content_moderation: false,
    stream_response: false,
    published_after: "",
    published_before: "",
    crawled_after: "",
    crawled_before: "",
    system_prompt: "",
  });

  const clusterQuery = useQuery({
    queryKey: ["web-discovery-cluster", clusterId],
    queryFn: () => getWebDiscoveryCluster(clusterId),
    enabled: !!clusterId,
  });
  const queryDetailQuery = useQuery({
    queryKey: ["web-discovery-query", queryId],
    queryFn: () => getWebDiscoveryQuery(queryId),
    enabled: !!queryId,
  });
  const clusterRunsQuery = useQuery({
    queryKey: ["web-discovery-runs", clusterId],
    queryFn: () => listWebDiscoveryClusterRuns(clusterId, 20),
    enabled: !!clusterId && isEditMode,
    refetchInterval: (q) => {
      const rows = q.state.data ?? [];
      const tracking = activeRunId
        ? rows.find((r) => r.id === activeRunId)
        : rows[0];
      if (!tracking) return false;
      return ["queued", "researching", "synthesizing"].includes(tracking.status)
        ? 3000
        : false;
    },
  });

  const lastQueryRunId = useMemo(() => {
    if (!isEditMode || !queryId) return null;
    const rows = clusterRunsQuery.data ?? [];
    for (const run of rows) {
      if (runIncludesQuery(run, queryId)) return run.id;
    }
    return null;
  }, [clusterRunsQuery.data, isEditMode, queryId]);
  const activeRunQuery = useQuery({
    queryKey: ["web-discovery-run", activeRunId],
    queryFn: () => getWebDiscoveryRun(activeRunId),
    enabled: !!activeRunId,
    refetchInterval: (q) => {
      const row = q.state.data;
      if (!row) return 1000;
      return ["queued", "researching", "synthesizing"].includes(row.status) ? 1000 : false;
    },
  });

  useEffect(() => {
    if (isEditMode) return;
    const cluster = clusterQuery.data;
    if (!cluster || autoPrefillAppliedRef.current) return;

    const geoFocus = cluster.geography_focus.filter(Boolean);
    const includeKeywords = cluster.include_keywords.filter(Boolean);
    const excludeKeywords = cluster.exclude_keywords.filter(Boolean);
    const signals = cluster.signal_priorities.filter(Boolean);
    const geoText =
      geoFocus.length === 0
        ? ""
        : geoFocus.length === 1
          ? geoFocus[0]
          : geoFocus.slice(0, 2).join(" and ");
    const keywordSeed = includeKeywords.slice(0, 3);
    const baseSearchIntent = keywordSeed.length
      ? `emerging ${keywordSeed.join(", ")} launches and market signals`
      : `emerging ${cluster.name} launches and market signals`;
    const searchQuery = geoText ? `${baseSearchIntent} in ${geoText}` : baseSearchIntent;

    const guidingQuery = signals.length
      ? `prioritize ${signals.slice(0, 3).join(", ").toLowerCase()}`
      : "";

    const seedSystemPromptParts = [
      signals.length
        ? `Focus on these signals: ${signals.slice(0, 4).join(", ")}.`
        : "",
      excludeKeywords.length
        ? `Down-rank irrelevant matches related to: ${excludeKeywords.slice(0, 5).join(", ")}.`
        : "",
      geoText ? `Prefer developments relevant to ${geoText}.` : "",
    ].filter(Boolean);

    const variationSeeds = signals.slice(0, 3).map((signal) =>
      `${keywordSeed[0] ?? cluster.name} ${signal.toLowerCase()}${geoText ? ` ${geoText}` : ""}`,
    );

    setForm((curr) => ({
      ...curr,
      label: curr.label || `${cluster.name} monitor`,
      search_query: curr.search_query || searchQuery,
      highlights_guiding_query: curr.highlights_guiding_query || guidingQuery,
      system_prompt: curr.system_prompt || seedSystemPromptParts.join(" "),
    }));

    if (variationSeeds.length) {
      setAdditionalQueries((curr) => (curr.length ? curr : variationSeeds));
    }
    toast.message("Cluster context loaded", {
      description:
        "Some query fields were prefilled from this cluster. Review and adjust before running.",
    });

    autoPrefillAppliedRef.current = true;
  }, [clusterQuery.data, isEditMode]);

  useEffect(() => {
    const q = queryDetailQuery.data;
    if (!q) return;
    setForm((curr) => ({
      ...curr,
      label: q.label,
      search_query: q.search_query,
      search_type: q.search_type,
      num_results: q.num_results,
      category: q.category ?? "",
      user_location: q.user_location ?? "",
      content_highlights: q.content_highlights,
      highlights_max_chars: q.highlights_max_chars,
      highlights_guiding_query: q.highlights_guiding_query ?? "",
      content_text: q.content_text,
      text_max_chars: q.text_max_chars,
      text_main_content_only: q.text_main_content_only,
      content_summary: q.content_summary,
      summary_max_chars: q.summary_max_chars,
      max_age_hours: q.max_age_hours,
      livecrawl_timeout_ms: q.livecrawl_timeout_ms,
      content_moderation: q.content_moderation,
      stream_response: q.stream_response,
      published_after: q.published_after ?? "",
      published_before: q.published_before ?? "",
      crawled_after: q.crawled_after ?? "",
      crawled_before: q.crawled_before ?? "",
      system_prompt: q.system_prompt ?? "",
    }));
    setIncludeDomains(q.include_domains ?? []);
    setExcludeDomains(q.exclude_domains ?? []);
    setAdditionalQueries(q.additional_queries ?? []);
    autoPrefillAppliedRef.current = true;
  }, [queryDetailQuery.data]);

  useEffect(() => {
    if (!isEditMode || !activeRunStorageKey) return;
    const stored = localStorage.getItem(activeRunStorageKey);
    if (stored) setActiveRunId(stored);
  }, [isEditMode, activeRunStorageKey]);

  useEffect(() => {
    if (!isEditMode || !queryId) return;
    const latest = clusterRunsQuery.data?.[0];
    if (!latest || activeRunId) return;
    if (!["queued", "researching", "synthesizing"].includes(latest.status)) return;
    if (!runIncludesQuery(latest, queryId)) return;
    setActiveRunId(latest.id);
    localStorage.setItem(activeRunStorageKey, latest.id);
  }, [clusterRunsQuery.data, activeRunId, activeRunStorageKey, isEditMode, queryId]);

  const goToQueryResults = (run: string) => {
    if (!isEditMode || !queryId || redirectedRunRef.current === run) return;
    redirectedRunRef.current = run;
    qc.invalidateQueries({ queryKey: ["web-discovery-query-results", queryId] });
    qc.invalidateQueries({ queryKey: ["web-discovery-query-runs", queryId] });
    navigate(
      `/discover-web/clusters/${clusterId}/queries/${queryId}/results?run=${run}`,
    );
  };

  // When idle, show logs from the most recent run for this query.
  useEffect(() => {
    if (activeRunId || runLaunching || !lastQueryRunId) return;
    let cancelled = false;
    recentRunEvents(lastQueryRunId, 120)
      .then((rows) => {
        if (!cancelled && rows.length) {
          setFeedEvents(rows);
          setFeedConnected(false);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [activeRunId, runLaunching, lastQueryRunId]);

  useEffect(() => {
    if (!activeRunId) return;
    let cancelled = false;

    const hydrateEvents = () => {
      recentRunEvents(activeRunId, 120)
        .then((rows) => {
          if (cancelled || rows.length === 0) return;
          setFeedEvents(rows);
          setFeedConnected(true);
        })
        .catch(() => {});
    };

    hydrateEvents();
    const poll = window.setInterval(hydrateEvents, 800);

    const unsub = subscribeRunEvents(
      activeRunId,
      (ev) => {
        setFeedConnected(true);
        setFeedEvents((prev) => {
          if (prev.some((p) => p.id === ev.id)) return prev;
          const next = [...prev.filter((p) => !p.id.startsWith("opt-")), ev];
          return next.length > 120 ? next.slice(-120) : next;
        });
        if (isEditMode && ev.kind === "run_completed") {
          goToQueryResults(activeRunId);
        }
      },
      () => {
        /* polling still hydrates logs if SSE blips */
      },
      () => setFeedConnected(true),
    );
    return () => {
      cancelled = true;
      window.clearInterval(poll);
      unsub();
    };
  }, [activeRunId, isEditMode, queryId, clusterId]);

  useEffect(() => {
    const status = activeRunQuery.data?.status;
    if (!status) return;
    if (!["queued", "researching", "synthesizing"].includes(status)) {
      if (activeRunStorageKey) localStorage.removeItem(activeRunStorageKey);
    }
  }, [activeRunQuery.data?.status, activeRunStorageKey]);

  useEffect(() => {
    if (!isEditMode || !activeRunId) return;
    const status = activeRunQuery.data?.status;
    if (status === "completed") {
      goToQueryResults(activeRunId);
    }
  }, [activeRunQuery.data?.status, activeRunId, isEditMode, clusterId, queryId]);

  const buildQueryPayload = (): WebDiscoveryQueryInput => {
    if (!form.search_query.trim()) {
      throw new Error("Search query is required");
    }
    return {
      label: form.label.trim() || form.search_query.trim().slice(0, 80),
      search_query: form.search_query.trim(),
      search_type: form.search_type,
      num_results: form.num_results,
      category: form.category || null,
      user_location: form.user_location || null,
      structured_outputs: false,
      system_prompt: form.system_prompt.trim() || null,
      output_schema: null,
      content_highlights: form.content_highlights,
      highlights_max_chars: form.content_highlights ? form.highlights_max_chars : null,
      highlights_guiding_query:
        form.content_highlights && form.highlights_guiding_query.trim()
          ? form.highlights_guiding_query.trim()
          : null,
      content_text: form.content_text,
      text_max_chars: form.content_text ? form.text_max_chars : null,
      text_main_content_only: form.text_main_content_only,
      content_summary: form.content_summary,
      summary_max_chars: form.content_summary ? form.summary_max_chars : null,
      max_age_hours: form.max_age_hours,
      livecrawl_timeout_ms: form.livecrawl_timeout_ms,
      subpages: 0,
      extra_links: 0,
      extra_image_links: 0,
      content_moderation: form.content_moderation,
      stream_response: form.stream_response,
      include_domains: includeDomains,
      exclude_domains: excludeDomains,
      published_after: form.published_after || null,
      published_before: form.published_before || null,
      crawled_after: form.crawled_after || null,
      crawled_before: form.crawled_before || null,
      additional_queries: additionalQueries,
    };
  };

  const createMut = useMutation({
    mutationFn: (body: WebDiscoveryQueryInput) => createWebDiscoveryQuery(clusterId, body),
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ["web-discovery-queries", clusterId] });
      setLastCreatedLabel(created.label);
      toast.success("Query created", {
        description: "Saved to this cluster. Use Run Query when you are ready.",
      });
    },
    onError: (err) => {
      toast.error("Failed to create query", { description: (err as Error).message });
    },
  });
  const updateMut = useMutation({
    mutationFn: (body: WebDiscoveryQueryInput) => updateWebDiscoveryQuery(queryId, body),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ["web-discovery-query", queryId] });
      qc.invalidateQueries({ queryKey: ["web-discovery-queries", clusterId] });
      setLastCreatedLabel(updated.label);
      toast.success("Query updated", {
        description: "Changes saved. You can run and monitor logs from this page.",
      });
    },
    onError: (err) => {
      toast.error("Failed to update query", { description: (err as Error).message });
    },
  });
  const runMut = useMutation({
    mutationFn: async () => {
      let targetQueryId = queryId;
      if (!isEditMode) {
        const created = await createWebDiscoveryQuery(clusterId, buildQueryPayload());
        targetQueryId = created.id;
        qc.invalidateQueries({ queryKey: ["web-discovery-queries", clusterId] });
        setLastCreatedLabel(created.label);
      }
      const run = await startWebDiscoveryClusterRun(clusterId, targetQueryId);
      return { run, targetQueryId };
    },
    onMutate: () => {
      setUserInitiatedRun(true);
      setRunLaunching(true);
      const now = new Date().toISOString();
      setFeedEvents([
        {
          id: "opt-queued",
          run_id: "pending",
          kind: "run_queued",
          message: "Sending run to engine…",
          level: "info",
          meta: {},
          created_at: now,
        },
      ]);
      setFeedConnected(false);
    },
    onSuccess: ({ run: created, targetQueryId }) => {
      redirectedRunRef.current = null;
      setRunLaunching(false);
      setActiveRunId(created.run_id);
      const runStorageKey = `web_discovery_active_run_${clusterId}_${targetQueryId}`;
      localStorage.setItem(runStorageKey, created.run_id);
      localStorage.setItem(`web_discovery_query_has_run_${targetQueryId}`, "1");
      qc.setQueryData(["web-discovery-run", created.run_id], {
        id: created.run_id,
        status: created.status,
        progress_pct: 0,
        source_kind: "web_discovery",
        query: "",
        engines: {},
        engine_outputs: {},
        started_at: null,
        completed_at: null,
        error: null,
        created_at: new Date().toISOString(),
      });
      qc.invalidateQueries({ queryKey: ["web-discovery-runs", clusterId] });
      qc.invalidateQueries({ queryKey: ["web-discovery-query-runs", targetQueryId] });
      recentRunEvents(created.run_id, 120)
        .then((rows) => {
          if (rows.length) setFeedEvents(rows);
        })
        .catch(() => {});
      if (!isEditMode) {
        toast.success("Query created and run started", {
          description: "Opening this query’s workbench — results when the run finishes.",
        });
        navigate(`/discover-web/clusters/${clusterId}/queries/${targetQueryId}`);
        return;
      }
      toast.success("Query run started", {
        description: "Live activity below — results open when the run finishes.",
      });
    },
    onError: (err) => {
      setUserInitiatedRun(false);
      setRunLaunching(false);
      setFeedEvents([]);
      toast.error("Failed to start run", { description: (err as Error).message });
    },
    onSettled: () => {
      setRunLaunching(false);
    },
  });

  const searchTypeIdx = useMemo(
    () => SEARCH_TYPES.findIndex((option) => option.value === form.search_type),
    [form.search_type],
  );

  const selectedContent = useMemo(() => {
    const out: string[] = [];
    if (form.content_highlights) out.push("Highlights");
    if (form.content_text) out.push("Full text");
    if (form.content_summary) out.push("Summary");
    return out;
  }, [form.content_highlights, form.content_text, form.content_summary]);

  const activeRunLive = useMemo(() => {
    if (runLaunching || runMut.isPending) return true;
    if (!activeRunId) return false;
    const row = activeRunQuery.data;
    if (!row) return true;
    return ["queued", "researching", "synthesizing"].includes(row.status);
  }, [runLaunching, runMut.isPending, activeRunId, activeRunQuery.data]);

  const realFeedEvents = useMemo(
    () => feedEvents.filter((ev) => !ev.id.startsWith("opt-")),
    [feedEvents],
  );

  const showLivePanel = isEditMode
    ? runLaunching || !!activeRunId || realFeedEvents.length > 0
    : runLaunching || runMut.isPending || (userInitiatedRun && !!activeRunId);

  const liveStatusLabel = runLaunching || runMut.isPending
    ? "launching"
    : activeRunLive
      ? activeRunQuery.data?.status ?? "connecting"
      : realFeedEvents.length > 0
        ? "archive"
        : "ready";

  const hasCompletedRun = useMemo(() => {
    if (!isEditMode || !queryId) return false;
    if (localStorage.getItem(`web_discovery_query_has_run_${queryId}`) === "1") {
      return true;
    }
    const rows = clusterRunsQuery.data ?? [];
    return rows.some(
      (run) => run.status === "completed" && runIncludesQuery(run, queryId),
    );
  }, [clusterRunsQuery.data, isEditMode, queryId]);

  const waitingForLiveLogs =
    (runLaunching || runMut.isPending || !!activeRunId) &&
    realFeedEvents.length === 0 &&
    (runLaunching || runMut.isPending || activeRunLive);

  const qualityWarning = useMemo(() => {
    if (!form.content_highlights && !form.content_text && !form.content_summary) {
      return "No content output selected. Results may be too thin for downstream ranking.";
    }
    return null;
  }, [form.content_highlights, form.content_text, form.content_summary]);

  const savePending = createMut.isPending || updateMut.isPending;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    try {
      const payload = buildQueryPayload();
      if (isEditMode) {
        updateMut.mutate(payload);
        return;
      }
      createMut.mutate(payload);
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  if (isEditMode && queryDetailQuery.isLoading) {
    return (
      <>
        <Topbar title="Web Discovery" subtitle="Loading query..." />
        <PageBody>
          <div className="grid gap-5 xl:grid-cols-[1fr_300px]">
            <section className="space-y-4">
              <div className="animate-pulse rounded-xl border border-border bg-white p-5 shadow-soft">
                <div className="h-3 w-28 rounded bg-tint/80" />
                <div className="mt-2 h-7 w-52 rounded bg-tint/70" />
                <div className="mt-2 h-4 w-80 rounded bg-tint/60" />
              </div>
              <div className="animate-pulse rounded-2xl border border-border bg-white p-4 shadow-soft">
                <div className="h-5 w-24 rounded bg-tint/70" />
                <div className="mt-4 h-10 w-full rounded bg-tint/60" />
                <div className="mt-3 h-20 w-full rounded bg-tint/60" />
                <div className="mt-4 h-5 w-28 rounded bg-tint/70" />
                <div className="mt-3 h-10 w-full rounded bg-tint/60" />
              </div>
            </section>
            <aside className="space-y-3">
              <div className="animate-pulse rounded-xl border border-border bg-white p-4 shadow-soft">
                <div className="h-4 w-28 rounded bg-tint/70" />
                <div className="mt-3 h-24 w-full rounded bg-tint/60" />
              </div>
              <div className="animate-pulse rounded-xl border border-border bg-white p-4 shadow-soft">
                <div className="h-10 w-full rounded bg-tint/60" />
                <div className="mt-2 h-10 w-full rounded bg-tint/60" />
                <div className="mt-2 h-10 w-full rounded bg-tint/60" />
              </div>
            </aside>
          </div>
        </PageBody>
      </>
    );
  }

  return (
    <>
      <Topbar
        title="Web Discovery"
        subtitle={
          isEditMode
            ? "Edit and monitor this query with live synchronized activity."
            : "Create and tune Exa Search queries for this cluster."
        }
      />
      <PageBody>
        <div className="mb-4 flex items-center gap-2 text-sm text-muted">
          <Link to="/discover-web" className="hover:text-ink">Clusters</Link>
          <span>›</span>
          <Link to={`/discover-web/clusters/${clusterId}`} className="hover:text-ink">
            {clusterQuery.data?.name ?? "Cluster"}
          </Link>
          <span>›</span>
          <span className="text-ink">{isEditMode ? "Query" : "New query"}</span>
        </div>

        <form onSubmit={onSubmit} className="grid gap-5 xl:grid-cols-[1fr_300px]">
          <section className="space-y-4">
            <div className="rounded-xl border border-border bg-gradient-to-b from-white to-[#FCFCFB] p-5 shadow-soft">
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#5E8E4A]">
                Exa Search Query
              </p>
              <h2 className="mt-1 text-2xl font-semibold text-ink">
                {isEditMode ? "Query Workbench" : "Add Search Query"}
              </h2>
              <p className="mt-1 text-sm text-muted">
                Give users Exa-level control over search behavior, content retrieval, and filtering.
              </p>
            </div>

            <div className="overflow-visible rounded-2xl border border-border bg-white shadow-soft">
              <details open className="group border-b border-border">
                <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3">
                  <span className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                    Search
                    <SectionInfo text="Define query intent and label used by this cluster run." />
                  </span>
                  <ChevronDown className="h-4 w-4 text-soft transition group-open:rotate-180" />
                </summary>
                <div className="space-y-3 px-4 pb-4">
                  <Field
                    label="Query Label"
                    value={form.label}
                    onChange={(v) => setForm((prev) => ({ ...prev, label: v }))}
                    placeholder="e.g. Nootropic product launches"
                  />
                  <div>
                    <Label>Query *</Label>
                    <textarea
                      rows={3}
                      value={form.search_query}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, search_query: e.target.value }))
                      }
                      className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
                    />
                    <p className="mt-1 text-[11px] text-soft">
                      Use natural-language intent, e.g. "emerging nootropic pouch launches in North America".
                    </p>
                  </div>
                </div>
              </details>

              <details open className="group border-b border-border">
                <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3">
                  <span className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                    Exa Presets
                    <SectionInfo text="Quickly apply tested default profiles for speed, balance, or depth." />
                  </span>
                  <ChevronDown className="h-4 w-4 text-soft transition group-open:rotate-180" />
                </summary>
                <div className="px-4 pb-4">
                  <p className="text-xs text-soft">
                    Apply a tested baseline profile, then fine-tune the rest.
                  </p>
                  <div className="mt-3">
                    <PremiumSelect
                      label="Preset"
                      value={preset}
                      onChange={(next) => {
                        const selected = PRESETS.find((p) => p.key === next);
                        if (!selected) return;
                        setPreset(next as PresetKey);
                        setForm((curr) => selected.apply(curr));
                      }}
                      options={PRESETS.map((p) => ({ value: p.key, label: p.label }))}
                    />
                  </div>
                  <p className="mt-2 text-xs text-muted">
                    {PRESETS.find((p) => p.key === preset)?.hint}
                  </p>
                </div>
              </details>

              <details open className="group border-b border-border">
                <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3">
                  <span className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                    Search Type
                    <SectionInfo text="Controls retrieval depth and latency from instant to deep reasoning." />
                  </span>
                  <ChevronDown className="h-4 w-4 text-soft transition group-open:rotate-180" />
                </summary>
                <div className="px-4 pb-4">
                  <input
                    type="range"
                    min={0}
                    max={SEARCH_TYPES.length - 1}
                    step={1}
                    value={Math.max(searchTypeIdx, 0)}
                    onChange={(e) =>
                      setForm((prev) => ({
                        ...prev,
                        search_type: SEARCH_TYPES[Number(e.target.value)]?.value ?? "auto",
                      }))
                    }
                    className="w-full accent-accent"
                  />
                  <div className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-6">
                    {SEARCH_TYPES.map((option) => {
                      const active = option.value === form.search_type;
                      return (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => setForm((prev) => ({ ...prev, search_type: option.value }))}
                          className={cn(
                            "rounded-lg border px-2 py-1 text-left text-xs transition",
                            active
                              ? "border-accent bg-accent/10 text-ink"
                              : "border-border bg-white text-muted hover:border-soft",
                          )}
                        >
                          <div className="font-medium">{option.label}</div>
                          <div className="text-[10px] text-soft">{option.hint}</div>
                        </button>
                      );
                    })}
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <NumberField
                      label="Number of Results"
                      value={form.num_results}
                      min={1}
                      max={100}
                      onChange={(v) => setForm((prev) => ({ ...prev, num_results: v }))}
                    />
                    <PremiumSelect
                      label="Result Category"
                      value={form.category}
                      onChange={(next) => setForm((prev) => ({ ...prev, category: next }))}
                      options={[...RESULT_CATEGORY_OPTIONS]}
                      helper="Optional. Keep empty for broad discovery."
                    />
                  </div>
                  <p className="mt-2 text-[11px] text-soft">
                    Exa can return up to 100 results; higher values increase latency and post-processing cost.
                  </p>
                </div>
              </details>

              <details open className="group border-b border-border">
                <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3">
                  <span className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                    Contents
                    <SectionInfo text="Choose what payload to fetch from each result: highlights, text, and summary." />
                  </span>
                  <ChevronDown className="h-4 w-4 text-soft transition group-open:rotate-180" />
                </summary>
                <div className="space-y-3 px-4 pb-4">
                  <Toggle
                    label="Highlights"
                    checked={form.content_highlights}
                    onChange={(checked) =>
                      setForm((prev) => ({ ...prev, content_highlights: checked }))
                    }
                  />
                  {form.content_highlights && (
                    <div className="grid gap-3 pl-4 sm:grid-cols-2">
                      <NumberField
                        label="Highlights max characters"
                        value={form.highlights_max_chars ?? 0}
                        min={0}
                        max={100000}
                        onChange={(v) =>
                          setForm((prev) => ({ ...prev, highlights_max_chars: v || null }))
                        }
                      />
                      <Field
                        label="Highlights guiding query"
                        value={form.highlights_guiding_query}
                        onChange={(v) =>
                          setForm((prev) => ({ ...prev, highlights_guiding_query: v }))
                        }
                        placeholder="e.g. key takeaways"
                      />
                    </div>
                  )}

                  <Toggle
                    label="Full webpage text"
                    checked={form.content_text}
                    onChange={(checked) => setForm((prev) => ({ ...prev, content_text: checked }))}
                  />
                  {form.content_text && (
                    <div className="grid gap-3 pl-4 sm:grid-cols-2">
                      <NumberField
                        label="Text max characters"
                        value={form.text_max_chars ?? 0}
                        min={0}
                        max={200000}
                        onChange={(v) =>
                          setForm((prev) => ({ ...prev, text_max_chars: v || null }))
                        }
                      />
                      <Toggle
                        label="Main content only"
                        checked={form.text_main_content_only}
                        onChange={(checked) =>
                          setForm((prev) => ({ ...prev, text_main_content_only: checked }))
                        }
                      />
                    </div>
                  )}

                  <Toggle
                    label="Summary"
                    checked={form.content_summary}
                    onChange={(checked) =>
                      setForm((prev) => ({ ...prev, content_summary: checked }))
                    }
                  />
                  {form.content_summary && (
                    <div className="pl-4">
                      <NumberField
                        label="Summary max characters"
                        value={form.summary_max_chars ?? 0}
                        min={0}
                        max={50000}
                        onChange={(v) =>
                          setForm((prev) => ({ ...prev, summary_max_chars: v || null }))
                        }
                      />
                    </div>
                  )}
                  {qualityWarning && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                      {qualityWarning}
                    </div>
                  )}
                </div>
              </details>

              <details open className="group border-b border-border">
                <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3">
                  <span className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                    Synthesis Controls
                    <SectionInfo text="Guide post-retrieval interpretation behavior using a system prompt." />
                  </span>
                  <ChevronDown className="h-4 w-4 text-soft transition group-open:rotate-180" />
                </summary>
                <div className="space-y-3 px-4 pb-4">
                  <div>
                    <Label>System Prompt (optional)</Label>
                    <textarea
                      rows={4}
                      value={form.system_prompt}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, system_prompt: e.target.value }))
                      }
                      placeholder="Guide how results should be synthesized or interpreted..."
                      className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
                    />
                  </div>
                </div>
              </details>

              <details open className="group border-b border-border">
                <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3">
                  <span className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                    Livecrawl
                    <SectionInfo text="Tune freshness and crawl timeout for recency-sensitive discovery." />
                  </span>
                  <ChevronDown className="h-4 w-4 text-soft transition group-open:rotate-180" />
                </summary>
                <div className="px-4 pb-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <PremiumSelect
                      label="Max age"
                      value={
                        LIVECRAWL_AGE_OPTIONS.find((opt) => opt.hours === form.max_age_hours)?.value ??
                        "cache_only"
                      }
                      onChange={(next) => {
                        const selected = LIVECRAWL_AGE_OPTIONS.find((opt) => opt.value === next);
                        setForm((prev) => ({ ...prev, max_age_hours: selected?.hours ?? null }));
                      }}
                      options={LIVECRAWL_AGE_OPTIONS.map((opt) => ({
                        value: opt.value,
                        label: opt.label,
                      }))}
                    />
                    <PremiumSelect
                      label="Livecrawl timeout"
                      value={
                        LIVECRAWL_TIMEOUT_OPTIONS.find((opt) => opt.ms === form.livecrawl_timeout_ms)
                          ?.value ?? "10s"
                      }
                      onChange={(next) => {
                        const selected = LIVECRAWL_TIMEOUT_OPTIONS.find((opt) => opt.value === next);
                        if (!selected) return;
                        setForm((prev) => ({ ...prev, livecrawl_timeout_ms: selected.ms }));
                      }}
                      options={LIVECRAWL_TIMEOUT_OPTIONS.map((opt) => ({
                        value: opt.value,
                        label: opt.label,
                      }))}
                    />
                  </div>
                  <p className="mt-2 text-[11px] text-soft">
                    Keep this simple: choose freshness window + timeout, and we handle crawl depth automatically.
                  </p>
                </div>
              </details>

              <details open className="group border-b border-border">
                <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3">
                  <span className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                    Filters
                    <SectionInfo text="Constrain discovery by domains, date ranges, geography, and moderation flags." />
                  </span>
                  <ChevronDown className="h-4 w-4 text-soft transition group-open:rotate-180" />
                </summary>
                <div className="px-4 pb-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <DomainsField
                      label="Include domains"
                      values={includeDomains}
                      onChange={setIncludeDomains}
                      placeholder="exa.ai, docs.exa.ai/reference"
                    />
                    <DomainsField
                      label="Exclude domains"
                      values={excludeDomains}
                      onChange={setExcludeDomains}
                      placeholder="reddit.com, twitter.com"
                    />
                    <DateRangeField
                      label="Published date range"
                      fromValue={form.published_after}
                      toValue={form.published_before}
                      onChangeFrom={(v) => setForm((prev) => ({ ...prev, published_after: v }))}
                      onChangeTo={(v) => setForm((prev) => ({ ...prev, published_before: v }))}
                    />
                    <DateRangeField
                      label="Crawled date range"
                      fromValue={form.crawled_after}
                      toValue={form.crawled_before}
                      onChangeFrom={(v) => setForm((prev) => ({ ...prev, crawled_after: v }))}
                      onChangeTo={(v) => setForm((prev) => ({ ...prev, crawled_before: v }))}
                    />
                    <Field
                      label="User location (country code)"
                      value={form.user_location}
                      onChange={(v) =>
                        setForm((prev) => ({ ...prev, user_location: v.toUpperCase() }))
                      }
                      placeholder="US"
                    />
                  </div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <Toggle
                      label="Content moderation"
                      checked={form.content_moderation}
                      onChange={(checked) =>
                        setForm((prev) => ({ ...prev, content_moderation: checked }))
                      }
                    />
                    <Toggle
                      label="Stream response"
                      checked={form.stream_response}
                      onChange={(checked) =>
                        setForm((prev) => ({ ...prev, stream_response: checked }))
                      }
                    />
                  </div>
                  <p className="mt-2 text-[11px] text-soft">
                    Use domain filters sparingly; strict filters can suppress novel findings.
                  </p>
                </div>
              </details>

              <details open className="group">
                <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3">
                  <span className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                    Deep Search extras
                    <SectionInfo text="Add query variations to broaden coverage for adjacent opportunities." />
                  </span>
                  <ChevronDown className="h-4 w-4 text-soft transition group-open:rotate-180" />
                </summary>
                <div className="px-4 pb-4">
                  <DomainsField
                    label="Additional query variations"
                    values={additionalQueries}
                    onChange={setAdditionalQueries}
                    placeholder="add variation and press Enter"
                  />
                </div>
              </details>
            </div>
          </section>

          <aside className="space-y-3">
            <div className="overflow-hidden rounded-xl border border-border bg-gradient-to-b from-[#FFFCF8] to-white shadow-soft">
              <div className="border-b border-border/80 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-soft">
                  Live Run Panel
                </p>
                {!showLivePanel && !isEditMode ? (
                  <p className="mt-1 text-xs text-muted">
                    Use Create &amp; Run Query to save this query and stream its run here.
                  </p>
                ) : !showLivePanel ? (
                  <p className="mt-1 text-xs text-muted">
                    Run this query to stream activity here in real time.
                  </p>
                ) : (
                  <>
                    <div className="mt-1 flex items-center justify-between">
                      <span className="inline-flex items-center gap-1.5 text-sm font-medium text-ink">
                        <Activity
                          className={cn(
                            "h-4 w-4 text-accent",
                            activeRunLive && "animate-pulse",
                          )}
                        />
                        {liveStatusLabel}
                      </span>
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                          activeRunLive
                            ? feedConnected
                              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                              : "border-amber-200 bg-amber-50 text-amber-700"
                            : "border-border bg-slate-50 text-soft",
                        )}
                      >
                        <span
                          className={cn(
                            "h-1.5 w-1.5 rounded-full",
                            activeRunLive
                              ? feedConnected
                                ? "animate-pulse bg-emerald-500"
                                : "bg-amber-500"
                              : "bg-soft",
                          )}
                        />
                        {activeRunLive ? (feedConnected ? "Live" : "Syncing") : "Archive"}
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 rounded-full bg-[#EFEDE8]">
                      <div
                        className="h-1.5 rounded-full bg-accent transition-all"
                        style={{
                          width: `${Math.max(
                            0,
                            Math.min(
                              100,
                              activeRunQuery.data?.progress_pct ??
                                clusterRunsQuery.data?.find((r) => r.id === lastQueryRunId)
                                  ?.progress_pct ??
                                0,
                            ),
                          )}%`,
                        }}
                      />
                    </div>
                  </>
                )}
              </div>
              <div className="min-h-[280px] max-h-[380px] overflow-y-auto px-2 py-2">
                {realFeedEvents.length > 0 ? (
                  <>
                    <ol className="space-y-1.5">
                      {realFeedEvents.slice(-24).map((ev) => (
                        <li
                          key={ev.id}
                          className={cn(
                            "rounded-lg border px-2.5 py-2 text-xs transition",
                            ev.id.startsWith("opt-") && "border-dashed border-accent/30 bg-accent/5",
                            ev.level === "error"
                              ? "border-red-200 bg-red-50 text-red-700"
                              : ev.level === "warn"
                                ? "border-amber-200 bg-amber-50 text-amber-700"
                                : !ev.id.startsWith("opt-") &&
                                    "border-border bg-white text-muted",
                          )}
                        >
                          <p className="font-medium text-ink">{ev.message}</p>
                          <p className="mt-0.5 text-[10px] text-soft">
                            {new Date(ev.created_at).toLocaleTimeString()} · {ev.kind}
                          </p>
                        </li>
                      ))}
                    </ol>
                    {waitingForLiveLogs ? (
                      <RunLogSkeleton
                        className="mt-2 border-t border-border/60 pt-2"
                        hint="Fetching live activity…"
                      />
                    ) : null}
                  </>
                ) : waitingForLiveLogs ? (
                  <RunLogSkeleton hint="Connecting to live activity…" />
                ) : (
                  <div className="px-2 py-12 text-center text-xs text-soft">
                    No activity yet. Use Run Query to start streaming logs.
                  </div>
                )}
              </div>
            </div>
            <div className="rounded-xl border border-border bg-white p-4 shadow-soft">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-soft">
                Configuration
              </p>
              <dl className="mt-2 space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted">Search type</dt>
                  <dd className="font-medium text-ink">{form.search_type}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">Results</dt>
                  <dd className="font-medium text-ink">{form.num_results}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">Content</dt>
                  <dd className="font-medium text-ink">
                    {selectedContent.length ? selectedContent.join(", ") : "None"}
                  </dd>
                </div>
              </dl>
            </div>
            <div className="rounded-xl border border-border bg-white p-4 text-xs text-soft">
              Cluster rules (keywords, geography, and signal detection) apply on top of each query.
            </div>
            {lastCreatedLabel ? (
              <div className="rounded-xl border border-[#BDE6D3] bg-[#ECF8F1] px-3 py-2 text-xs text-[#155A3E]">
                Query added: <span className="font-semibold">{lastCreatedLabel}</span>
              </div>
            ) : null}
            <Button type="submit" className="w-full" disabled={savePending}>
              <Search className="h-4 w-4" />
              {savePending
                ? isEditMode
                  ? "Saving..."
                  : "Creating..."
                : isEditMode
                  ? "Save Query"
                  : "Create Query"}
            </Button>
            {isEditMode ? (
              <Button
                type="button"
                className={cn(
                  "w-full",
                  activeRunLive &&
                    "disabled:!cursor-wait disabled:!bg-accent disabled:!text-white disabled:!opacity-95",
                )}
                onClick={() => {
                  if (hasCompletedRun && !activeRunLive) {
                    setConfirmRunQuery(true);
                    return;
                  }
                  try {
                    buildQueryPayload();
                    runMut.mutate();
                  } catch (err) {
                    toast.error((err as Error).message);
                  }
                }}
                disabled={activeRunLive || savePending}
              >
                <Activity className={cn("h-4 w-4", activeRunLive && "animate-pulse")} />
                {runMut.isPending || runLaunching
                  ? "Launching…"
                  : activeRunLive
                    ? "Running…"
                    : hasCompletedRun
                      ? "Run Again"
                      : "Run Query"}
              </Button>
            ) : (
              <Button
                type="button"
                className={cn(
                  "w-full",
                  activeRunLive &&
                    "disabled:!cursor-wait disabled:!bg-accent disabled:!text-white disabled:!opacity-95",
                )}
                onClick={() => {
                  try {
                    buildQueryPayload();
                    runMut.mutate();
                  } catch (err) {
                    toast.error((err as Error).message);
                  }
                }}
                disabled={activeRunLive || savePending}
              >
                <Activity className={cn("h-4 w-4", activeRunLive && "animate-pulse")} />
                {runMut.isPending || runLaunching
                  ? "Launching…"
                  : activeRunLive
                    ? "Running…"
                    : "Create & Run Query"}
              </Button>
            )}
            {isEditMode ? (
              <Button
                type="button"
                variant="secondary"
                className="w-full"
                onClick={() =>
                  navigate(`/discover-web/clusters/${clusterId}/queries/${queryId}/results`)
                }
              >
                <ChevronDown className="h-4 w-4 rotate-[-90deg]" />
                View Query Results
              </Button>
            ) : null}
            <Button
              type="button"
              variant="secondary"
              className="w-full"
              onClick={() => navigate(`/discover-web/clusters/${clusterId}`)}
            >
              <ArrowLeft className="h-4 w-4" />
              Cancel
            </Button>
          </aside>
        </form>
      </PageBody>
      {isEditMode ? (
        <ConfirmDialog
          open={confirmRunQuery}
          onOpenChange={setConfirmRunQuery}
          title="Run this query again?"
          description="This starts a fresh Exa search for the current query settings. You will be taken to the results page when it completes."
          confirmText={runMut.isPending || runLaunching ? "Launching…" : "Run again"}
          cancelText="Cancel"
          busy={runMut.isPending || runLaunching}
          onConfirm={() => {
            setConfirmRunQuery(false);
            runMut.mutate();
          }}
        />
      ) : null}
    </>
  );
}

function runIncludesQuery(run: WebDiscoveryRun, queryId: string): boolean {
  const payload =
    run.engine_outputs && typeof run.engine_outputs === "object"
      ? run.engine_outputs
      : run.engines;
  const queries = Array.isArray(payload?.queries) ? payload.queries : [];
  return queries.some(
    (item) =>
      item &&
      typeof item === "object" &&
      String((item as Record<string, unknown>).query_id) === queryId,
  );
}

function RunLogSkeleton({
  hint,
  className,
}: {
  hint?: string;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2 px-2 py-3", className)}>
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="h-11 animate-pulse rounded-lg bg-[#EFEDE8]"
          style={{ opacity: 1 - i * 0.12 }}
        />
      ))}
      {hint ? <p className="pt-1 text-center text-xs text-soft">{hint}</p> : null}
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <p className="mb-1 text-[12px] font-semibold text-muted">{children}</p>;
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <Label>{label}</Label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-10 w-full rounded-lg border border-border bg-white px-3 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
      />
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
}) {
  return (
    <div>
      <Label>{label}</Label>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value || 0))}
        className="h-10 w-full rounded-lg border border-border bg-white px-3 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
      />
    </div>
  );
}

function DateRangeField({
  label,
  fromValue,
  toValue,
  onChangeFrom,
  onChangeTo,
}: {
  label: string;
  fromValue: string;
  toValue: string;
  onChangeFrom: (v: string) => void;
  onChangeTo: (v: string) => void;
}) {
  return (
    <div>
      <Label>{label}</Label>
      <div className="grid gap-2 sm:grid-cols-2">
        <input
          type="date"
          value={fromValue}
          onChange={(e) => onChangeFrom(e.target.value)}
          className="h-10 w-full rounded-lg border border-border bg-white px-3 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
        />
        <input
          type="date"
          value={toValue}
          onChange={(e) => onChangeTo(e.target.value)}
          className="h-10 w-full rounded-lg border border-border bg-white px-3 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
        />
      </div>
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-center justify-between rounded-lg border px-3 py-2 text-sm transition",
        checked ? "border-[#BDE6D3] bg-[#ECF8F1] text-[#155A3E]" : "border-border bg-[#FCFCFB]",
      )}
    >
      {label}
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 accent-[#0E9F6E]"
      />
    </label>
  );
}

function DomainsField({
  label,
  values,
  onChange,
  placeholder,
}: {
  label: string;
  values: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
}) {
  const [draft, setDraft] = useState("");
  return (
    <div>
      <Label>{label}</Label>
      <div className="rounded-lg border border-border bg-white p-2">
        <div className="mb-2 flex flex-wrap gap-1.5">
          {values.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => onChange(values.filter((v) => v !== value))}
              className="rounded-full border border-border bg-tint px-2 py-0.5 text-xs text-ink hover:bg-soft/30"
            >
              {value} ×
            </button>
          ))}
        </div>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (!["Enter", ",", " "].includes(e.key)) return;
            e.preventDefault();
            const next = draft.trim();
            if (!next || values.includes(next)) return;
            onChange([...values, next]);
            setDraft("");
          }}
          placeholder={placeholder}
          className="h-9 w-full rounded-md border border-border px-2.5 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
        />
      </div>
    </div>
  );
}

function PremiumSelect({
  label,
  value,
  options,
  onChange,
  helper,
}: {
  label: string;
  value: string;
  options: ReadonlyArray<{ value: string; label: string }>;
  onChange: (next: string) => void;
  helper?: string;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (event: MouseEvent) => {
      if (!rootRef.current) return;
      if (rootRef.current.contains(event.target as Node)) return;
      setOpen(false);
    };
    window.addEventListener("mousedown", onDocClick);
    return () => window.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const active = options.find((opt) => opt.value === value) ?? options[0];

  return (
    <div ref={rootRef} className="relative">
      <Label>{label}</Label>
      <button
        type="button"
        onClick={() => setOpen((curr) => !curr)}
        className={cn(
          "flex h-10 w-full items-center justify-between rounded-lg border bg-white px-3 text-left text-sm shadow-sm transition",
          open
            ? "border-accent ring-2 ring-accent/15"
            : "border-border hover:border-accent/60 hover:shadow-md",
        )}
      >
        <span className={cn(!active?.value && "text-soft")}>{active?.label}</span>
        <ChevronDown className={cn("h-4 w-4 text-soft transition", open && "rotate-180")} />
      </button>
      {open && (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border border-border bg-white shadow-2xl">
          {options.map((opt) => {
            const selected = opt.value === value;
            return (
              <button
                key={opt.value || "__empty"}
                type="button"
                onClick={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
                className={cn(
                  "flex w-full items-center justify-between px-3 py-2 text-left text-sm transition",
                  selected ? "bg-accent/10 text-ink" : "text-muted hover:bg-tint hover:text-ink",
                )}
              >
                <span>{opt.label}</span>
                {selected ? <span className="text-xs text-accent">Selected</span> : null}
              </button>
            );
          })}
        </div>
      )}
      {helper ? <p className="mt-1 text-[11px] text-soft">{helper}</p> : null}
    </div>
  );
}

function SectionInfo({ text }: { text: string }) {
  return (
    <span className="group/info relative inline-flex items-center">
      <Info className="h-3.5 w-3.5 text-soft transition group-hover/info:text-accent" />
      <span className="pointer-events-none absolute left-0 top-full z-40 mt-2 w-64 rounded-md border border-border bg-white px-2.5 py-1.5 text-[11px] font-normal leading-relaxed text-muted opacity-0 shadow-xl transition group-hover/info:opacity-100">
        {text}
      </span>
    </span>
  );
}
