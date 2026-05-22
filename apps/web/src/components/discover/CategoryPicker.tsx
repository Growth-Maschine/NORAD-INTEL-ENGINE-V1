import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Hash } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { getCategories } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface WatchlistGroup {
  label: string;
  items: string[];
}

/**
 * Dropdown selector over the grouped TrendHunter taxonomy.
 * Uses a native popover (no portal needed) and closes on outside-click.
 *
 * Optionally renders a "Watchlist" section at the top — keyword shortcuts
 * the BD team is actively tracking. Picking one fires `onKeyword` and
 * leaves the actual category selection alone.
 */
export function CategoryPicker({
  value,
  onChange,
  watchlist,
  onKeyword,
  activeKeyword,
  className,
}: {
  value: string;
  onChange: (slug: string) => void;
  watchlist?: WatchlistGroup[];
  onKeyword?: (kw: string) => void;
  activeKeyword?: string;
  className?: string;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["categories"],
    queryFn: getCategories,
    staleTime: Infinity,
  });
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

  const all = Object.values(data?.groups ?? {}).flat();
  const current = all.find((c) => c.slug === value);

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        disabled={isLoading}
        className={cn(
          "flex w-full items-center justify-between gap-3 rounded-md border border-border bg-white px-3 py-2",
          "text-sm font-medium text-ink transition hover:border-soft",
          open && "border-accent ring-2 ring-accent/15",
        )}
      >
        <span className="truncate">
          {current?.label ?? (isLoading ? "Loading…" : "Pick category")}
        </span>
        <ChevronDown className={cn("h-4 w-4 text-soft transition", open && "rotate-180")} />
      </button>

      {open && data && (
        <div
          className={cn(
            "absolute z-30 mt-2 max-h-[28rem] w-80 overflow-auto rounded-xl border border-border bg-white shadow-lift",
          )}
        >
          {Object.entries(data.groups).map(([group, items]) => (
            <div key={group} className="py-2">
              <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-soft">
                {group}
              </div>
              <ul>
                {items.map((c) => (
                  <li key={c.slug}>
                    <button
                      type="button"
                      onClick={() => {
                        onChange(c.slug);
                        setOpen(false);
                      }}
                      className={cn(
                        "flex w-full items-center justify-between px-3 py-1.5 text-left text-sm transition",
                        c.slug === value
                          ? "bg-accent/10 font-medium text-accent"
                          : "text-ink hover:bg-tint",
                      )}
                    >
                      <span>{c.label}</span>
                      {c.slug === value && (
                        <span className="text-[10px] font-semibold text-accent">SELECTED</span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          {watchlist && onKeyword && watchlist.length > 0 && (
            <div className="mt-1 border-t-2 border-dashed border-border bg-gradient-to-b from-accent/5 to-transparent">
              <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border/60 bg-white/90 px-3 py-2 backdrop-blur">
                <div className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-accent shadow-[0_0_0_3px_rgba(232,107,32,0.18)]" />
                  <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-ink">
                    Watchlist
                  </span>
                </div>
                <span className="text-[10px] font-medium text-muted">
                  Click to set keyword
                </span>
              </div>
              {watchlist.map((g) => (
                <div key={g.label} className="px-2 py-1.5">
                  <div className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-wider text-soft">
                    {g.label}
                  </div>
                  <ul className="space-y-0.5">
                    {g.items.map((kw) => {
                      const active =
                        (activeKeyword ?? "").trim().toLowerCase() === kw.toLowerCase();
                      return (
                        <li key={kw}>
                          <button
                            type="button"
                            onClick={() => {
                              onKeyword(kw);
                              setOpen(false);
                            }}
                            className={cn(
                              "group flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] transition-all",
                              active
                                ? "bg-accent text-white shadow-soft"
                                : "text-ink hover:bg-white hover:shadow-soft hover:ring-1 hover:ring-accent/20",
                            )}
                            aria-pressed={active}
                          >
                            <Hash
                              className={cn(
                                "h-3.5 w-3.5 shrink-0 transition",
                                active
                                  ? "text-white/80"
                                  : "text-accent/70 group-hover:text-accent",
                              )}
                            />
                            <span className="truncate font-medium">{kw}</span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
