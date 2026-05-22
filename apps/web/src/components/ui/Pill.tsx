import { cn } from "@/lib/utils";

type Variant = "neutral" | "accent" | "success" | "warning" | "danger" | "navy";

const variants: Record<Variant, string> = {
  neutral: "bg-tint text-muted border-border",
  accent: "bg-accent/10 text-accent border-accent/20",
  success: "bg-emerald-50 text-emerald-700 border-emerald-200",
  warning: "bg-amber-50 text-amber-700 border-amber-200",
  danger: "bg-red-50 text-red-700 border-red-200",
  navy: "bg-navy/5 text-navy border-navy/15",
};

/**
 * Tiny rounded label. Use for ticker/index badges, statuses, signal types.
 */
export function Pill({
  children,
  variant = "neutral",
  className,
}: {
  children: React.ReactNode;
  variant?: Variant;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.06em]",
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
