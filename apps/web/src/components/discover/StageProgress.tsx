import { motion } from "framer-motion";
import {
  BarChart3,
  Check,
  FileText,
  Filter,
  Loader2,
  PackageOpen,
  Search,
} from "lucide-react";

import { HoverTip } from "@/components/ui/Tooltip";
import { cn } from "@/lib/utils";

/**
 * 5-stage funnel progress strip. Backend (`services/discovery.py`) bumps
 * `runs.progress_pct` at these *completion* milestones:
 *
 *   Start → 5
 *   Stage 1 (Exa search)   completes → 20
 *   Stage 2 (Dedup)        completes → 30
 *   Stage 3 (Haiku rank)   completes → 50
 *   Stage 4 (Exa /contents) completes → 75
 *   Stage 5 (Sonnet extract) completes → 100
 *
 * A stage is *active* when progress is below its completion threshold and
 * at-or-above the previous one. A stage is *reached* when progress ≥ its
 * completion threshold (or status is "completed").
 */
type Stage = { num: number; label: string; icon: typeof Search; done: number };

const STAGES: readonly Stage[] = [
  { num: 1, label: "Search", icon: Search, done: 20 },
  { num: 2, label: "Dedup", icon: Filter, done: 30 },
  { num: 3, label: "Rank", icon: BarChart3, done: 50 },
  { num: 4, label: "Read", icon: FileText, done: 75 },
  { num: 5, label: "Extract", icon: PackageOpen, done: 100 },
] as const;

const STAGE_START = 5; // backend sets progress=5 on run start (before Stage 1)

export function StageProgress({
  progressPct,
  status,
}: {
  progressPct: number;
  status: string;
}) {
  const isComplete = status === "completed";
  const isFailed = status === "failed";

  return (
    <div className="flex items-center justify-between gap-1">
      {STAGES.map((stage, i) => {
        const prevDone = i === 0 ? STAGE_START : STAGES[i - 1].done;
        const reached = isComplete || progressPct >= stage.done;
        const active =
          !isComplete &&
          !isFailed &&
          progressPct < stage.done &&
          progressPct >= prevDone;
        const Icon = stage.icon;

        // Width of the connector to the *next* stage, in [0, 100].
        const connectorPct = reached
          ? 100
          : active
            ? Math.max(
                0,
                Math.min(
                  100,
                  ((progressPct - prevDone) / (stage.done - prevDone)) * 100,
                ),
              )
            : 0;

        return (
          <div key={stage.num} className="flex flex-1 items-center gap-1">
            <HoverTip label={`Stage ${stage.num} — ${stage.label}`}>
              <button
                type="button"
                tabIndex={0}
                aria-label={`Stage ${stage.num}: ${stage.label}${
                  reached ? " (done)" : active ? " (in progress)" : ""
                }`}
                className={cn(
                  "grid h-7 w-7 shrink-0 place-items-center rounded-full border-2 transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40",
                  reached && !isFailed
                    ? "border-accent bg-accent text-white"
                    : active
                      ? "border-accent bg-white text-accent animate-pulse-ring"
                      : isFailed
                        ? "border-red-300 bg-red-50 text-red-500"
                        : "border-border bg-white text-soft",
                )}
              >
                {reached && !isFailed ? (
                  <Check className="h-3.5 w-3.5" />
                ) : active ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Icon className="h-3.5 w-3.5" />
                )}
              </button>
            </HoverTip>
            {i < STAGES.length - 1 && (
              <div className="relative h-0.5 flex-1 overflow-hidden rounded-full bg-border">
                <motion.div
                  initial={false}
                  animate={{ width: `${connectorPct}%` }}
                  transition={{ duration: 0.4, ease: "easeOut" }}
                  className={cn(
                    "absolute inset-y-0 left-0 rounded-full",
                    isFailed ? "bg-red-400" : "bg-accent",
                  )}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
