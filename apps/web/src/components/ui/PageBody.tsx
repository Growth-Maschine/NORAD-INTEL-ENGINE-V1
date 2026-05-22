import { cn } from "@/lib/utils";

/**
 * Standard scrollable page body. Pair with <Topbar> at the top of a page.
 */
export function PageBody({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <main className={cn("min-h-0 flex-1 overflow-y-auto", className)}>
      <div className="mx-auto max-w-7xl px-6 py-8">{children}</div>
    </main>
  );
}
