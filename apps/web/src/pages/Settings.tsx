import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleX, Save, Loader2, Activity, Cpu, Database, Globe, Check, ChevronDown } from "lucide-react";

import { Topbar } from "@/components/layout/Topbar";
import { PageBody } from "@/components/ui/PageBody";
import {
  ApiError,
  getHealthDb,
  getResearchConfig,
  getResearchConfigOptions,
  updateResearchConfig,
  type ResearchConfig,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const PARALLEL_BLURB: Record<string, string> = {
  lite: "Fastest, cheapest. Quick lookups, low accuracy.",
  base: "Light research, ~30s.",
  core: "Balanced default. ~60s, mid accuracy.",
  pro: "Deep research, ~5–10 min, ~$0.10/run, 62% on Deep Research Bench.",
  ultra: "Highest single-model accuracy, ~$0.50/run, 68.5% on DRB.",
  ultra2x: "Multi-pass Ultra. Slower / pricier, marginal lift.",
  ultra4x: "4× Ultra ensemble. Very slow / expensive.",
  ultra8x: "8× Ultra ensemble. Maximum cost.",
};

const EXA_TYPE_BLURB: Record<string, string> = {
  auto: "Exa picks the best strategy per query.",
  fast: "Sub-second keyword-style lookup.",
  neural: "Embedding-based semantic search.",
  keyword: "Classic keyword match.",
  deep: "Agentic deep research over the web. Slower, much higher quality.",
};

const EXA_DEEP_BLURB: Record<string, string> = {
  "deep-lite": "Cheapest deep variant.",
  deep: "Standard deep research.",
  "deep-reasoning": "Highest-quality reasoning model. Recommended.",
};

export default function Settings() {
  const queryClient = useQueryClient();
  const dbHealth = useQuery({
    queryKey: ["health-db"],
    queryFn: getHealthDb,
    refetchInterval: 30_000,
  });
  const config = useQuery({
    queryKey: ["research-config"],
    queryFn: getResearchConfig,
  });
  const options = useQuery({
    queryKey: ["research-config-options"],
    queryFn: getResearchConfigOptions,
  });

  const [draft, setDraft] = useState<ResearchConfig | null>(null);
  useEffect(() => {
    if (config.data && !draft) setDraft(config.data);
  }, [config.data, draft]);

  const dirty = useMemo(() => {
    if (!draft || !config.data) return false;
    return JSON.stringify(draft) !== JSON.stringify(config.data);
  }, [draft, config.data]);

  const save = useMutation({
    mutationFn: async () => {
      if (!draft) throw new Error("no draft");
      return updateResearchConfig({ parallel: draft.parallel, exa: draft.exa });
    },
    onSuccess: (next) => {
      queryClient.setQueryData(["research-config"], next);
      setDraft(next);
    },
  });

  const errMsg = (e: unknown) =>
    e instanceof ApiError
      ? `${e.status}: ${e.message}`
      : e instanceof Error
        ? e.message
        : "unknown error";

  return (
    <>
      <Topbar title="Settings" subtitle="Engines, integrations, and system status" />
      <PageBody>
        <section className="overflow-hidden rounded-xl border border-border bg-white shadow-soft">
          <div className="flex items-center justify-between border-b border-border bg-gradient-to-b from-tint/40 to-white px-6 py-4">
            <div className="flex items-center gap-2.5">
              <div className="grid h-7 w-7 place-items-center rounded-md bg-emerald-50 ring-1 ring-emerald-100">
                <Activity className="h-3.5 w-3.5 text-emerald-600" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-ink">System status</h3>
                <p className="mt-0.5 text-[11px] text-muted">
                  Live connectivity check for the storage layer.
                </p>
              </div>
            </div>
          </div>
          <div className="grid gap-3 p-6 sm:grid-cols-2">
            <StatusRow
              label="Postgres (Supabase)"
              icon={Database}
              ok={dbHealth.data?.postgres.ok}
              latency={dbHealth.data?.postgres.latency_ms}
              loading={dbHealth.isLoading}
            />
            <StatusRow
              label="Redis (Upstash)"
              icon={Database}
              ok={dbHealth.data?.redis.ok}
              latency={dbHealth.data?.redis.latency_ms}
              loading={dbHealth.isLoading}
            />
          </div>
        </section>

        <section className="mt-6 overflow-hidden rounded-xl border border-border bg-white shadow-soft">
          <div className="flex items-start justify-between gap-4 border-b border-border bg-gradient-to-b from-tint/40 to-white px-6 py-4">
            <div className="flex items-center gap-2.5">
              <div className="grid h-7 w-7 place-items-center rounded-md bg-accent/10 ring-1 ring-accent/20">
                <Cpu className="h-3.5 w-3.5 text-accent" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-ink">Research engines</h3>
                <p className="mt-0.5 text-[11px] text-muted">
                  Defaults applied to every research run. Changes take effect on
                  the next run.
                </p>
              </div>
            </div>
            <button
              type="button"
              disabled={!dirty || save.isPending}
              onClick={() => save.mutate()}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition",
                dirty && !save.isPending
                  ? "bg-ink text-white shadow-sm hover:bg-ink/90"
                  : "cursor-not-allowed bg-tint text-soft",
              )}
            >
              {save.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Save className="h-3.5 w-3.5" />
              )}
              {save.isPending ? "Saving…" : dirty ? "Save changes" : "Saved"}
            </button>
          </div>

          <div className="p-6">
          {(config.isLoading || options.isLoading || !draft) && (
            <p className="text-xs text-muted">Loading config…</p>
          )}
          {config.error && (
            <p className="text-xs text-red-600">
              Failed to load config: {errMsg(config.error)}
            </p>
          )}
          {save.error && (
            <p className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              Save failed: {errMsg(save.error)}
            </p>
          )}

          {draft && options.data && (
            <div className="grid gap-5 lg:grid-cols-2">
              <EngineCard
                title="Parallel Task API"
                subtitle="Deep research over structured sources (filings, news, blogs)."
                icon={Cpu}
                accent="accent"
              >
                <Field label="Processor">
                  <Select
                    value={draft.parallel.processor}
                    options={options.data.parallel_processors}
                    onChange={(v) =>
                      setDraft({
                        ...draft,
                        parallel: { ...draft.parallel, processor: v },
                      })
                    }
                  />
                  <Hint text={PARALLEL_BLURB[draft.parallel.processor]} />
                </Field>
                <Field label="Timeout (seconds)">
                  <input
                    type="number"
                    min={60}
                    max={3600}
                    step={30}
                    value={draft.parallel.timeout_s}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        parallel: {
                          ...draft.parallel,
                          timeout_s: Number(e.target.value) || 0,
                        },
                      })
                    }
                    className="w-full rounded-md border border-border bg-white px-3 py-1.5 text-sm text-ink focus:border-ink focus:outline-none"
                  />
                  <Hint text="Hard cap per run. Pro typically finishes in 5–10 min." />
                </Field>
              </EngineCard>

              <EngineCard
                title="Exa"
                subtitle="Web search + retrieval. Pulls citations and supporting context."
                icon={Globe}
                accent="navy"
              >
                <Field label="Search type">
                  <Select
                    value={draft.exa.search_type}
                    options={options.data.exa_search_types}
                    onChange={(v) =>
                      setDraft({
                        ...draft,
                        exa: { ...draft.exa, search_type: v },
                      })
                    }
                  />
                  <Hint text={EXA_TYPE_BLURB[draft.exa.search_type]} />
                </Field>
                <Field label="Deep model">
                  <Select
                    value={draft.exa.deep_model}
                    options={options.data.exa_deep_models}
                    disabled={draft.exa.search_type !== "deep"}
                    onChange={(v) =>
                      setDraft({
                        ...draft,
                        exa: { ...draft.exa, deep_model: v },
                      })
                    }
                  />
                  <Hint
                    text={
                      draft.exa.search_type === "deep"
                        ? EXA_DEEP_BLURB[draft.exa.deep_model]
                        : "Only applies when Search type is set to “deep”."
                    }
                  />
                </Field>
                <Field label="Results per query">
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={draft.exa.num_results}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        exa: {
                          ...draft.exa,
                          num_results: Number(e.target.value) || 0,
                        },
                      })
                    }
                    className="w-full rounded-md border border-border bg-white px-3 py-1.5 text-sm text-ink focus:border-ink focus:outline-none"
                  />
                  <Hint text="Deep search ignores this and chooses dynamically." />
                </Field>
              </EngineCard>
            </div>
          )}
          </div>
        </section>
      </PageBody>
    </>
  );
}

function StatusRow({
  label,
  icon: Icon,
  ok,
  latency,
  loading,
}: {
  label: string;
  icon: typeof Database;
  ok?: boolean;
  latency?: number;
  loading: boolean;
}) {
  const healthy = !loading && ok;
  return (
    <div className="group flex items-center justify-between rounded-lg border border-border bg-gradient-to-b from-white to-tint/20 px-4 py-3.5 transition hover:border-ink/15 hover:shadow-soft">
      <div className="flex items-center gap-3 min-w-0">
        <div
          className={cn(
            "grid h-9 w-9 shrink-0 place-items-center rounded-md ring-1",
            healthy
              ? "bg-emerald-50 ring-emerald-100"
              : loading
                ? "bg-tint/60 ring-border"
                : "bg-red-50 ring-red-100",
          )}
        >
          <Icon
            className={cn(
              "h-4 w-4",
              healthy ? "text-emerald-600" : loading ? "text-soft" : "text-red-600",
            )}
          />
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-ink">{label}</div>
          <div className="font-mono text-[11px] tabular-nums text-muted">
            {loading
              ? "checking…"
              : latency !== undefined
                ? `${latency.toFixed(0)} ms`
                : "—"}
          </div>
        </div>
      </div>
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin text-soft" />
      ) : ok ? (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-700">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
          </span>
          Live
        </span>
      ) : (
        <CircleX className="h-5 w-5 text-red-600" />
      )}
    </div>
  );
}

function EngineCard({
  title,
  subtitle,
  icon: Icon,
  accent,
  children,
}: {
  title: string;
  subtitle: string;
  icon: typeof Cpu;
  accent: "accent" | "navy";
  children: React.ReactNode;
}) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-white p-5 shadow-soft">
      <span
        aria-hidden
        className={cn(
          "absolute inset-x-0 top-0 h-0.5",
          accent === "accent" ? "bg-accent" : "bg-navy",
        )}
      />
      <div className="flex items-start gap-2.5">
        <div
          className={cn(
            "grid h-7 w-7 shrink-0 place-items-center rounded-md ring-1",
            accent === "accent"
              ? "bg-accent/10 ring-accent/20"
              : "bg-navy/5 ring-navy/15",
          )}
        >
          <Icon
            className={cn(
              "h-3.5 w-3.5",
              accent === "accent" ? "text-accent" : "text-navy",
            )}
          />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-ink">{title}</div>
          <div className="mt-0.5 text-[11px] leading-relaxed text-muted">{subtitle}</div>
        </div>
      </div>
      <div className="mt-5 space-y-4">{children}</div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-[11px] font-semibold uppercase tracking-wider text-muted">
        {label}
      </span>
      <div className="mt-1 space-y-1">{children}</div>
    </label>
  );
}

function Select({
  value,
  options,
  onChange,
  disabled,
}: {
  value: string;
  options: string[];
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(() =>
    Math.max(0, options.indexOf(value)),
  );
  const wrapperRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!wrapperRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onEsc);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  // When opening, snap active to current value & scroll into view
  useEffect(() => {
    if (open) {
      const i = options.indexOf(value);
      setActiveIdx(i >= 0 ? i : 0);
      requestAnimationFrame(() => {
        const el = listRef.current?.querySelector<HTMLElement>(
          `[data-idx="${i >= 0 ? i : 0}"]`,
        );
        el?.scrollIntoView({ block: "nearest" });
      });
    }
  }, [open, value, options]);

  const commit = (v: string) => {
    onChange(v);
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;
    if (!open && (e.key === "Enter" || e.key === " " || e.key === "ArrowDown")) {
      e.preventDefault();
      setOpen(true);
      return;
    }
    if (!open) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(options.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      commit(options[activeIdx]);
    } else if (e.key === "Home") {
      e.preventDefault();
      setActiveIdx(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setActiveIdx(options.length - 1);
    }
  };

  return (
    <div ref={wrapperRef} className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setOpen((o) => !o)}
        onKeyDown={onKeyDown}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={cn(
          "group flex w-full items-center justify-between gap-2 rounded-lg border bg-white px-3 py-2 text-left text-sm transition",
          "shadow-sm hover:border-ink/20",
          open ? "border-ink/40 ring-2 ring-ink/5" : "border-border",
          disabled
            ? "cursor-not-allowed bg-tint/40 text-soft hover:border-border"
            : "text-ink",
        )}
      >
        <span className="truncate font-medium">{value}</span>
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 shrink-0 text-soft transition-transform duration-200",
            open && "rotate-180 text-ink",
            disabled && "text-soft/60",
          )}
        />
      </button>

      <AnimatePresence>
        {open && !disabled && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.12, ease: "easeOut" }}
            className="absolute left-0 right-0 z-20 mt-1.5 origin-top overflow-hidden rounded-lg border border-border bg-white shadow-lg ring-1 ring-black/[0.03]"
          >
            <ul
              ref={listRef}
              role="listbox"
              className="scrollbar-thin max-h-60 overflow-y-auto py-1"
            >
              {options.map((o, i) => {
                const selected = o === value;
                const active = i === activeIdx;
                return (
                  <li
                    key={o}
                    role="option"
                    aria-selected={selected}
                    data-idx={i}
                    onMouseEnter={() => setActiveIdx(i)}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      commit(o);
                    }}
                    className={cn(
                      "mx-1 flex cursor-pointer items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-sm transition-colors",
                      active && "bg-tint/70",
                      selected ? "text-ink" : "text-muted",
                    )}
                  >
                    <span className={cn("truncate", selected && "font-semibold text-ink")}>
                      {o}
                    </span>
                    {selected && (
                      <Check className="h-3.5 w-3.5 shrink-0 text-accent" />
                    )}
                  </li>
                );
              })}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Hint({ text }: { text?: string }) {
  if (!text) return null;
  return <p className="text-[11px] leading-relaxed text-muted">{text}</p>;
}
