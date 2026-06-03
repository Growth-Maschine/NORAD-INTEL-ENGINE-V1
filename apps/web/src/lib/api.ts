/**
 * Thin API client. Path resolution:
 *   - If `VITE_API_URL` is set (e.g. on Vercel pointing at a Railway backend),
 *     requests are prefixed with it.
 *   - Otherwise paths stay relative — Vite's dev proxy forwards `/api` +
 *     `/health` to the local FastAPI, and in single-origin prod (backend
 *     serving the built frontend) relative just works.
 */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** Strip a trailing slash so `${BASE}${path}` doesn't double up. */
const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");

/** Shared bearer for admin-only write routes (research/discovery/settings).
 *  Backend requires `X-Admin-Token` matching NORAD_ADMIN_TOKEN in prod.
 *  Bundled into the JS bundle — anyone with the URL can read it via DevTools,
 *  so treat it as a soft gate, not a security boundary. */
const ADMIN_TOKEN = (import.meta.env.VITE_ADMIN_TOKEN ?? "").trim();

/** All routes pass through to the backend untouched. */
export async function api<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const url = API_BASE ? `${API_BASE}${path}` : path;
  const baseHeaders: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (ADMIN_TOKEN) baseHeaders["X-Admin-Token"] = ADMIN_TOKEN;
  const res = await fetch(url, {
    headers: { ...baseHeaders, ...(init.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, text || res.statusText);
  }
  return (await res.json()) as T;
}

// ── Health types ─────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  environment: string;
}
export interface DependencyCheck {
  ok: boolean;
  latency_ms: number;
  error?: string;
}
export interface HealthDbResponse {
  status: "ok" | "degraded";
  postgres: DependencyCheck;
  redis: DependencyCheck;
}
export const getHealth = () => api<HealthResponse>("/health");
export const getHealthDb = () => api<HealthDbResponse>("/health/db");

// All discovery + events endpoints already include the `/api` prefix.

// ── Discovery types ──────────────────────────────────────────────────────────

export interface DiscoveryCluster {
  id: string;
  name: string;
  slug: string;
  group_name: string;
  description: string | null;
  keywords: string[];
  is_enabled: boolean;
  is_default: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface DiscoveryClusterGroups {
  groups: Record<string, DiscoveryCluster[]>;
  default_cluster_id: string | null;
}

export interface DiscoveryClusterInput {
  name: string;
  group_name: string;
  description?: string | null;
  keywords: string[];
  is_enabled?: boolean;
  is_default?: boolean;
}

// Legacy category picker compatibility types.
// Kept so older UI components compile while Discovery Clusters fully replace
// category taxonomy on Today.
export interface CategoryRef {
  slug: string;
  label: string;
  th_url: string;
}
export interface CategoryGroups {
  groups: Record<string, CategoryRef[]>;
}

export interface DiscoveryRunRequest {
  cluster_id: string;
  restrict_to_trendhunter_domain?: boolean;
  date_from?: string | null;
  date_to?: string | null;
  max_articles?: number;
}

export interface DiscoveryRunCreated {
  run_id: string;
  status: string;
  cluster_id: string;
  cluster_name: string;
  restrict_to_trendhunter_domain: boolean;
  sse_url: string;
  poll_url: string;
}

export type RunStatusName =
  | "queued"
  | "researching"
  | "synthesizing"
  | "completed"
  | "failed"
  | "cancelled";

export interface RunStatus {
  id: string;
  status: RunStatusName;
  progress_pct: number;
  source_kind: string;
  query: string;
  engines: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  created_at: string;
}

export interface ExtractedCompany {
  name: string;
  excerpt: string;
  hint_url?: string | null;
}

export type ArticleStatus =
  | "discovered"
  | "ranked"
  | "read"
  | "extracted"
  | "dismissed"
  | "researched";

export interface Article {
  id: string;
  url: string;
  source: string;
  category: string | null;
  title: string | null;
  dek: string | null;
  image_url: string | null;
  published_date: string | null;
  summary: string | null;
  relevance_score: number | null;
  relevance_reason: string | null;
  status: ArticleStatus;
  extracted_companies: ExtractedCompany[];
  discovery_run_id: string | null;
  created_at: string;
}

export interface RunEvent {
  id: string;
  run_id: string;
  kind: string;
  message: string;
  level: "info" | "warn" | "error";
  meta: Record<string, unknown>;
  created_at: string;
}

// ── Discovery endpoints ──────────────────────────────────────────────────────

export const getDiscoveryClusters = () =>
  api<DiscoveryClusterGroups>("/api/discovery/clusters");

export const getCategories = async (): Promise<CategoryGroups> => {
  const data = await getDiscoveryClusters();
  const groups: Record<string, CategoryRef[]> = {};
  for (const [group, items] of Object.entries(data.groups)) {
    groups[group] = items
      .filter((c) => c.is_enabled)
      .map((c) => ({
        slug: c.slug,
        label: c.name,
        th_url: "",
      }));
  }
  return { groups };
};

export const createDiscoveryCluster = (body: DiscoveryClusterInput) =>
  api<DiscoveryCluster>("/api/discovery/clusters", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const updateDiscoveryCluster = (
  id: string,
  body: DiscoveryClusterInput,
) =>
  api<DiscoveryCluster>(`/api/discovery/clusters/${id}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });

export const deleteDiscoveryCluster = (id: string) =>
  api<{ ok: boolean }>(`/api/discovery/clusters/${id}`, { method: "DELETE" });

export const startDiscoveryRun = (body: DiscoveryRunRequest) =>
  api<DiscoveryRunCreated>("/api/discovery/runs", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getRun = (id: string) => api<RunStatus>(`/api/discovery/runs/${id}`);

export const listRuns = (limit = 20, sourceKind?: string) => {
  const q = new URLSearchParams({ limit: String(limit) });
  if (sourceKind) q.set("source_kind", sourceKind);
  return api<RunStatus[]>(`/api/discovery/runs?${q.toString()}`);
};

export interface ArticleQuery {
  category?: string;
  status?: ArticleStatus | "all";
  run_id?: string;
  min_score?: number;
  limit?: number;
}
export const listArticles = (q: ArticleQuery = {}) => {
  const sp = new URLSearchParams();
  if (q.category) sp.set("category", q.category);
  if (q.status) sp.set("status", q.status);
  if (q.run_id) sp.set("run_id", q.run_id);
  if (q.min_score != null) sp.set("min_score", String(q.min_score));
  if (q.limit != null) sp.set("limit", String(q.limit));
  return api<Article[]>(`/api/discovery/articles?${sp.toString()}`);
};

export const dismissArticle = (id: string) =>
  api<Article>(`/api/discovery/articles/${id}/dismiss`, { method: "POST" });

export const recentRunEvents = (runId: string, limit = 50) =>
  api<RunEvent[]>(`/api/events/runs/${runId}/recent?limit=${limit}`);

// ── Web Discovery types + endpoints ──────────────────────────────────────────

export type WebDiscoveryClusterPriority =
  | "P1 Critical"
  | "P2 Daily Intelligence"
  | "P3 Weekly Monitoring";

export interface WebDiscoveryCluster {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  priority: WebDiscoveryClusterPriority;
  is_active: boolean;
  include_keywords: string[];
  exclude_keywords: string[];
  geography_focus: string[];
  source_preferences: string[];
  signal_priorities: string[];
  query_count: number;
  signal_count: number;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WebDiscoveryClusterInput {
  name: string;
  description?: string | null;
  priority?: WebDiscoveryClusterPriority;
  is_active?: boolean;
  include_keywords?: string[];
  exclude_keywords?: string[];
  geography_focus?: string[];
  source_preferences?: string[];
  signal_priorities?: string[];
}

export interface WebDiscoveryQuery {
  id: string;
  cluster_id: string;
  label: string;
  search_query: string;
  search_type: "auto" | "fast" | "deep" | "deep-lite" | "deep-reasoning" | "instant";
  num_results: number;
  content_highlights: boolean;
  content_text: boolean;
  content_summary: boolean;
  structured_outputs: boolean;
  highlights_max_chars: number | null;
  highlights_guiding_query: string | null;
  text_max_chars: number | null;
  text_main_content_only: boolean;
  summary_max_chars: number | null;
  system_prompt: string | null;
  output_schema: Record<string, unknown> | null;
  livecrawl_timeout_ms: number;
  max_age_hours: number | null;
  subpages: number;
  extra_links: number;
  extra_image_links: number;
  subpage_target_keywords: string[];
  category: string | null;
  user_location: string | null;
  include_domains: string[];
  exclude_domains: string[];
  published_after: string | null;
  published_before: string | null;
  crawled_after: string | null;
  crawled_before: string | null;
  content_moderation: boolean;
  stream_response: boolean;
  additional_queries: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WebDiscoveryQueryInput {
  label: string;
  search_query: string;
  search_type?: WebDiscoveryQuery["search_type"];
  num_results?: number;
  content_highlights?: boolean;
  content_text?: boolean;
  content_summary?: boolean;
  structured_outputs?: boolean;
  highlights_max_chars?: number | null;
  highlights_guiding_query?: string | null;
  text_max_chars?: number | null;
  text_main_content_only?: boolean;
  summary_max_chars?: number | null;
  system_prompt?: string | null;
  output_schema?: Record<string, unknown> | null;
  livecrawl_timeout_ms?: number;
  max_age_hours?: number | null;
  subpages?: number;
  extra_links?: number;
  extra_image_links?: number;
  subpage_target_keywords?: string[];
  category?: string | null;
  user_location?: string | null;
  include_domains?: string[];
  exclude_domains?: string[];
  published_after?: string | null;
  published_before?: string | null;
  crawled_after?: string | null;
  crawled_before?: string | null;
  content_moderation?: boolean;
  stream_response?: boolean;
  additional_queries?: string[];
  is_active?: boolean;
}

export interface WebDiscoveryRun {
  id: string;
  status: string;
  progress_pct: number;
  source_kind: string;
  query: string;
  display_name?: string;
  engines: Record<string, unknown>;
  engine_outputs: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  created_at: string;
}

export interface WebDiscoveryQueryRun {
  id: string;
  display_name: string;
  status: string;
  result_count: number;
  completed_at: string | null;
  created_at: string;
  run_scope: string | null;
}

export interface WebDiscoveryRunCreated {
  run_id: string;
  status: string;
  cluster_id: string;
  cluster_name: string;
  query_count: number;
  sse_url: string;
  poll_url: string;
}

export const listWebDiscoveryClusters = () =>
  api<{ clusters: WebDiscoveryCluster[] }>("/api/web-discovery/clusters");

export const createWebDiscoveryCluster = (body: WebDiscoveryClusterInput) =>
  api<WebDiscoveryCluster>("/api/web-discovery/clusters", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getWebDiscoveryCluster = (id: string) =>
  api<WebDiscoveryCluster>(`/api/web-discovery/clusters/${id}`);

export const updateWebDiscoveryCluster = (id: string, body: WebDiscoveryClusterInput) =>
  api<WebDiscoveryCluster>(`/api/web-discovery/clusters/${id}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });

export const deleteWebDiscoveryCluster = (id: string) =>
  api<{ ok: boolean }>(`/api/web-discovery/clusters/${id}`, { method: "DELETE" });

export const listWebDiscoveryQueries = (clusterId: string) =>
  api<WebDiscoveryQuery[]>(`/api/web-discovery/clusters/${clusterId}/queries`);

export const createWebDiscoveryQuery = (clusterId: string, body: WebDiscoveryQueryInput) =>
  api<WebDiscoveryQuery>(`/api/web-discovery/clusters/${clusterId}/queries`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getWebDiscoveryQuery = (queryId: string) =>
  api<WebDiscoveryQuery>(`/api/web-discovery/queries/${queryId}`);

export const updateWebDiscoveryQuery = (queryId: string, body: WebDiscoveryQueryInput) =>
  api<WebDiscoveryQuery>(`/api/web-discovery/queries/${queryId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });

export const startWebDiscoveryClusterRun = (clusterId: string, queryId?: string) =>
  api<WebDiscoveryRunCreated>(`/api/web-discovery/clusters/${clusterId}/runs`, {
    method: "POST",
    body: JSON.stringify(queryId ? { query_id: queryId } : {}),
  });

export const listWebDiscoveryClusterRuns = (clusterId: string, limit = 20) =>
  api<WebDiscoveryRun[]>(`/api/web-discovery/clusters/${clusterId}/runs?limit=${limit}`);

export const listWebDiscoveryQueryRuns = (queryId: string, limit = 30) =>
  api<WebDiscoveryQueryRun[]>(
    `/api/web-discovery/queries/${queryId}/runs?limit=${limit}`,
  );

export const getWebDiscoveryRun = (runId: string) =>
  api<WebDiscoveryRun>(`/api/web-discovery/runs/${runId}`);

export interface WebDiscoveryResultItem {
  url: string;
  exa_id?: string | null;
  title: string | null;
  snippet: string | null;
  published_date: string | null;
  score: number | null;
  highlights: string[] | null;
  summary: string | null;
  text: string | null;
  image: string | null;
  favicon: string | null;
  author: string | null;
}

export interface WebDiscoveryQueryResultsPayload {
  query_id: string;
  run_id: string;
  status: string;
  result_count: number;
  latency_ms: number | null;
  cost_usd: number;
  error: string | null;
  completed_at: string | null;
  query_label?: string | null;
  search_query?: string | null;
  search_type?: string | null;
  num_results?: number | null;
  content_modes?: string[];
  results: WebDiscoveryResultItem[];
  available_runs?: WebDiscoveryQueryRun[];
}

export const getWebDiscoveryQueryResults = (queryId: string, runId?: string) => {
  const qs = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return api<WebDiscoveryQueryResultsPayload>(
    `/api/web-discovery/queries/${queryId}/results${qs}`,
  );
};

// ── Research types + endpoints ───────────────────────────────────────────────

export interface ResearchRunRequest {
  company_name: string;
  domain_hint?: string | null;
  trend_article_id?: string | null;
}

export interface ResearchRunCreated {
  run_id: string;
  status: string;
  company_name: string;
  sse_url: string;
  poll_url: string;
}

export interface ResearchRunStatus extends RunStatus {
  engine_outputs: Record<string, unknown>;
  company_id: string | null;
  card_id: string | null;
}

/** The full CompanyCardV1 JSON. We treat it as opaque on the client — sub-
 *  blocks are rendered defensively from `card.card` using optional chaining. */
export interface CardOut {
  id: string;
  company_id: string;
  run_id: string | null;
  schema_version: string;
  review_status: string;
  score_overall: number | null;
  score_growth: number | null;
  score_momentum: number | null;
  score_fundraising: number | null;
  score_acquisition: number | null;
  score_partnership_fit: number | null;
  score_strategic_fit: number | null;
  score_risk: number | null;
  card: Record<string, any>;
  created_at: string;
}

export interface CompanyOut {
  id: string;
  company_name: string;
  domain: string | null;
  website: string | null;
  logo_url: string | null;
  industry: string | null;
  category: string | null;
  status: string | null;
  headquarters_country: string | null;
  canonical_card_id: string | null;
  score_overall: number | null;
  created_at: string;
}

export interface SignalRow {
  id: string;
  type: string;
  subtype: string | null;
  headline: string;
  evidence: string | null;
  weight: number;
  signal_date: string | null;
  source_refs: number[];
}

export interface SourceRow {
  id: string;
  local_id: number;
  url: string;
  title: string | null;
  type: string | null;
  trust_tier: string | null;
  date_published: string | null;
  snippet: string | null;
  freshness_score: number | null;
}

export interface CompanyDetail {
  company: CompanyOut;
  card: CardOut | null;
  signals: SignalRow[];
  sources: SourceRow[];
}

export const startResearchRun = (body: ResearchRunRequest) =>
  api<ResearchRunCreated>("/api/research/runs", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getResearchRun = (id: string) =>
  api<ResearchRunStatus>(`/api/research/runs/${id}`);

/** Soft-cancel a research run. Returns the updated row (status="cancelled"
 *  if it was in flight, or its original terminal status otherwise). */
export const cancelResearchRun = (id: string) =>
  api<ResearchRunStatus>(`/api/research/runs/${id}/cancel`, {
    method: "POST",
  });

export const getCard = (id: string) => api<CardOut>(`/api/research/cards/${id}`);

export const listCompanies = (limit = 50) =>
  api<CompanyOut[]>(`/api/research/companies?limit=${limit}`);

export const getCompany = (id: string) =>
  api<CompanyDetail>(`/api/research/companies/${id}`);

// ── Company evidence (raw engine I/O) ────────────────────────────────────────

export interface DiffbotPerson {
  name: string;
  title?: string;
  role?: string;
  summary?: string;
  linkedInUri?: string;
  twitterUri?: string;
  email?: string;
}

export interface DiffbotEvidence {
  status: string;
  score: number;
  hits: number;
  latency_ms: number;
  identity: {
    name?: string | null;
    aka?: string | null;
    description?: string | null;
    homepage?: string | null;
    hq?: string | null;
    founded?: string | null;
    is_public?: boolean | null;
    stock?: string | null;
  };
  people: {
    ceo?: DiffbotPerson | null;
    founders: DiffbotPerson[];
    executives: DiffbotPerson[];
  };
  traction: { employees?: string | number | null };
  finance: {
    investments: Array<{
      date?: string | null;
      amount_usd?: string | number | null;
      series?: string | null;
      investors?: string[];
    }>;
    investment_count: number;
  };
  market: {
    industries: string[];
    categories: string[];
    competitors: string[];
  };
  links: Array<{ label: string; url: string }>;
  origins: string[];
  field_count: number;
}

export interface ParallelSignal {
  type?: string;
  date?: string | null;
  headline?: string;
  evidence?: string | null;
  weight?: number | null;
  source_urls?: string[];
}

export interface ParallelSource {
  url: string;
  title?: string | null;
  date_published?: string | null;
  trust_tier?: string | null;
}

export interface ParallelBrief {
  company_name?: string;
  legal_entity_name?: string | null;
  domain?: string | null;
  website?: string | null;
  headquarters?: string | null;
  founded_year?: number | null;
  founders?: string[];
  ceo?: string | null;
  status?: string | null;
  industry?: string | null;
  category?: string | null;
  business_type?: string | null;
  summary?: string;
  products?: string[];
  revenue_estimate_usd?: string | null;
  employee_count_estimate?: number | null;
  hiring_pace?: string | null;
  total_funding_usd?: number | null;
  last_round_type?: string | null;
  last_round_date?: string | null;
  last_round_amount_usd?: number | null;
  investors?: string[];
  competitors?: string[];
  competitive_advantage?: string | null;
  signals?: ParallelSignal[];
  sources?: ParallelSource[];
  notes_for_synthesizer?: string | null;
  [key: string]: unknown;
}

export interface ParallelBasisCitation {
  url?: string;
  title?: string | null;
  excerpts?: string[];
}

export interface ParallelBasisField {
  field?: string;
  citations?: ParallelBasisCitation[];
  reasoning?: string | null;
  confidence?: string | null;
}

export interface ParallelEvidence {
  status: string;
  processor?: string | null;
  latency_ms: number;
  cost_usd: number;
  brief: ParallelBrief;
  basis?: ParallelBasisField[];
  citations: unknown[];
  signal_count: number;
  source_count: number;
  basis_field_count?: number;
}

export interface ExaSearchRow {
  query?: string;
  search_type?: string;
  deep_model?: string;
  num_results?: number;
  urls: string[];
  count: number;
  latency_ms: number;
}

export interface ExaPageRow {
  url: string;
  title?: string | null;
  chars?: number;
  text_preview?: string | null;
  published_date?: string | null;
  snippet_source?: string;
}

export interface ExaEvidence {
  search_count: number;
  page_count: number;
  searches: ExaSearchRow[];
  pages: ExaPageRow[];
}

export interface CompanyEvidenceSummary {
  has_evidence: boolean;
  engine_count: number;
  total_cost_usd: number;
  diffbot_score?: number | null;
  parallel_signals: number;
  exa_pages: number;
  diffbot_fields?: number | null;
}

export interface CompanyEvidence {
  company_id: string;
  run_id: string | null;
  card_id: string | null;
  collected_at: string | null;
  diffbot: DiffbotEvidence | null;
  parallel: ParallelEvidence | null;
  exa: ExaEvidence;
  summary: CompanyEvidenceSummary;
}

export const getCompanyEvidence = (id: string) =>
  api<CompanyEvidence>(`/api/research/companies/${id}/evidence`);

/** Past research runs for a company — newest first. Used to render the
 *  "Profile history" timeline on the company page. */
export const listCompanyResearchRuns = (companyId: string, limit = 20) =>
  api<ResearchRunStatus[]>(
    `/api/research/companies/${companyId}/runs?limit=${limit}`,
  );

/** One row of the Companies command-center feed. */
export interface CompanyFeedRow {
  bucket_key: string;
  company_id: string | null;
  company_name: string;
  domain: string | null;
  industry: string | null;
  score_overall: number | null;
  card_id: string | null;
  latest_run: ResearchRunStatus;
  run_count: number;
  is_live: boolean;
}

export const listCompanyFeed = (limit = 50) =>
  api<CompanyFeedRow[]>(`/api/research/feed?limit=${limit}`);

// ── Settings types ───────────────────────────────────────────────────────────

export interface ParallelConfig {
  processor: string;
  timeout_s: number;
}
export interface ExaConfig {
  search_type: string;
  deep_model: string;
  num_results: number;
}
export interface DiffbotConfig {
  enabled: boolean;
  score_threshold: number;
}
export interface ResearchConfig {
  parallel: ParallelConfig;
  exa: ExaConfig;
  diffbot: DiffbotConfig;
}
export interface ResearchConfigOptions {
  parallel_processors: string[];
  exa_search_types: string[];
  exa_deep_models: string[];
}
export type ResearchConfigPatch = {
  parallel?: Partial<ParallelConfig>;
  exa?: Partial<ExaConfig>;
  diffbot?: Partial<DiffbotConfig>;
};

export const getResearchConfig = () =>
  api<ResearchConfig>("/api/settings/research");

export const getResearchConfigOptions = () =>
  api<ResearchConfigOptions>("/api/settings/research/options");

export const updateResearchConfig = (patch: ResearchConfigPatch) =>
  api<ResearchConfig>("/api/settings/research", {
    method: "PUT",
    body: JSON.stringify(patch),
  });

// ── SSE helper ───────────────────────────────────────────────────────────────

/** Subscribes to the SSE stream for a run. Returns a cleanup fn. */
export function subscribeRunEvents(
  runId: string,
  onEvent: (ev: RunEvent) => void,
  onError?: (err: Event) => void,
  onOpen?: () => void,
): () => void {
  const sseUrl = API_BASE
    ? `${API_BASE}/api/events/runs/${runId}`
    : `/api/events/runs/${runId}`;
  const es = new EventSource(sseUrl);
  es.onopen = () => {
    if (onOpen) onOpen();
  };
  es.onmessage = (m) => {
    if (!m.data) return;
    try {
      onEvent(JSON.parse(m.data) as RunEvent);
    } catch {
      /* ignore non-JSON keep-alives */
    }
  };
  if (onError) es.onerror = onError;
  return () => es.close();
}
