import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  Building2,
  Compass,
  Activity,
  TrendingUp,
} from "lucide-react";

import { Topbar } from "@/components/layout/Topbar";
import { PageBody } from "@/components/ui/PageBody";
import { getHealthDb } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function Home() {
  const dbHealth = useQuery({
    queryKey: ["health-db"],
    queryFn: getHealthDb,
    refetchInterval: 30_000,
  });

  return (
    <>
      <Topbar
        title="Dashboard"
        subtitle="Find companies. Build profiles. Track signals."
      />
      <PageBody>
        {/* Hero CTA */}
        <section className="relative overflow-hidden rounded-xl border border-border bg-gradient-to-br from-white via-white to-tint/40 p-6 shadow-soft sm:p-8">
          <span
            aria-hidden
            className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-accent/5 blur-3xl"
          />
          <span
            aria-hidden
            className="pointer-events-none absolute -left-24 bottom-0 h-48 w-48 rounded-full bg-navy/5 blur-3xl"
          />
          <div className="relative flex flex-col items-start gap-5 md:flex-row md:items-center md:justify-between md:gap-6">
            <div className="max-w-2xl">
              <p className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-accent">
                <span className="inline-block h-1 w-1 rounded-full bg-accent" />
                Company Discovery
              </p>
              <h2 className="mt-2.5 text-xl font-semibold tracking-tight text-navy sm:text-[26px] sm:leading-[1.15]">
                From a query to a complete intel profile.
              </h2>
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted">
                Run a discovery query — Parallel and Exa search in parallel,
                Claude synthesizes the result into a structured Company Card.
              </p>
            </div>
            <Link
              to="/discover"
              className={cn(
                "group inline-flex w-full shrink-0 items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5",
                "text-sm font-semibold text-white shadow-sm ring-1 ring-accent/20 transition hover:bg-accent/90 hover:shadow md:w-auto",
              )}
            >
              <Compass className="h-4 w-4" />
              Start Discovery
              <ArrowUpRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </Link>
          </div>
        </section>

        {/* Stats */}
        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Companies" value="0" icon={Building2} />
          <StatCard label="Runs (24h)" value="0" icon={Activity} />
          <StatCard label="Signals (7d)" value="0" icon={TrendingUp} />
          <StatCard
            label="System"
            value={
              dbHealth.isLoading
                ? "…"
                : dbHealth.data?.status === "ok"
                  ? "OK"
                  : "Degraded"
            }
            icon={ArrowUpRight}
            tone={dbHealth.data?.status === "ok" ? "positive" : "neutral"}
          />
        </section>

        {/* Recent runs (placeholder) */}
        <section className="mt-10">
          <div className="mb-3 flex items-end justify-between">
            <div>
              <h3 className="text-sm font-semibold text-ink">Recent runs</h3>
              <p className="mt-0.5 text-[11px] text-muted">
                Your latest company-discovery runs will appear here.
              </p>
            </div>
            <Link
              to="/companies"
              className="text-xs font-semibold text-accent hover:underline"
            >
              View all companies →
            </Link>
          </div>
          <div className="rounded-xl border border-dashed border-border bg-gradient-to-b from-white to-tint/20 px-6 py-14 text-center">
            <div className="mx-auto grid h-10 w-10 place-items-center rounded-lg border border-border bg-white shadow-soft">
              <Compass className="h-4 w-4 text-soft" />
            </div>
            <p className="mt-3 text-sm text-muted">
              No runs yet. Hit <span className="font-semibold text-ink">Start Discovery</span> to build your first Company Card.
            </p>
          </div>
        </section>
      </PageBody>
    </>
  );
}

function StatCard({
  label,
  value,
  icon: Icon,
  tone = "neutral",
}: {
  label: string;
  value: string;
  icon: typeof Building2;
  tone?: "neutral" | "positive";
}) {
  return (
    <div className="group relative overflow-hidden rounded-xl border border-border bg-white px-5 py-4 shadow-soft transition hover:border-ink/15 hover:shadow">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">
          {label}
        </span>
        <div
          className={cn(
            "grid h-6 w-6 place-items-center rounded-md ring-1",
            tone === "positive"
              ? "bg-emerald-50 ring-emerald-100"
              : "bg-tint/60 ring-border",
          )}
        >
          <Icon
            className={cn(
              "h-3.5 w-3.5",
              tone === "positive" ? "text-emerald-600" : "text-soft",
            )}
          />
        </div>
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-tight tabular-nums text-navy">
        {value}
      </div>
    </div>
  );
}
