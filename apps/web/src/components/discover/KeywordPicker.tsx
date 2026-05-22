import * as Popover from "@radix-ui/react-popover";
import { Lightbulb, Plus, Search, X } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";
import { WATCHLIST, type WatchlistGroup } from "@/lib/watchlist";

/**
 * Keyword input with a built-in suggestion drawer. Click the chip icon
 * inside the input to open a curated panel of suggestions — categories,
 * product themes, and watchlist brands the team is actively tracking.
 *
 * The picker is intentionally a single-value control: clicking a chip
 * replaces the current keyword. The backend takes one string anyway, and
 * a multi-chip "tag" picker would just queue work the funnel can't yet
 * action.
 */

const SUGGESTIONS = WATCHLIST;

export function KeywordPicker({
  value,
  onChange,
  onSubmit,
  disabled = false,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit?: () => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative flex h-9 items-center">
      <div className="pointer-events-none absolute left-3 grid h-9 place-items-center text-soft">
        <Search className="h-3.5 w-3.5" />
      </div>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && onSubmit && !disabled) onSubmit();
        }}
        placeholder="Focus the search with a topic, brand, or theme"
        className={cn(
          "h-9 w-full rounded-md border border-border bg-white pl-9 pr-20 text-sm",
          "placeholder:text-soft focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/15",
          "transition-colors",
        )}
        disabled={disabled}
      />
      <div className="absolute right-1.5 flex h-9 items-center gap-1">
        {value && !disabled && (
          <button
            type="button"
            onClick={() => onChange("")}
            aria-label="Clear keyword"
            className="grid h-6 w-6 place-items-center rounded text-soft transition hover:bg-tint hover:text-ink"
          >
            <X className="h-3 w-3" />
          </button>
        )}
        <Popover.Root open={open} onOpenChange={setOpen}>
          <Popover.Trigger asChild>
            <button
              type="button"
              aria-label="Browse keyword suggestions"
              className={cn(
                "inline-flex h-6 items-center gap-1 rounded-md px-2 text-[11px] font-medium transition-colors",
                "text-muted hover:bg-tint hover:text-ink",
                open && "bg-tint text-ink",
              )}
            >
              <Lightbulb className="h-3 w-3" />
              Suggestions
            </button>
          </Popover.Trigger>
          <Popover.Portal>
            <Popover.Content
              align="end"
              side="bottom"
              sideOffset={8}
              className={cn(
                "z-50 w-[420px] rounded-xl border border-border bg-white p-4 shadow-lift",
                "animate-fade-in",
              )}
            >
              <div className="mb-3 flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-ink">Keyword library</p>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-muted">
                    Pick a focus from the team's tracking list, or keep
                    typing your own.
                  </p>
                </div>
                <Popover.Close asChild>
                  <button
                    type="button"
                    aria-label="Close suggestions"
                    className="grid h-6 w-6 place-items-center rounded text-soft transition hover:bg-tint hover:text-ink"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </Popover.Close>
              </div>
              <div className="scrollbar-thin max-h-[60vh] space-y-4 overflow-y-auto pr-1">
                {SUGGESTIONS.map((g) => (
                  <Group
                    key={g.label}
                    group={g}
                    activeValue={value}
                    onPick={(v) => {
                      onChange(v);
                      setOpen(false);
                    }}
                  />
                ))}
              </div>
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      </div>
    </div>
  );
}

function Group({
  group,
  activeValue,
  onPick,
}: {
  group: WatchlistGroup;
  activeValue: string;
  onPick: (v: string) => void;
}) {
  return (
    <section>
      <div className="mb-1.5 flex items-baseline justify-between">
        <h4 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-soft">
          {group.label}
        </h4>
        {group.hint && (
          <span className="text-[10px] text-soft/70">{group.hint}</span>
        )}
      </div>
      <ul className="flex flex-wrap gap-1.5">
        {group.items.map((item) => {
          const active = activeValue.trim().toLowerCase() === item.toLowerCase();
          return (
            <li key={item}>
              <button
                type="button"
                onClick={() => onPick(item)}
                className={cn(
                  "group inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition-all",
                  active
                    ? "border-accent bg-accent text-white shadow-soft"
                    : "border-border bg-white text-ink hover:border-accent/40 hover:bg-accent/5 hover:text-accent",
                )}
                aria-pressed={active}
              >
                <Plus
                  className={cn(
                    "h-3 w-3 transition-transform",
                    active
                      ? "rotate-45 text-white/80"
                      : "text-soft group-hover:text-accent",
                  )}
                />
                {item}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
