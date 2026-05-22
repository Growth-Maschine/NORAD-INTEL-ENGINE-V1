import { cn } from "@/lib/utils";

/**
 * Horizontal progress bar — label left, score right, fill below.
 * Used on the Metric Breakdown card.
 */
export function MetricBar({
  label,
  value,
  max = 100,
  accent = "navy",
}: {
  label: string;
  value: number;
  max?: number;
  accent?: "navy" | "accent" | "emerald" | "amber";
}) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const fill = {
    navy: "bg-navy",
    accent: "bg-accent",
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
  }[accent];

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-xs font-medium text-ink">{label}</span>
        <span className="tabular-nums text-xs font-semibold text-ink">
          {value}
        </span>
      </div>
      <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-tint">
        <div
          className={cn("h-full rounded-full transition-all", fill)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
