import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { useState } from "react";
import {
  Bell,
  Briefcase,
  CheckCircle2,
  ChevronRight,
  DollarSign,
  ExternalLink,
  History,
  Info,
  Loader2,
  RadioTower,
  Share2,
  SearchX,
  Target,
  Star,
  Users,
  X,
  XCircle,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { Topbar } from "@/components/layout/Topbar";
import { MustHaveCoverage } from "@/components/MustHaveCoverage";
import { CompanyBriefSections } from "@/components/company/CompanyBriefSections";
import { ResearchEvidence } from "@/components/company/ResearchEvidence";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { MetricBar } from "@/components/ui/MetricBar";
import { PageBody } from "@/components/ui/PageBody";
import { Pill } from "@/components/ui/Pill";
import { ScoreBar } from "@/components/ui/ScoreBar";
import { StrategicFitText } from "@/components/ui/StrategicFitText";
import { HoverTip } from "@/components/ui/Tooltip";
import {
  cancelResearchRun,
  getCompany,
  listCompanyResearchRuns,
  type CompanyDetail,
  type ResearchRunStatus,
  type SourceRow,
} from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Real CompanyCardV1 viewer. Pulls /api/research/companies/:id and renders
 * defensively from the JSON — every block uses optional chaining because the
 * synthesizer may have left half the card as `Valued(unknown)`.
 */
export default function CompanyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const q = useQuery({
    queryKey: ["company", id],
    queryFn: () => (id ? getCompany(id) : Promise.resolve(null)),
    enabled: !!id,
    refetchInterval: 30000,
  });
  const data = q.data ?? null;

  if (q.isLoading) {
    return (
      <>
        <Topbar title="Company" subtitle="Loading…" />
        <PageBody>
          <div className="rounded-xl border border-dashed border-border bg-white px-6 py-16 text-center text-sm text-soft">
            <Loader2 className="mx-auto mb-3 h-5 w-5 animate-spin" />
            Loading card…
          </div>
        </PageBody>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <Topbar title="Company" subtitle="Not found" />
        <PageBody>
          <EmptyState
            icon={SearchX}
            title="Company not found"
            description="This company id doesn't exist. Try the Companies list."
          />
        </PageBody>
      </>
    );
  }

  return <CompanyCardView data={data} />;
}

function CompanyCardView({ data }: { data: CompanyDetail }) {
  const { company, card, signals, sources } = data;
  const c = card?.card ?? {};
  const identity = c.company_identity ?? {};
  const classification = c.classification ?? {};
  const fit = c.strategic_fit ?? {};
  const financials = c.financials ?? {};
  const funding = c.funding_and_investors ?? {};
  const traction = c.traction_and_momentum ?? {};
  const market = c.market_and_competitors ?? {};
  const people = c.people_and_decision_map ?? {};

  const description: string | undefined =
    typeof identity.description === "string" ? identity.description : undefined;

  const fitSummary: string | undefined = fit.fit_summary?.value;
  const recAction: string | undefined = fit.recommended_next_action?.value;
  const recRationale: string | undefined = fit.recommended_action_rationale?.value;

  const sc = c.sources_and_confidence ?? {};
  const overallConfidence: string | undefined = sc.overall_confidence;
  const coverageSummary: string | undefined = sc.coverage_summary;
  const gaps: string[] = Array.isArray(sc.gaps) ? sc.gaps : [];

  const initials = (company.company_name || "?")
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();

  const fitTone =
    recAction?.startsWith("outreach")
      ? "Strong Fit"
      : recAction === "monitor"
        ? "Monitor"
        : recAction === "pass"
          ? "Pass"
          : "Reviewing";

  // Grouped fact panels — replaces the old uniform 3×3 cell grid. Each group
  // gets an icon + section label; numeric facts (money) get emphasized type so
  // the eye lands on what matters instead of skimming a spreadsheet.
  type FactItem = {
    k: string;
    v: string | number | null | undefined;
    emphasis?: boolean;
  };
  const factGroups: { label: string; icon: typeof Briefcase; items: FactItem[] }[] = [
    {
      label: "Classification",
      icon: Briefcase,
      items: [
        { k: "Industry", v: classification.industry ?? company.industry },
        { k: "Category", v: classification.category ?? company.category },
        { k: "Business Type", v: classification.business_type },
        { k: "Status", v: identity.status ?? company.status },
      ],
    },
    {
      label: "Financials",
      icon: DollarSign,
      items: [
        {
          k: "Funding (total)",
          v: fmtMoneyRange(funding.total_funding?.value),
          emphasis: true,
        },
        {
          k: "Last Round",
          v: funding.last_round_type
            ? `${funding.last_round_type}${funding.last_round_date ? " · " + funding.last_round_date : ""}`
            : null,
        },
        {
          k: "Revenue Est.",
          v: fmtMoneyRange(financials.revenue_estimate?.value),
          emphasis: true,
        },
      ],
    },
    {
      label: "Team",
      icon: Users,
      items: [
        {
          k: "Employees",
          v: traction.employee_count_estimate?.value,
          emphasis: true,
        },
        { k: "Hiring", v: traction.hiring_pace?.value },
      ],
    },
  ];

  const rail: { k: string; v: string | number | null | undefined }[] = [
    { k: "Domain", v: identity.domain ?? company.domain },
    { k: "Founded", v: identity.founded_year ?? identity.founded_date },
    { k: "CEO", v: people.ceo?.name },
    {
      k: "Sector",
      v: classification.sector,
    },
    { k: "HQ", v: identity.headquarters },
    { k: "Stage", v: funding.last_round_type },
  ];

  const breakdown = [
    { label: "Strategic Fit", value: card?.score_strategic_fit, accent: "navy" as const },
    { label: "Growth Momentum", value: card?.score_momentum, accent: "emerald" as const },
    { label: "Fundraising Signal", value: card?.score_fundraising, accent: "amber" as const },
    { label: "Acquisition Signal", value: card?.score_acquisition, accent: "amber" as const },
    { label: "Partnership Fit", value: card?.score_partnership_fit, accent: "accent" as const },
    { label: "Risk", value: card?.score_risk, accent: "emerald" as const },
  ];

  const domain = company.domain ?? identity.domain ?? null;

  return (
    <>
      <Topbar
        title={company.company_name}
        subtitle={domain ?? "no domain on file"}
      />
      <PageBody className="bg-tint/40">
        <nav className="mb-4 flex items-center gap-1 text-xs text-muted">
          <Link to="/companies" className="hover:text-ink">
            Companies
          </Link>
          <ChevronRight className="h-3 w-3 text-soft" />
          <span className="font-medium text-ink">{company.company_name}</span>
        </nav>

        {/* Header */}
        <Card className="px-6 py-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <CompanyAvatar
                domain={domain}
                initials={initials}
              />
              <div className="min-w-0">
                <h1 className="text-2xl font-semibold tracking-tight text-ink">
                  {company.company_name}
                </h1>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {classification.industry && (
                    <Pill variant="neutral">{classification.industry}</Pill>
                  )}
                  {funding.last_round_type && (
                    <Pill variant="navy">{funding.last_round_type}</Pill>
                  )}
                  <Pill variant="accent">{fitTone}</Pill>
                  {overallConfidence && (
                    <HoverTip
                      label={
                        <div className="space-y-1">
                          <div className="font-semibold capitalize">
                            {overallConfidence} confidence
                          </div>
                          {coverageSummary && (
                            <div className="text-white/80">{coverageSummary}</div>
                          )}
                          {gaps.length > 0 && (
                            <div className="text-white/70">
                              Gaps: {gaps.slice(0, 3).join("; ")}
                            </div>
                          )}
                        </div>
                      }
                    >
                      <button
                        type="button"
                        className={cn(
                          "inline-flex cursor-help items-center gap-1 rounded-md border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.06em]",
                          overallConfidence === "high"
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                            : overallConfidence === "medium"
                              ? "border-amber-200 bg-amber-50 text-amber-700"
                              : overallConfidence === "low"
                                ? "border-red-200 bg-red-50 text-red-700"
                                : "border-border bg-tint text-soft",
                        )}
                      >
                        <Info className="h-3 w-3" />
                        {overallConfidence} confidence
                      </button>
                    </HoverTip>
                  )}
                  {domain && (
                    <a
                      href={`https://${domain}`}
                      target="_blank"
                      rel="noreferrer"
                      className="ml-1 inline-flex items-center gap-1 text-xs text-muted hover:text-ink"
                    >
                      {domain}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-3 py-1.5 text-xs font-medium text-ink hover:bg-tint"
              >
                <Star className="h-3.5 w-3.5" />
                Follow
              </button>
              <button
                type="button"
                className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-3 py-1.5 text-xs font-medium text-ink hover:bg-tint"
              >
                <Bell className="h-3.5 w-3.5" />
                Signal Alert
              </button>
              <button
                type="button"
                className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-3 py-1.5 text-xs font-medium text-ink hover:bg-tint"
              >
                <Share2 className="h-3.5 w-3.5" />
                Share
              </button>
            </div>
          </div>
        </Card>

        {/* Two-column body */}
        <div className="mt-6 grid grid-cols-12 gap-6">
          <div className="col-span-12 space-y-6 lg:col-span-8">
            {/* Company facts — grouped into Classification / Financials / Team
                with subtle icons + a clearer visual hierarchy. Money values get
                slightly larger numerals (tabular-nums) so they read as data, not
                another row of label/value. Replaces the old uniform 3×3 cell
                grid which felt tabular. */}
            {/* Premium key-stat panel: label-above-value stack instead of an
                inline label/value table. Long values like
                "Wellness and Fitness Services" no longer fight a right-aligned
                column — they get their own line with consistent left alignment,
                so the eye scans top-to-bottom in each panel instead of
                zig-zagging. Money/headcount stay as emphasized tabular-nums. */}
            <Card>
              <CardBody className="grid grid-cols-1 gap-0 divide-y divide-border/60 p-0 md:grid-cols-3 md:divide-x md:divide-y-0">
                {factGroups.map((group) => {
                  const Icon = group.icon;
                  return (
                    <div key={group.label} className="px-5 py-5">
                      <div className="mb-4 flex items-center gap-2 text-soft">
                        <Icon className="h-3.5 w-3.5" />
                        <span className="text-[10.5px] font-semibold uppercase tracking-[0.12em]">
                          {group.label}
                        </span>
                      </div>
                      <dl className="space-y-3.5">
                        {group.items.map((item) => {
                          const v = fmt(item.v);
                          const isEmpty = v == null;
                          return (
                            <div
                              key={item.k}
                              className="group/stat -mx-2 rounded-md px-2 py-1 transition-colors hover:bg-tint/60"
                            >
                              <dt className="text-[10px] font-medium uppercase tracking-[0.1em] text-soft">
                                {item.k}
                              </dt>
                              <dd
                                className={cn(
                                  "mt-0.5 text-ink",
                                  item.emphasis
                                    ? "text-[15px] font-semibold tabular-nums leading-tight"
                                    : "text-[13.5px] font-medium leading-snug",
                                  isEmpty && "text-soft/50 font-normal",
                                )}
                              >
                                {v ?? "—"}
                              </dd>
                            </div>
                          );
                        })}
                      </dl>
                    </div>
                  );
                })}
              </CardBody>
            </Card>

            {/* Strategic Fit narrative — just the summary; the recommended
                action + rationale moved to the right-rail CTA card so we're
                not saying the same thing twice. */}
            {fitSummary && (
              <Card>
                <CardHeader>
                  <CardTitle>Strategic Fit</CardTitle>
                </CardHeader>
                <CardBody>
                  <StrategicFitText text={fitSummary} />
                </CardBody>
              </Card>
            )}

            {description && (
              <Card>
                <CardHeader>
                  <CardTitle>About</CardTitle>
                </CardHeader>
                <CardBody>
                  <p className="text-sm leading-relaxed text-muted">{description}</p>
                </CardBody>
              </Card>
            )}

            <CompanyBriefSections card={c} />

            {/* Signals */}
            <div>
              <div className="mb-3 flex items-baseline justify-between">
                <h2 className="text-base font-semibold text-ink">
                  Signals
                </h2>
                <span className="text-xs text-muted">
                  {signals.length} on record
                </span>
              </div>

              {signals.length === 0 ? (
                <EmptyState
                  icon={RadioTower}
                  title="No structured signals on this card"
                  description={
                    sources.length === 0
                      ? "The deep research run completed but didn't surface specific growth, funding, or momentum signals strong enough to record. The narrative above still draws on the underlying research — re-run for a fresh synthesis if you need cited evidence."
                      : "The deep research run cited sources but Claude didn't extract discrete signals on this pass. Re-run to retry the synthesis."
                  }
                />
              ) : (
                <Card>
                  <div className="divide-y divide-border">
                    {signals.map((s) => (
                      <article key={s.id} className="p-5">
                        <div className="flex items-start gap-5">
                          <div className="w-20 shrink-0">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-soft">
                              {s.signal_date ?? "—"}
                            </div>
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="mb-2 flex items-center gap-3">
                              <Pill variant="neutral">{s.type}</Pill>
                              <span className="text-[11px] font-semibold text-emerald-600">
                                weight {s.weight}/10
                              </span>
                            </div>
                            <h3 className="text-sm font-semibold text-ink">
                              {s.headline}
                            </h3>
                            {s.evidence && (
                              <p className="mt-1.5 text-[13px] leading-relaxed text-muted">
                                {s.evidence}
                              </p>
                            )}
                            {s.source_refs.length > 0 && (
                              <p className="mt-1.5 text-[11px] text-soft">
                                sources: {s.source_refs.map((n) => `[${n}]`).join(" ")}
                              </p>
                            )}
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                </Card>
              )}
            </div>

            {/* Market & competitors quick view */}
            {(market.direct_competitors?.length ||
              market.competitive_advantage?.value) && (
              <Card>
                <CardHeader>
                  <CardTitle>Market & Competitors</CardTitle>
                </CardHeader>
                <CardBody className="space-y-3 text-sm">
                  {market.competitive_advantage?.value && (
                    <p className="text-muted">
                      <span className="font-semibold text-ink">Moat: </span>
                      {market.competitive_advantage.value}
                    </p>
                  )}
                  {market.direct_competitors?.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {market.direct_competitors.map((n: string) => (
                        <Pill key={n} variant="neutral">
                          {n}
                        </Pill>
                      ))}
                    </div>
                  )}
                </CardBody>
              </Card>
            )}

            {/* Sources */}
            {sources.length > 0 && <SourcesBlock sources={sources} />}
          </div>

          {/* Right rail */}
          <aside className="col-span-12 space-y-4 lg:col-span-4">
            {/* Hero CTA — what GM should actually do, why. Lifted out of the
                main column so the rail anchors on action, not duplicated
                narrative. */}
            {recAction && (
              <motion.div
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, ease: "easeOut" }}
              >
                <Card className="relative overflow-hidden border-accent/30 bg-white shadow-[0_1px_0_rgba(0,0,0,0.02),0_8px_24px_-14px_rgba(255,107,53,0.22)]">
                  <span
                    aria-hidden
                    className="absolute inset-y-0 left-0 w-[3px] bg-accent"
                  />
                  <CardBody className="space-y-3 py-5 pl-6 pr-5">
                    <span className="text-[10.5px] font-semibold uppercase tracking-[0.08em] text-accent">
                      Recommended action
                    </span>
                    <div className="text-[15px] font-semibold leading-snug text-ink">
                      {recAction.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                    </div>
                    {recRationale && (
                      <p className="text-[12.5px] leading-[1.6] text-muted">
                        {recRationale}
                      </p>
                    )}
                  </CardBody>
                </Card>
              </motion.div>
            )}

            {/* Fit Score */}
            <Card>
              <CardHeader>
                <CardTitle>Fit Score</CardTitle>
                <span className="text-[10px] font-semibold uppercase tracking-[0.06em] text-soft">
                  {signals.length} signals
                </span>
              </CardHeader>
              <CardBody className="space-y-3">
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-semibold tracking-tight text-ink tabular-nums">
                    {card?.score_overall ?? 0}
                  </span>
                  <span className="text-xs text-soft">/ 100</span>
                </div>
                <div
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[10.5px] font-semibold uppercase tracking-[0.06em]",
                    (card?.score_overall ?? 0) >= 70
                      ? "bg-emerald-50 text-emerald-700"
                      : (card?.score_overall ?? 0) >= 40
                        ? "bg-amber-50 text-amber-700"
                        : "bg-tint text-soft",
                  )}
                >
                  <Target className="h-3 w-3" />
                  {(card?.score_overall ?? 0) >= 70
                    ? "Strong Match"
                    : (card?.score_overall ?? 0) >= 40
                      ? "Decent Match"
                      : "Light Match"}
                </div>
                <ScoreBar
                  current={card?.score_overall ?? 0}
                  threshold={50}
                  max={100}
                />
              </CardBody>
            </Card>

            {/* Quick facts — pure identity / who-they-are. No narrative here;
                that lives in Strategic Fit (main column) and the CTA above. */}
            <Card>
              <CardHeader>
                <CardTitle>Quick facts</CardTitle>
              </CardHeader>
              <CardBody className="space-y-2.5">
                {rail
                  .filter((r) => r.v != null && r.v !== "")
                  .map((r) => (
                    <div
                      key={r.k}
                      className="flex items-baseline justify-between gap-3 border-b border-border/40 pb-2 last:border-0 last:pb-0"
                    >
                      <span className="text-[11px] font-medium uppercase tracking-[0.06em] text-soft">
                        {r.k}
                      </span>
                      <span className="text-right text-[13px] font-medium text-ink">
                        {fmt(r.v)}
                      </span>
                    </div>
                  ))}
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Metric Breakdown</CardTitle>
              </CardHeader>
              <CardBody className="space-y-3.5">
                {breakdown.map((b) => (
                  <MetricBar
                    key={b.label}
                    label={b.label}
                    value={b.value ?? 0}
                    accent={b.accent}
                  />
                ))}
              </CardBody>
            </Card>

            <ProfileHistory companyId={company.id} />
          </aside>

          {/* Research Evidence — full-width raw engine data (Diffbot / Parallel / Exa)
              sits above the completeness audit so analysts see everything we
              fetched, not just what synthesis kept in the brief. */}
          <div className="col-span-12">
            <ResearchEvidence companyId={company.id} cardSources={sources} />
          </div>

          {/* Profile Completeness — full-width audit of the must-have NORAD
              parameters. Sits at the bottom of the page (below profile
              history) since it's a diagnostic / coverage view, not part of
              the primary at-a-glance read. Collapsed by default to just
              the Identity group; click "Show full audit" to expand. */}
          <div className="col-span-12">
            <MustHaveCoverage card={c} />
          </div>
        </div>
      </PageBody>
    </>
  );
}

/**
 * Favicon-first avatar. Tries Google's s2 favicon service for the company
 * domain; falls back to a clean initials tile if the image fails to load
 * (the onError flips a state flag).
 */
function CompanyAvatar({
  domain,
  initials,
}: {
  domain: string | null;
  initials: string;
}) {
  const [errored, setErrored] = useState(false);
  const showFavicon = !!domain && !errored;
  return (
    <div className="grid h-14 w-14 shrink-0 place-items-center overflow-hidden rounded-xl border border-border bg-white shadow-sm">
      {showFavicon ? (
        <img
          src={`https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain!)}&sz=128`}
          alt=""
          width={40}
          height={40}
          className="h-10 w-10 rounded-md object-contain"
          onError={() => setErrored(true)}
        />
      ) : (
        <div className="grid h-full w-full place-items-center bg-accent text-base font-bold text-white">
          {initials}
        </div>
      )}
    </div>
  );
}

/**
 * Profile history — every research run we've fired at this company, newest
 * first. Each row links back to /runs/:id so the user can revisit the saved
 * SSE log and the card snapshot from that pass. Active/in-flight runs get an
 * amber spinner so it's obvious one is still cooking.
 */
function ProfileHistory({ companyId }: { companyId: string }) {
  const q = useQuery({
    queryKey: ["company-research-runs", companyId],
    queryFn: () => listCompanyResearchRuns(companyId, 20),
    // Poll while at least one run is still in flight so the active row
    // updates without a full page refresh.
    refetchInterval: (rq) => {
      const rows = rq.state.data as ResearchRunStatus[] | undefined;
      if (!rows || rows.length === 0) return false;
      const live = rows.some(
        (r) =>
          r.status !== "completed" &&
          r.status !== "failed" &&
          r.status !== "cancelled",
      );
      return live ? 3000 : false;
    },
  });
  const runs = q.data ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <History className="mr-1.5 inline h-3.5 w-3.5 -translate-y-px text-soft" />
          Profile history
        </CardTitle>
        {runs.length > 0 && (
          <span className="text-[10px] font-semibold uppercase tracking-[0.06em] text-soft">
            {runs.length} run{runs.length === 1 ? "" : "s"}
          </span>
        )}
      </CardHeader>
      <CardBody className="p-0">
        {q.isLoading ? (
          <div className="flex items-center gap-2 px-4 py-4 text-xs text-soft">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Loading history…
          </div>
        ) : q.isError ? (
          <div className="flex items-start gap-2 px-4 py-4 text-xs text-red-700">
            <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              Couldn't load profile history.{" "}
              <button
                type="button"
                onClick={() => q.refetch()}
                className="font-semibold underline underline-offset-2 hover:text-red-900"
              >
                Retry
              </button>
            </span>
          </div>
        ) : runs.length === 0 ? (
          <div className="px-4 py-4 text-xs text-soft">
            No prior profile runs recorded for this company.
          </div>
        ) : (
          <ol className="divide-y divide-border">
            {runs.map((r) => (
              <ProfileHistoryRow key={r.id} run={r} />
            ))}
          </ol>
        )}
      </CardBody>
    </Card>
  );
}

function ProfileHistoryRow({ run }: { run: ResearchRunStatus }) {
  const isDone = run.status === "completed";
  const isFail = run.status === "failed" || run.status === "cancelled";
  const isLive = !isDone && !isFail;

  const when = run.started_at ?? run.created_at;
  const stamp = when ? formatRunStamp(when) : "—";

  const dotTone = isDone
    ? "bg-emerald-500"
    : isFail
      ? "bg-red-500"
      : "bg-amber-500 animate-pulse";

  const [confirmOpen, setConfirmOpen] = useState(false);
  const qc = useQueryClient();
  const cancelMut = useMutation({
    mutationFn: () => cancelResearchRun(run.id),
    onSuccess: () => {
      // Listing endpoint filters cancelled runs out, so refetching makes
      // this row disappear from the Profile history list.
      qc.invalidateQueries({ queryKey: ["company-research-runs"] });
      // Also bust the run-detail cache in case the user navigates into it.
      qc.invalidateQueries({ queryKey: ["research-run", run.id] });
      setConfirmOpen(false);
    },
  });

  return (
    <li className="group/row relative">
      <Link
        to={`/runs/${run.id}`}
        className="flex items-start gap-3 px-4 py-3 transition hover:bg-tint/40"
      >
        <span
          aria-hidden
          className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", dotTone)}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2">
            <span className="truncate text-[13px] font-medium text-ink">
              {stamp}
            </span>
            <span className="shrink-0 text-[10px] font-mono text-soft">
              {run.id.slice(0, 8)}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-1.5 text-[11px] text-muted">
            {isLive ? (
              <Loader2 className="h-3 w-3 animate-spin text-amber-600" />
            ) : isDone ? (
              <CheckCircle2 className="h-3 w-3 text-emerald-600" />
            ) : (
              <XCircle className="h-3 w-3 text-red-600" />
            )}
            <span className="capitalize">{run.status}</span>
            {isLive && (
              <>
                <span className="text-soft">·</span>
                <span>{run.progress_pct}%</span>
              </>
            )}
          </div>
        </div>
        {isLive ? (
          // Spacer so the right-side icon area stays aligned with terminal
          // rows. The actual cancel button is rendered absolutely below so
          // it can sit outside the <Link> click target.
          <span aria-hidden className="mt-1 h-3.5 w-3.5 shrink-0" />
        ) : (
          <ChevronRight className="mt-1 h-3.5 w-3.5 shrink-0 text-soft transition group-hover/row:translate-x-0.5 group-hover/row:text-ink" />
        )}
      </Link>
      {isLive && (
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setConfirmOpen(true);
          }}
          disabled={cancelMut.isPending}
          aria-label="Cancel this run"
          className={cn(
            "absolute right-3 top-1/2 -translate-y-1/2",
            "inline-flex items-center gap-1 rounded-md border border-border bg-white",
            "px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.06em] text-soft",
            "shadow-sm transition hover:border-red-300 hover:bg-red-50 hover:text-red-700",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400",
            "disabled:cursor-not-allowed disabled:opacity-50",
          )}
        >
          {cancelMut.isPending ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <X className="h-3 w-3" />
          )}
          Cancel
        </button>
      )}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={(v) => {
          if (!cancelMut.isPending) setConfirmOpen(v);
        }}
        title="Cancel this run?"
        description={
          <>
            This will stop research run{" "}
            <span className="font-mono text-ink">{run.id.slice(0, 8)}</span> and
            remove it from this list. The audit log is preserved.
          </>
        }
        confirmText={cancelMut.isPending ? "Cancelling…" : "Cancel run"}
        cancelText="Keep running"
        variant="danger"
        busy={cancelMut.isPending}
        onConfirm={() => cancelMut.mutate()}
      />
    </li>
  );
}

function formatRunStamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (sameDay) {
    return `Today · ${d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`;
  }
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function SourcesBlock({ sources }: { sources: SourceRow[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Sources</CardTitle>
        <span className="text-[10px] uppercase tracking-wider text-soft">
          {sources.length}
        </span>
      </CardHeader>
      <CardBody className="space-y-2">
        {sources.map((s) => (
          <div key={s.id} className="flex items-start gap-3 text-xs">
            <span className="mt-0.5 inline-block w-6 shrink-0 font-mono text-soft">
              [{s.local_id}]
            </span>
            <a
              href={s.url}
              target="_blank"
              rel="noreferrer"
              className="min-w-0 flex-1 text-accent hover:underline"
            >
              <div className="truncate text-sm font-medium">
                {s.title ?? s.url}
              </div>
              <div className="truncate text-[11px] text-muted">{s.url}</div>
            </a>
            {s.trust_tier && (
              <span className="rounded-md bg-tint px-1.5 py-0.5 text-[10px] font-semibold text-muted">
                tier {s.trust_tier}
              </span>
            )}
          </div>
        ))}
      </CardBody>
    </Card>
  );
}

// ── Formatting helpers ───────────────────────────────────────────────────────

function fmt(v: unknown): string | null {
  if (v == null || v === "") return null;
  if (typeof v === "number") return v.toLocaleString();
  if (typeof v === "string") return v;
  return String(v);
}

function fmtMoneyRange(
  r: { low?: number | null; high?: number | null; currency?: string } | null | undefined,
): string | null {
  if (!r || (r.low == null && r.high == null)) return null;
  const cur = r.currency ?? "USD";
  if (r.low != null && r.high != null) {
    return `${cur} ${shortMoney(r.low)}–${shortMoney(r.high)}`;
  }
  return `${cur} ${shortMoney(r.low ?? r.high ?? 0)}`;
}

function shortMoney(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return String(n);
}
