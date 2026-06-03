import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Layers3, Plus, Search, Sparkles } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Topbar } from "@/components/layout/Topbar";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { PageBody } from "@/components/ui/PageBody";
import {
  createWebDiscoveryCluster,
  listWebDiscoveryClusters,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type ClusterFormState = {
  name: string;
  description: string;
  is_active: boolean;
  include_keywords: string[];
  exclude_keywords: string[];
  geography_focus: string[];
  source_preferences: string[];
  signal_priorities: string[];
};

const REGION_OPTIONS = [
  "United States",
  "Canada",
  "United Kingdom",
  "Europe",
  "Middle East",
  "Asia Pacific",
];

const SOURCE_OPTIONS = [
  "News",
  "Company Websites",
  "Scientific Papers",
  "Industry Blogs",
  "Social",
];

const SIGNAL_OPTIONS = [
  "New product launches",
  "Funding announcements",
  "Acquisitions / partnerships",
  "Regulatory updates",
  "Scientific studies",
  "Patent activity",
  "Retail expansion",
  "Consumer traction",
];

const DEFAULT_FORM: ClusterFormState = {
  name: "",
  description: "",
  is_active: true,
  include_keywords: [],
  exclude_keywords: [],
  geography_focus: [],
  source_preferences: [],
  signal_priorities: [],
};

export default function WebDiscovery() {
  const [openCreate, setOpenCreate] = useState(false);
  const [form, setForm] = useState<ClusterFormState>(DEFAULT_FORM);
  const [includeDraft, setIncludeDraft] = useState("");
  const [excludeDraft, setExcludeDraft] = useState("");
  const qc = useQueryClient();
  const navigate = useNavigate();

  const clustersQuery = useQuery({
    queryKey: ["web-discovery-clusters"],
    queryFn: listWebDiscoveryClusters,
  });
  const clusters = clustersQuery.data?.clusters ?? [];

  const createMut = useMutation({
    mutationFn: createWebDiscoveryCluster,
    onSuccess: (cluster) => {
      qc.invalidateQueries({ queryKey: ["web-discovery-clusters"] });
      setForm(DEFAULT_FORM);
      setIncludeDraft("");
      setExcludeDraft("");
      setOpenCreate(false);
      toast.success("Web cluster created");
      navigate(`/discover-web/clusters/${cluster.id}`);
    },
    onError: (err) => {
      toast.error("Failed to create web cluster", {
        description: (err as Error).message,
      });
    },
  });

  const activeClusters = useMemo(
    () => clusters.filter((cluster) => cluster.is_active).length,
    [clusters],
  );

  const saveCluster = (e: FormEvent) => {
    e.preventDefault();
    const includeKeywords = mergeTokens(form.include_keywords, includeDraft);
    const excludeKeywords = mergeTokens(form.exclude_keywords, excludeDraft);

    if (!form.name.trim()) {
      toast.error("Cluster name is required");
      return;
    }
    createMut.mutate({
      name: form.name.trim(),
      description: form.description.trim() || null,
      is_active: form.is_active,
      include_keywords: includeKeywords,
      exclude_keywords: excludeKeywords,
      geography_focus: form.geography_focus,
      source_preferences: form.source_preferences,
      signal_priorities: form.signal_priorities,
    });
  };

  return (
    <>
      <Topbar
        title="Web Discovery"
        subtitle="Build advanced Exa search clusters with intelligence rules, source preferences, and signal priorities."
      />
      <PageBody>
        <section className="rounded-2xl border border-border bg-gradient-to-b from-white to-[#FCFCFB] p-5 shadow-soft sm:p-6">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#5E8E4A]">
                Intelligence
              </p>
              <h2 className="mt-1 text-2xl font-semibold text-ink">Search Clusters</h2>
              <p className="mt-1 text-sm text-muted">
                Create and manage intelligence categories that organize searches,
                filtering rules, and signal detection.
              </p>
            </div>
            <Button
              className="rounded-lg bg-[#17140F] shadow-soft transition-all duration-200 hover:-translate-y-0.5 hover:bg-black hover:shadow-lift"
              onClick={() => setOpenCreate(true)}
            >
              <Plus className="h-4 w-4" />
              Create Cluster
            </Button>
          </div>

          <div className="mb-5 grid gap-3 sm:grid-cols-3">
            <MetricTile label="Total clusters" value={String(clusters.length)} />
            <MetricTile label="Active" value={String(activeClusters)} />
            <MetricTile
              label="Signals queued"
              value={String(clusters.reduce((acc, c) => acc + c.signal_count, 0))}
            />
          </div>

          {clustersQuery.isLoading ? (
            <div className="text-sm text-soft">Loading web clusters...</div>
          ) : clusters.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-[#FCFCFB] px-4 py-10 text-center text-sm text-soft">
              No web clusters yet. Create your first cluster to start query orchestration.
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {clusters.map((cluster) => (
                <article
                  key={cluster.id}
                  className="rounded-2xl border border-border bg-[#FCFCFB] p-4 shadow-soft transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lift"
                >
                  <h3 className="text-[18px] font-semibold text-ink">{cluster.name}</h3>
                  <p className="mt-1 min-h-[40px] text-sm text-muted">
                    {cluster.description ?? "No description yet."}
                  </p>
                  <div className="mt-3 flex items-center gap-2">
                    <Tag kind={cluster.is_active ? "active" : "idle"}>
                      {cluster.is_active ? "Active" : "Paused"}
                    </Tag>
                  </div>
                  <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-3 text-xs">
                    <StatItem label="Queries" value={String(cluster.query_count)} />
                    <StatItem label="Signals" value={String(cluster.signal_count)} />
                    <StatItem
                      label="Last Run"
                      value={cluster.last_run_at ? new Date(cluster.last_run_at).toLocaleDateString() : "Never"}
                    />
                  </div>
                  <Button
                    variant="secondary"
                    className="mt-4 h-9 w-full rounded-md border-[#221F19] bg-[#221F19] text-white transition-all duration-200 hover:-translate-y-0.5 hover:bg-black hover:text-white"
                    onClick={() => navigate(`/discover-web/clusters/${cluster.id}`)}
                  >
                    Open Cluster
                  </Button>
                </article>
              ))}
            </div>
          )}
        </section>
      </PageBody>

      <Dialog open={openCreate} onOpenChange={setOpenCreate}>
        <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto rounded-2xl border-[#E9E7E2] bg-gradient-to-b from-white to-[#FCFCFB] p-0 shadow-[0_30px_90px_-28px_rgba(16,24,40,0.35)]">
          <form onSubmit={saveCluster} className="p-6">
            <DialogHeader>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-soft">
                Intelligence
              </p>
              <DialogTitle className="mt-2 text-2xl">Create Cluster</DialogTitle>
              <DialogDescription>
                Define a monitoring category with rules that organize searches, filtering,
                and signal detection.
              </DialogDescription>
            </DialogHeader>

            <section className="mt-5 rounded-xl border border-border bg-white/80">
              <SectionHead
                icon={Layers3}
                title="Basic Information"
                subtitle="Name, description, and active status"
              />
              <div className="grid gap-4 p-4 md:grid-cols-2">
                <div className="md:col-span-2">
                  <FieldLabel>Cluster Name *</FieldLabel>
                  <TextInput
                    value={form.name}
                    placeholder="Nootropic & Cognitive Products"
                    onChange={(value) => setForm((prev) => ({ ...prev, name: value }))}
                  />
                </div>
                <div className="md:col-span-2">
                  <FieldLabel>Description</FieldLabel>
                  <textarea
                    rows={3}
                    value={form.description}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, description: e.target.value }))
                    }
                    placeholder="What this cluster monitors and why it matters."
                    className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm text-ink outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
                  />
                </div>
                <div className="md:col-span-2 rounded-lg border border-[#D7EAD0] bg-[#F4FAF2] p-3">
                  <FieldLabel>Status</FieldLabel>
                  <label className="mt-2 flex items-center justify-between text-sm">
                    <span className="font-medium text-[#1E3A17]">Active</span>
                    <input
                      type="checkbox"
                      checked={form.is_active}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, is_active: e.target.checked }))
                      }
                      className="h-4 w-4 accent-[#0E9F6E]"
                    />
                  </label>
                  <p className="mt-1 text-xs text-[#587A4D]">
                    Cluster runs on schedule and surfaces new signals.
                  </p>
                </div>
              </div>
            </section>

            <section className="mt-4 rounded-xl border border-border bg-white/80">
              <SectionHead
                icon={FlaskConical}
                title="Cluster Rules"
                subtitle="Keywords, geography, and source filters"
              />
              <div className="grid gap-4 p-4 md:grid-cols-2">
                <div>
                  <FieldLabel>Include Keywords</FieldLabel>
                  <KeywordInput
                    placeholder="Type keyword, press Space"
                    values={form.include_keywords}
                    draft={includeDraft}
                    setDraft={setIncludeDraft}
                    onChange={(values) =>
                      setForm((prev) => ({ ...prev, include_keywords: values }))
                    }
                  />
                </div>
                <div>
                  <FieldLabel>Exclusion Keywords</FieldLabel>
                  <KeywordInput
                    placeholder="Type exclusion, press Space"
                    values={form.exclude_keywords}
                    draft={excludeDraft}
                    setDraft={setExcludeDraft}
                    onChange={(values) =>
                      setForm((prev) => ({ ...prev, exclude_keywords: values }))
                    }
                  />
                </div>
                <div>
                  <FieldLabel>Geography Focus</FieldLabel>
                  <MultiSelectChips
                    options={REGION_OPTIONS}
                    selected={form.geography_focus}
                    onToggle={(value) =>
                      setForm((prev) => ({
                        ...prev,
                        geography_focus: toggleInArray(prev.geography_focus, value),
                      }))
                    }
                  />
                </div>
                <div>
                  <FieldLabel>Source Preferences</FieldLabel>
                  <MultiSelectChips
                    options={SOURCE_OPTIONS}
                    selected={form.source_preferences}
                    onToggle={(value) =>
                      setForm((prev) => ({
                        ...prev,
                        source_preferences: toggleInArray(prev.source_preferences, value),
                      }))
                    }
                  />
                </div>
              </div>
            </section>

            <section className="mt-4 rounded-xl border border-border bg-white/80">
              <SectionHead
                icon={Sparkles}
                title="Signal Detection"
                subtitle="What types of intelligence to prioritize"
              />
              <div className="grid gap-2 p-4 sm:grid-cols-2">
                {SIGNAL_OPTIONS.map((signal) => {
                  const checked = form.signal_priorities.includes(signal);
                  return (
                    <label
                      key={signal}
                      className={cn(
                        "flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition",
                        checked
                          ? "border-[#BDE6D3] bg-[#ECF8F1] text-[#155A3E]"
                          : "border-border bg-white text-ink hover:border-soft",
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() =>
                          setForm((prev) => ({
                            ...prev,
                            signal_priorities: toggleInArray(prev.signal_priorities, signal),
                          }))
                        }
                        className="h-4 w-4 accent-[#0E9F6E]"
                      />
                      {signal}
                    </label>
                  );
                })}
              </div>
            </section>

            <DialogFooter className="mt-5">
              <Button type="button" variant="secondary" onClick={() => setOpenCreate(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                className="bg-[#17140F] transition-all duration-200 hover:-translate-y-0.5 hover:bg-black"
                disabled={createMut.isPending}
              >
                <Search className="h-4 w-4" />
                {createMut.isPending ? "Creating..." : "Create Cluster"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

function SectionHead({
  icon: Icon,
  title,
  subtitle,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="flex items-center gap-2 border-b border-border px-4 py-3">
      <div className="grid h-8 w-8 place-items-center rounded-full bg-tint text-soft">
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <p className="text-sm font-semibold text-ink">{title}</p>
        <p className="text-xs text-soft">{subtitle}</p>
      </div>
    </div>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-[#FCFCFB] px-3 py-2">
      <p className="text-[11px] uppercase tracking-[0.14em] text-soft">{label}</p>
      <p className="mt-1 text-lg font-semibold text-ink">{value}</p>
    </div>
  );
}

function Tag({
  children,
  kind,
}: {
  children: React.ReactNode;
  kind: "active" | "idle";
}) {
  const style =
    kind === "active"
      ? "border-[#CFE8C6] bg-[#ECF8E8] text-[#2F7A33]"
      : "border-[#E8E8E8] bg-[#F7F7F7] text-[#6A6A6A]";
  return <span className={cn("rounded-full border px-2 py-0.5 text-xs", style)}>{children}</span>;
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-[0.12em] text-soft">{label}</p>
      <p className="mt-0.5 font-medium text-ink">{value}</p>
    </div>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <p className="mb-1 text-[12px] font-semibold text-muted">{children}</p>;
}

function TextInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="h-10 w-full rounded-lg border border-border bg-white px-3 text-sm text-ink outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
    />
  );
}

function KeywordInput({
  values,
  draft,
  setDraft,
  onChange,
  placeholder,
}: {
  values: string[];
  draft: string;
  setDraft: (v: string) => void;
  onChange: (values: string[]) => void;
  placeholder: string;
}) {
  const commitDraft = () => {
    const tokens = tokenizeDraft(draft);
    if (!tokens.length) return;
    const existing = new Set(values.map((item) => item.toLowerCase()));
    const nextValues = [...values];
    tokens.forEach((token) => {
      if (existing.has(token.toLowerCase())) return;
      existing.add(token.toLowerCase());
      nextValues.push(token);
    });
    onChange(nextValues);
    setDraft("");
  };

  return (
    <div className="rounded-lg border border-border bg-white p-2">
      <div className="mb-2 flex flex-wrap gap-1.5">
        {values.map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => onChange(values.filter((v) => v !== value))}
            className="rounded-full border border-border bg-tint px-2 py-0.5 text-xs text-ink transition hover:scale-[1.02] hover:bg-soft/30"
            title="Remove keyword"
          >
            {value} ×
          </button>
        ))}
      </div>
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commitDraft}
        onKeyDown={(e) => {
          if (!["Enter", "Tab", ",", " "].includes(e.key)) return;
          e.preventDefault();
          commitDraft();
        }}
        placeholder={placeholder}
        className="h-9 w-full rounded-md border border-border px-2.5 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
      />
      <p className="mt-1 text-[11px] text-soft">
        Add with Space, Enter, Tab, or comma. {values.length} selected.
      </p>
    </div>
  );
}

function MultiSelectChips({
  options,
  selected,
  onToggle,
}: {
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2 rounded-lg border border-border bg-white p-2">
      {options.map((option) => {
        const active = selected.includes(option);
        return (
          <button
            key={option}
            type="button"
            onClick={() => onToggle(option)}
            className={cn(
              "rounded-full border px-2.5 py-1 text-xs transition-all duration-200 hover:-translate-y-0.5",
              active
                ? "border-[#BDE6D3] bg-[#ECF8F1] text-[#155A3E] shadow-soft"
                : "border-border bg-[#FAFAFA] text-muted hover:border-soft",
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
