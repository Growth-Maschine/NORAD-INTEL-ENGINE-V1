import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Layers3,
  Pencil,
  Plus,
  Star,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Topbar } from "@/components/layout/Topbar";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog, Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import { PageBody } from "@/components/ui/PageBody";
import {
  createDiscoveryCluster,
  deleteDiscoveryCluster,
  getDiscoveryClusters,
  updateDiscoveryCluster,
  type DiscoveryCluster,
  type DiscoveryClusterInput,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type ClusterFormState = {
  name: string;
  group_name: string;
  description: string;
  keywordsText: string;
  is_enabled: boolean;
  is_default: boolean;
};

const EMPTY_FORM: ClusterFormState = {
  name: "",
  group_name: "Core Product & Industry",
  description: "",
  keywordsText: "",
  is_enabled: true,
  is_default: false,
};

function parseKeywords(raw: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const token of raw.split(/\n|,/g)) {
    const t = token.trim();
    if (!t) continue;
    const key = t.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(t);
  }
  return out;
}

function toInput(s: ClusterFormState): DiscoveryClusterInput {
  return {
    name: s.name.trim(),
    group_name: s.group_name.trim() || "Custom",
    description: s.description.trim() || null,
    keywords: parseKeywords(s.keywordsText),
    is_enabled: s.is_enabled,
    is_default: s.is_default,
  };
}

function fromCluster(c: DiscoveryCluster): ClusterFormState {
  return {
    name: c.name,
    group_name: c.group_name,
    description: c.description ?? "",
    keywordsText: c.keywords.join(", "),
    is_enabled: c.is_enabled,
    is_default: c.is_default,
  };
}

export default function DiscoveryClusters() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<DiscoveryCluster | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DiscoveryCluster | null>(null);
  const [form, setForm] = useState<ClusterFormState>(EMPTY_FORM);

  const clustersQuery = useQuery({
    queryKey: ["discovery-clusters"],
    queryFn: getDiscoveryClusters,
    staleTime: 30_000,
  });

  const groups = clustersQuery.data?.groups ?? {};
  const all = useMemo(
    () => Object.values(groups).flat(),
    [groups],
  );

  const saveMut = useMutation({
    mutationFn: async () => {
      const payload = toInput(form);
      if (payload.keywords.length === 0) {
        throw new Error("Please add at least one keyword.");
      }
      if (!payload.name) {
        throw new Error("Cluster name is required.");
      }
      return editing
        ? updateDiscoveryCluster(editing.id, payload)
        : createDiscoveryCluster(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["discovery-clusters"] });
      toast.success(editing ? "Cluster updated" : "Cluster created");
      setFormOpen(false);
      setEditing(null);
      setForm(EMPTY_FORM);
    },
    onError: (err) => {
      toast.error("Could not save cluster", {
        description: (err as Error).message,
      });
    },
  });

  const delMut = useMutation({
    mutationFn: (id: string) => deleteDiscoveryCluster(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["discovery-clusters"] });
      toast.success("Cluster deleted");
      setDeleteTarget(null);
    },
    onError: (err) => {
      toast.error("Delete failed", { description: (err as Error).message });
    },
  });

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormOpen(true);
  };

  const openEdit = (c: DiscoveryCluster) => {
    setEditing(c);
    setForm(fromCluster(c));
    setFormOpen(true);
  };

  const clusterCount = all.length;

  const setDefaultMut = useMutation({
    mutationFn: (c: DiscoveryCluster) =>
      updateDiscoveryCluster(c.id, {
        name: c.name,
        group_name: c.group_name,
        description: c.description,
        keywords: c.keywords,
        is_enabled: c.is_enabled,
        is_default: true,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["discovery-clusters"] });
      toast.success("Default cluster updated");
    },
    onError: (err) => {
      toast.error("Could not set default", { description: (err as Error).message });
    },
  });

  return (
    <>
      <Topbar
        title="Discovery Clusters"
        subtitle="Build reusable keyword clusters for one-click Discover runs."
      />
      <PageBody>
        <section className="mb-6 rounded-xl border border-border bg-white p-5 shadow-soft">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-ink">Cluster Library</p>
              <p className="mt-1 text-xs text-muted">
                One cluster per discovery run. Keywords stay behind the cluster name.
              </p>
            </div>
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New cluster
            </Button>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <Stat label="Total clusters" value={String(clusterCount)} />
            <Stat
              label="Enabled"
              value={String(all.filter((c) => c.is_enabled).length)}
            />
            <Stat
              label="Default"
              value={all.find((c) => c.is_default)?.name ?? "—"}
            />
          </div>
        </section>

        <section className="space-y-5">
          {clustersQuery.isLoading ? (
            <div className="rounded-xl border border-border bg-white p-8 text-sm text-muted">
              Loading clusters…
            </div>
          ) : Object.keys(groups).length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-white p-8 text-sm text-muted">
              No clusters yet. Create your first cluster.
            </div>
          ) : (
            Object.entries(groups).map(([groupName, items]) => (
              <div
                key={groupName}
                className="rounded-xl border border-border bg-white p-4 shadow-soft"
              >
                <div className="mb-3 flex items-center gap-2">
                  <Layers3 className="h-4 w-4 text-soft" />
                  <h2 className="text-sm font-semibold text-ink">{groupName}</h2>
                </div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {items.map((c) => (
                    <article
                      key={c.id}
                      className={cn(
                        "rounded-xl border p-3 transition",
                        c.is_default
                          ? "border-accent/40 bg-accent/5"
                          : "border-border bg-white hover:border-soft",
                      )}
                    >
                      <div className="mb-2 flex items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-semibold text-ink">{c.name}</p>
                          <p className="mt-0.5 text-[11px] text-muted">
                            {c.keywords.length} keywords
                          </p>
                        </div>
                        <div className="flex items-center gap-1">
                          {c.is_default && (
                            <span className="inline-flex items-center gap-1 rounded-full border border-accent/20 bg-accent/10 px-2 py-0.5 text-[10px] font-semibold text-accent">
                              <Star className="h-3 w-3" />
                              Default
                            </span>
                          )}
                          {!c.is_enabled && (
                            <span className="rounded-full border border-border px-2 py-0.5 text-[10px] font-semibold text-muted">
                              Disabled
                            </span>
                          )}
                        </div>
                      </div>
                      {c.description && (
                        <p className="mb-2 line-clamp-2 text-xs text-muted">
                          {c.description}
                        </p>
                      )}
                      <div className="mb-3 flex flex-wrap gap-1.5">
                        {c.keywords.slice(0, 5).map((kw) => (
                          <span
                            key={kw}
                            className="rounded-full border border-border bg-tint/40 px-2 py-0.5 text-[11px] text-ink"
                          >
                            {kw}
                          </span>
                        ))}
                        {c.keywords.length > 5 && (
                          <span className="rounded-full border border-border px-2 py-0.5 text-[11px] text-soft">
                            +{c.keywords.length - 5} more
                          </span>
                        )}
                      </div>
                      <div className="flex items-center justify-end gap-1.5">
                        {!c.is_default && (
                          <Button
                            variant="subtle"
                            size="sm"
                            onClick={() => setDefaultMut.mutate(c)}
                            disabled={setDefaultMut.isPending}
                          >
                            <Star className="h-3.5 w-3.5" />
                            Make default
                          </Button>
                        )}
                        <Button variant="secondary" size="sm" onClick={() => openEdit(c)} disabled={setDefaultMut.isPending}>
                          <Pencil className="h-3.5 w-3.5" />
                          Edit
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => setDeleteTarget(c)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          Delete
                        </Button>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            ))
          )}
        </section>
      </PageBody>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit cluster" : "Create cluster"}</DialogTitle>
            <DialogDescription>
              Cluster names appear on Today. Keywords remain hidden and are auto-used in discovery.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Cluster name">
              <input
                value={form.name}
                onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))}
                className="h-9 w-full rounded-md border border-border px-3 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/15"
                placeholder="Nicotine Alternatives"
              />
            </Field>
            <Field label="Group">
              <input
                value={form.group_name}
                onChange={(e) => setForm((s) => ({ ...s, group_name: e.target.value }))}
                className="h-9 w-full rounded-md border border-border px-3 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/15"
                placeholder="Core Product & Industry"
              />
            </Field>
          </div>

          <Field label="Description (optional)">
            <input
              value={form.description}
              onChange={(e) => setForm((s) => ({ ...s, description: e.target.value }))}
              className="h-9 w-full rounded-md border border-border px-3 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/15"
              placeholder="Short intent of this cluster"
            />
          </Field>

          <Field label="Keywords (comma or new line)">
            <textarea
              value={form.keywordsText}
              onChange={(e) => setForm((s) => ({ ...s, keywordsText: e.target.value }))}
              className="min-h-[120px] w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/15"
              placeholder="nicotine pouch, smokeless nicotine, modern oral"
            />
          </Field>

          <div className="flex flex-wrap gap-3 rounded-lg border border-border bg-tint/30 px-3 py-2">
            <label className="inline-flex items-center gap-2 text-xs text-ink">
              <input
                type="checkbox"
                checked={form.is_enabled}
                onChange={(e) => setForm((s) => ({ ...s, is_enabled: e.target.checked }))}
              />
              Enabled
            </label>
            <label className="inline-flex items-center gap-2 text-xs text-ink">
              <input
                type="checkbox"
                checked={form.is_default}
                onChange={(e) => setForm((s) => ({ ...s, is_default: e.target.checked }))}
              />
              Set as default cluster
            </label>
          </div>

          <DialogFooter>
            <Button
              variant="secondary"
              onClick={() => {
                setFormOpen(false);
                setEditing(null);
              }}
            >
              Cancel
            </Button>
            <Button onClick={() => saveMut.mutate()} disabled={saveMut.isPending}>
              <CheckCircle2 className="h-4 w-4" />
              {saveMut.isPending ? "Saving..." : editing ? "Save changes" : "Create cluster"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(v) => !v && setDeleteTarget(null)}
        title={deleteTarget ? `Delete "${deleteTarget.name}"?` : "Delete cluster?"}
        description="This removes the cluster from Discover. Existing discovery runs are unaffected."
        confirmText="Delete"
        variant="danger"
        onConfirm={() => {
          if (deleteTarget) delMut.mutate(deleteTarget.id);
        }}
        busy={delMut.isPending}
      />
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="space-y-1.5">
      <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-soft">
        {label}
      </span>
      {children}
    </label>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-tint/30 px-3 py-2">
      <p className="text-[11px] text-soft">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}
