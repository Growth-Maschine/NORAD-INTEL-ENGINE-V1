import { useQuery } from "@tanstack/react-query";
import { Menu } from "lucide-react";

import { HoverTip } from "@/components/ui/Tooltip";
import { getHealthDb } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useMobileMenu } from "./mobile-menu-context";

export function Topbar({ title, subtitle }: { title: string; subtitle?: string }) {
  const { toggle } = useMobileMenu();
  const dbHealth = useQuery({
    queryKey: ["health-db"],
    queryFn: getHealthDb,
    refetchInterval: 30_000,
  });

  const { dot, label, tip } = (() => {
    if (dbHealth.isLoading)
      return { dot: "bg-soft", label: "Checking", tip: "Checking system status…" };
    if (dbHealth.isError)
      return {
        dot: "bg-red-500",
        label: "Offline",
        tip: "Failed to reach the API. Backend may be down.",
      };
    if (dbHealth.data?.status === "ok")
      return {
        dot: "bg-emerald-500",
        label: "All systems",
        tip: "Database + API are responding normally.",
      };
    return {
      dot: "bg-amber-500",
      label: "Degraded",
      tip: "Some subsystems are reporting issues.",
    };
  })();

  return (
    <header className="flex h-16 shrink-0 items-center justify-between gap-3 border-b border-border bg-white px-4 sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={toggle}
          aria-label="Open menu"
          className="grid h-9 w-9 place-items-center rounded-md text-ink transition hover:bg-tint md:hidden"
        >
          <Menu className="h-4 w-4" />
        </button>

        <div className="min-w-0">
          <h1 className="truncate text-[17px] font-semibold leading-tight tracking-tight text-ink">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-0.5 truncate text-[12px] font-medium leading-tight text-soft">
              {subtitle}
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <HoverTip label={tip}>
          <button
            type="button"
            tabIndex={0}
            aria-label={`System status: ${label}. ${tip}`}
            className="flex cursor-help items-center gap-2 rounded-md border border-border bg-tint/40 px-3 py-1.5 transition hover:bg-tint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
          >
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                dot,
                label === "All systems" && "shadow-[0_0_0_3px_rgba(16,185,129,0.15)]",
              )}
            />
            <span className="hidden text-xs text-muted sm:inline">{label}</span>
          </button>
        </HoverTip>
      </div>
    </header>
  );
}
