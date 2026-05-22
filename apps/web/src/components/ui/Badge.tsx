import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef } from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium leading-none whitespace-nowrap",
  {
    variants: {
      variant: {
        neutral: "bg-tint text-muted",
        navy: "bg-navy/10 text-navy",
        accent: "bg-accent/10 text-accent",
        success: "bg-emerald-50 text-emerald-700 border border-emerald-200/60",
        warning: "bg-amber-50 text-amber-700 border border-amber-200/60",
        danger: "bg-red-50 text-red-700 border border-red-200/60",
        outline: "border border-border text-muted bg-white",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant, ...props }, ref) => (
    <span
      ref={ref}
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  ),
);
Badge.displayName = "Badge";

export { badgeVariants };
