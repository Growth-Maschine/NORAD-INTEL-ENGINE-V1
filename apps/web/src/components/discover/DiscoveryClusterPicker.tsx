import { Check, ChevronDown, Sparkles } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { type DiscoveryCluster } from "@/lib/api";
import { cn } from "@/lib/utils";

export function DiscoveryClusterPicker({
  groups,
  value,
  onChange,
  disabled = false,
}: {
  groups: Record<string, DiscoveryCluster[]>;
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const all = useMemo(() => Object.values(groups).flat(), [groups]);
  const current = all.find((c) => c.id === value) ?? null;

  return (
    <div ref={rootRef} className="relative space-y-1.5">
      <span className="inline-flex items-center gap-1 text-[10.5px] font-bold uppercase tracking-[0.16em] text-muted">
        <Sparkles className="h-3.5 w-3.5" />
        Discovery cluster
      </span>

      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex h-10 w-full items-center justify-between gap-3 rounded-lg border border-border bg-white px-3.5 text-left",
          "text-sm font-medium text-ink transition",
          "hover:border-soft disabled:cursor-not-allowed disabled:opacity-60",
          open && "border-accent ring-2 ring-accent/15",
        )}
      >
        <span className="truncate">
          {current?.name ?? (all.length ? "Select cluster" : "No clusters available")}
        </span>
        <ChevronDown
          className={cn("h-4 w-4 text-soft transition", open && "rotate-180")}
        />
      </button>

      <p className="text-[11px] text-soft">
        Only the cluster name is shown here. Its keywords are auto-applied behind the scenes.
      </p>

      {open && !!all.length && (
        <div className="absolute z-30 mt-1 max-h-[28rem] w-[min(760px,calc(100vw-3rem))] overflow-auto rounded-xl border border-border bg-white p-3 shadow-lift">
          <div className="mb-2 border-b border-border pb-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-soft">
              Pick a discovery cluster
            </p>
          </div>
          <div className="space-y-3">
            {Object.entries(groups).map(([group, items]) => {
              if (!items.length) return null;
              return (
                <section key={group}>
                  <h4 className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-soft">
                    {group}
                  </h4>
                  <div className="grid gap-1.5 sm:grid-cols-2">
                    {items.map((c) => {
                      const active = c.id === value;
                      return (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => {
                            onChange(c.id);
                            setOpen(false);
                          }}
                          className={cn(
                            "rounded-lg border px-3 py-2 text-left transition",
                            active
                              ? "border-accent bg-accent/8"
                              : "border-border hover:border-soft hover:bg-tint/40",
                          )}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <p className="line-clamp-1 text-sm font-medium text-ink">
                              {c.name}
                            </p>
                            {active && (
                              <span className="mt-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-accent text-white">
                                <Check className="h-3 w-3" />
                              </span>
                            )}
                          </div>
                          <p className="mt-0.5 text-[11px] text-soft">
                            {c.keywords.length} keywords
                          </p>
                        </button>
                      );
                    })}
                  </div>
                </section>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
