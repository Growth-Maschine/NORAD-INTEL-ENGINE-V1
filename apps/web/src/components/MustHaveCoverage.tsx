import { useState } from "react";
import { ChevronDown, ChevronUp, CheckCircle2, AlertCircle, MinusCircle } from "lucide-react";

import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import type {
  ProfileCompletenessGroup,
  ProfileCompletenessOut,
  ProfileCompletenessParam,
} from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Profile Completeness — renders materialized rows from
 * ``GET /api/research/companies/:id/profile-completeness``.
 */

type Status = "verified" | "uncertain" | "missing";

const STATUS_META: Record<
  Status,
  { label: string; icon: typeof CheckCircle2; chip: string; dot: string }
> = {
  verified: {
    label: "Verified",
    icon: CheckCircle2,
    chip: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-500",
  },
  uncertain: {
    label: "Uncertain",
    icon: AlertCircle,
    chip: "bg-amber-50 text-amber-700 border-amber-200",
    dot: "bg-amber-500",
  },
  missing: {
    label: "Missing",
    icon: MinusCircle,
    chip: "bg-tint text-soft border-border",
    dot: "bg-soft/50",
  },
};

const isEmpty = (v: unknown): boolean => {
  if (v === null || v === undefined) return true;
  if (typeof v === "string") return v.trim() === "";
  if (Array.isArray(v)) return v.length === 0;
  if (typeof v === "object") return Object.keys(v as object).length === 0;
  return false;
};

function display(v: unknown): string {
  if (isEmpty(v)) return "—";
  if (typeof v === "string") return v;
  if (typeof v === "number") return Number.isFinite(v) ? v.toLocaleString() : "—";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (Array.isArray(v)) {
    const parts = v
      .map((x) => (typeof x === "string" ? x : x?.name ?? null))
      .filter((s): s is string => !!s);
    if (parts.length === 0) return `${v.length} item${v.length === 1 ? "" : "s"}`;
    return parts.slice(0, 4).join(", ") + (parts.length > 4 ? ` +${parts.length - 4}` : "");
  }
  if (typeof v === "object") {
    const o = v as Record<string, unknown>;
    if ("low" in o || "high" in o) {
      const cur = (o.currency as string) || "USD";
      const fmt = (n: unknown) =>
        typeof n === "number"
          ? n >= 1e9
            ? `${(n / 1e9).toFixed(1)}B`
            : n >= 1e6
              ? `${(n / 1e6).toFixed(1)}M`
              : n.toLocaleString()
          : "?";
      return `${cur} ${fmt(o.low)}–${fmt(o.high)}`;
    }
    if ("name" in o && typeof o.name === "string") return o.name;
    return JSON.stringify(o).slice(0, 80);
  }
  return String(v);
}

export function MustHaveCoverage({ data }: { data: ProfileCompletenessOut }) {
  const [expanded, setExpanded] = useState(false);

  const { completeness_pct: pct, verified_count: v, uncertain_count: u, missing_count: m, total_count: total, groups } =
    data;

  const visibleGroups = expanded ? groups : groups.slice(0, 1);
  const hiddenRowCount = groups.slice(1).reduce((n, g) => n + g.parameters.length, 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile Completeness</CardTitle>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold tabular-nums text-ink">{pct}%</span>
          <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-soft">
            · {v} verified · {u} uncertain · {m} missing
          </span>
        </div>
      </CardHeader>

      <div className="px-5 pb-3 pt-3">
        <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-tint">
          <div
            className="h-full bg-emerald-500"
            style={{ width: `${(v / Math.max(total, 1)) * 100}%` }}
          />
          <div
            className="h-full bg-amber-400"
            style={{ width: `${(u / Math.max(total, 1)) * 100}%` }}
          />
        </div>
      </div>

      <CardBody className="px-0 py-0">
        <div className="divide-y divide-border/60">
          {visibleGroups.map((g) => (
            <GroupBlock key={g.group_name} group={g} />
          ))}
        </div>

        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="flex w-full items-center justify-center gap-1.5 border-t border-border/60 bg-tint/30 px-5 py-2.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-soft transition-colors hover:bg-tint/60 hover:text-ink"
        >
          {expanded ? (
            <>
              <ChevronUp className="h-3 w-3" />
              Show less
            </>
          ) : (
            <>
              <ChevronDown className="h-3 w-3" />
              Show full audit · {hiddenRowCount} more
            </>
          )}
        </button>
      </CardBody>
    </Card>
  );
}

function GroupBlock({ group }: { group: ProfileCompletenessGroup }) {
  return (
    <section>
      <header className="flex items-center justify-between bg-tint/40 px-5 py-2">
        <span className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-soft">
          {group.group_name}
        </span>
        <span className="flex items-center gap-2 text-[10px] font-medium text-soft">
          <span className="inline-flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            {group.verified_count}
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
            {group.uncertain_count}
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-soft/40" />
            {group.missing_count}
          </span>
        </span>
      </header>
      <ul>
        {group.parameters.map((param) => (
          <ParamRow key={param.param_key} param={param} />
        ))}
      </ul>
    </section>
  );
}

function ParamRow({ param }: { param: ProfileCompletenessParam }) {
  const [open, setOpen] = useState(false);
  const status = param.coverage_status as Status;
  const meta = STATUS_META[status] ?? STATUS_META.missing;
  const Icon = meta.icon;
  const hasDetails =
    !!param.basis || (param.source_refs?.length ?? 0) > 0 || !isEmpty(param.value);

  return (
    <li className="border-t border-border/40 first:border-t-0">
      <button
        type="button"
        onClick={() => hasDetails && setOpen((o) => !o)}
        className={cn(
          "flex w-full items-center gap-3 px-5 py-2.5 text-left transition-colors",
          hasDetails ? "hover:bg-tint/40" : "cursor-default",
        )}
      >
        <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", meta.dot)} />
        <span className="flex-1 truncate text-[12.5px] font-medium text-ink">{param.label}</span>
        <span
          className={cn(
            "max-w-[40%] truncate text-right text-[12px] tabular-nums",
            status === "missing" ? "text-soft/60" : "text-muted",
          )}
        >
          {display(param.value)}
        </span>
        <span
          className={cn(
            "inline-flex shrink-0 items-center gap-1 rounded-md border px-1.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.06em]",
            meta.chip,
          )}
        >
          <Icon className="h-2.5 w-2.5" />
          {meta.label}
        </span>
        {hasDetails && (
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 shrink-0 text-soft transition-transform",
              open && "rotate-180",
            )}
          />
        )}
      </button>
      {open && hasDetails && (
        <div className="space-y-2 bg-tint/30 px-5 py-3 text-[12px] text-muted">
          {!isEmpty(param.value) && (
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-soft">
                Value
              </div>
              {typeof param.value === "string" ? (
                <p className="mt-1 whitespace-pre-wrap break-words text-ink/80">{param.value}</p>
              ) : (
                <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] text-ink/80">
                  {JSON.stringify(param.value, null, 2)}
                </pre>
              )}
            </div>
          )}
          {param.confidence && param.confidence !== "unknown" && (
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-soft">
                Confidence:{" "}
              </span>
              <span className="text-ink capitalize">{param.confidence}</span>
            </div>
          )}
          {param.basis && (
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-soft">
                Basis
              </div>
              <p className="mt-0.5 text-ink/80">{param.basis}</p>
            </div>
          )}
          {param.source_refs && param.source_refs.length > 0 && (
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-soft">
                Sources:{" "}
              </span>
              <span className="text-ink">{param.source_refs.map((n) => `[${n}]`).join(" ")}</span>
            </div>
          )}
        </div>
      )}
    </li>
  );
}
