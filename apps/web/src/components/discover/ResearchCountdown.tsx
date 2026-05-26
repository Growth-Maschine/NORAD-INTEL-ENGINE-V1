import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const TOTAL_MS = 3000;
const TICK_MS = 50;

/**
 * Bottom-center banner that gives the user a 3-second window to cancel the
 * auto-navigation to the run page after a research run has been kicked off.
 *
 * The research itself is already running in the background — cancelling
 * here only cancels the *navigation*, not the run.
 */
export function ResearchCountdown({
  companyName,
  onNavigate,
  onCancel,
}: {
  companyName: string;
  onNavigate: () => void;
  onCancel: () => void;
}) {
  // Elapsed time in ms.
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = performance.now();
    const id = setInterval(() => {
      const e = performance.now() - start;
      if (e >= TOTAL_MS) {
        clearInterval(id);
        setElapsed(TOTAL_MS);
        onNavigate();
      } else {
        setElapsed(e);
      }
    }, TICK_MS);
    return () => clearInterval(id);
  }, [onNavigate]);

  const pct = Math.min(100, (elapsed / TOTAL_MS) * 100);
  const secondsLeft = Math.max(1, Math.ceil((TOTAL_MS - elapsed) / 1000));

  return (
    <AnimatePresence>
      <motion.div
        key="countdown"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 20 }}
        transition={{ type: "spring", stiffness: 320, damping: 28 }}
        className="fixed bottom-6 left-1/2 z-[60] -translate-x-1/2 pb-[env(safe-area-inset-bottom)]"
        role="status"
        aria-live="polite"
      >
        <div
          className={cn(
            "relative w-[min(92vw,460px)] overflow-hidden rounded-xl",
            "border border-slate-700/70 bg-gradient-to-b from-slate-900 to-slate-800",
            "text-white shadow-[0_24px_60px_-20px_rgba(15,23,42,0.7)]",
            // Breathing room so this never sits flush against Sonner toasts
            // (bottom-right) or the viewport edge when multiple notices fire.
            "mb-1",
          )}
        >
          <div className="flex items-center gap-3 px-4 py-3">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-amber-400/15 ring-1 ring-amber-400/40">
              <Loader2 className="h-4 w-4 animate-spin text-amber-300" />
            </span>

            <div className="min-w-0 flex-1">
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-300/90">
                Research started
              </div>
              <div className="mt-0.5 truncate text-sm">
                Opening{" "}
                <span className="font-semibold text-white">{companyName}</span>{" "}
                in{" "}
                <span className="tabular-nums font-semibold text-white">
                  {secondsLeft}s
                </span>
              </div>
            </div>

            <button
              type="button"
              onClick={onCancel}
              className={cn(
                "inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-[11px] font-medium",
                "text-slate-300 transition hover:bg-white/10 hover:text-white",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/50",
              )}
            >
              <X className="h-3.5 w-3.5" />
              Cancel
            </button>
            <button
              type="button"
              onClick={onNavigate}
              className={cn(
                "inline-flex items-center gap-1 rounded-md bg-amber-400/15 px-2.5 py-1.5 text-[11px] font-semibold text-amber-200",
                "ring-1 ring-amber-400/40 transition hover:bg-amber-400/25 hover:text-white",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60",
              )}
            >
              Go now
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Progress hairline */}
          <div className="h-[2px] bg-white/5">
            <div
              className="h-full bg-gradient-to-r from-amber-400 to-amber-300 transition-[width] duration-[50ms] ease-linear"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
