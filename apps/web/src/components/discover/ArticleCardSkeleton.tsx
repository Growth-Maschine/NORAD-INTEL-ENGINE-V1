import { Skeleton } from "@/components/ui/Skeleton";

/** Ghost card displayed in the grid while a run is researching. Sized to
 *  match the real ArticleCard min-height so the grid doesn't jump when
 *  cards swap in. */
export function ArticleCardSkeleton() {
  return (
    <div className="flex min-h-[360px] flex-col rounded-xl border border-border bg-white p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex gap-2">
          <Skeleton className="h-5 w-14" />
          <Skeleton className="h-5 w-16" />
        </div>
        <Skeleton className="h-6 w-6 rounded-md" />
      </div>
      <Skeleton className="h-5 w-5/6" />
      <Skeleton className="mt-2 h-4 w-full" />
      <Skeleton className="mt-1 h-4 w-11/12" />
      <Skeleton className="mt-1 h-4 w-3/4" />
      <div className="mt-4 rounded-lg border border-border bg-tint/30 p-3">
        <Skeleton className="h-3 w-32" />
        <div className="mt-2 flex items-start gap-3">
          <Skeleton className="h-7 w-7 rounded-md" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-3 w-full" />
          </div>
        </div>
      </div>
      <div className="mt-auto flex items-center justify-between pt-4">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-14" />
      </div>
    </div>
  );
}
