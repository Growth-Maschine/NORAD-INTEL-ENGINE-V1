import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-colors transition-shadow disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none",
  {
    variants: {
      variant: {
        primary:
          "bg-accent text-white hover:bg-accent/90 shadow-soft disabled:bg-soft disabled:shadow-none",
        secondary:
          "bg-white text-ink border border-border hover:bg-tint hover:border-soft",
        ghost: "text-ink hover:bg-tint",
        subtle: "bg-tint/50 text-ink hover:bg-tint",
        danger:
          "bg-red-600 text-white hover:bg-red-700 shadow-soft disabled:bg-soft",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-9 px-4",
        lg: "h-11 px-5 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
