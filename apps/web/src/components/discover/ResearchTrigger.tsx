import { motion } from "framer-motion";
import { Loader2, ScanSearch } from "lucide-react";

import { HoverTip } from "@/components/ui/Tooltip";
import { cn } from "@/lib/utils";

/**
 * "Profile" trigger — the per-card CTA that kicks off a research run on the
 * subject company. Visual treatment: a compact horizontal pill that sits
 * vertically centered beside each article card. Premium dark surface, a
 * thin amber accent that intensifies on hover, lucide `ScanSearch` glyph,
 * single-word "Profile" label.
 *
 * States: idle / hover (lift + amber sharpens) / busy (spinner + "Working")
 * / disabled (muted, no accent).
 */
export function ResearchTrigger({
  companyName,
  onClick,
  busy = false,
  disabled = false,
}: {
  companyName: string | null;
  onClick: () => void;
  busy?: boolean;
  disabled?: boolean;
}) {
  const isDisabled = disabled || busy || !companyName;
  const tooltip = !companyName
    ? "Waiting for company extraction"
    : busy
      ? `Profiling ${companyName}…`
      : `Profile ${companyName}`;

  return (
    <HoverTip label={tooltip} side="left">
      <motion.button
        type="button"
        onClick={onClick}
        disabled={isDisabled}
        aria-label={tooltip}
        whileHover={isDisabled ? undefined : { y: -1 }}
        whileTap={isDisabled ? undefined : { scale: 0.96 }}
        transition={{ type: "spring", stiffness: 380, damping: 26 }}
        className={cn(
          "group relative grid h-11 w-11 shrink-0 place-items-center",
          "rounded-full border outline-none transition-colors",
          "focus-visible:ring-2 focus-visible:ring-amber-400/40",
          isDisabled
            ? "cursor-not-allowed border-border bg-tint/60 text-soft"
            : cn(
                "cursor-pointer text-white",
                "border-slate-700/80 bg-gradient-to-b from-slate-900 to-slate-800",
                "shadow-[0_1px_0_rgba(255,255,255,0.05)_inset,0_6px_16px_-10px_rgba(15,23,42,0.6)]",
                "hover:border-amber-400/55 hover:shadow-[0_1px_0_rgba(255,255,255,0.06)_inset,0_12px_24px_-10px_rgba(180,83,9,0.45)]",
              ),
        )}
      >
        {/* Glyph — single, centered, premium minimal. The label lives in
            the tooltip so the action stays compact and never crowds the
            article card next to it. */}
        {busy ? (
          <Loader2
            className={cn(
              "h-[18px] w-[18px] animate-spin",
              isDisabled ? "text-soft" : "text-amber-300",
            )}
          />
        ) : (
          <ScanSearch
            className={cn(
              "h-[18px] w-[18px] transition-colors",
              isDisabled
                ? "text-soft"
                : "text-amber-300/90 group-hover:text-amber-300",
            )}
            strokeWidth={2}
          />
        )}
      </motion.button>
    </HoverTip>
  );
}
