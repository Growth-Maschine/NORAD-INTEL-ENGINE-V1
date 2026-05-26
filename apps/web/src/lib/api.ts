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

export interface CategoryRef {
  slug: string;
  label: string;
  th_url: string;
}
export interface CategoryGroups {
  groups: Record<string, CategoryRef[]>;
}

export interface DiscoveryRunRequest {
  category: string;
  keyword?: string | null;
  date_from?: string | null;
  date_to?: string | null;
  max_articles?: number;
}

export interface DiscoveryRunCreated {
  run_id: string;
  status: string;
  category: string;
  keyword: string | null;
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

export const getCategories = () => api<CategoryGroups>("/api/discovery/categories");

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
