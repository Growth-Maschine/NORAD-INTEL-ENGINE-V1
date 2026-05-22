import { cn } from "@/lib/utils";

/**
 * 20-square gradient bar from cold → warm → hot, with the current score
 * marker overlayed. Used on the Fit Score card.
 */
export function ScoreBar({
  current,
  threshold = 50,
  max = 100,
}: {
  current: number;
  threshold?: number;
  max?: number;
}) {
  const cells = 20;
  const currentIdx = Math.round((current / max) * (cells - 1));

  return (
    <div>
      <div className="flex items-end gap-1">
        {Array.from({ length: cells }).map((_, i) => {
          const isActive = i <= currentIdx;
          const color =
            i < cells * 0.35
              ? "bg-sky-400"
              : i < cells * 0.7
                ? "bg-amber-400"
                : "bg-emerald-500";
          return (
            <div
              key={i}
              className={cn(
                "h-6 flex-1 rounded-sm transition-colors",
                isActive ? color : "bg-border/60",
              )}
            />
          );
        })}
      </div>

      <div className="mt-2 flex justify-between text-[10px] font-medium uppercase tracking-[0.08em] text-soft">
        <span>Cold</span>
        <span>Warm</span>
        <span>Hot</span>
      </div>

      <div className="mt-3 grid grid-cols-3 text-center">
        <div>
          <div className="text-lg font-semibold text-ink">{threshold}</div>
          <div className="text-[10px] uppercase tracking-[0.08em] text-soft">
            Threshold
          </div>
        </div>
        <div>
          <div className="text-lg font-semibold text-accent">{current}</div>
          <div className="text-[10px] uppercase tracking-[0.08em] text-soft">
            Current
          </div>
        </div>
        <div>
          <div className="text-lg font-semibold text-ink">{max}</div>
          <div className="text-[10px] uppercase tracking-[0.08em] text-soft">
            Max
          </div>
        </div>
      </div>
    </div>
  );
}
