/** Placeholder shapes shown while real data loads (shimmer in index.css). */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`ab-skeleton rounded-lg ${className}`} />
}

/** Same footprint as PropertyCard, so the page doesn't jump when data arrives. */
export function PropertyCardSkeleton() {
  return (
    <div aria-hidden="true" className="overflow-hidden rounded-2xl border border-ab-border bg-ab-card">
      <Skeleton className="aspect-[4/3] w-full rounded-none" />
      <div className="space-y-3 p-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-4 w-1/2" />
        <div className="flex gap-2 pt-2">
          <Skeleton className="h-9 flex-1 rounded-xl" />
          <Skeleton className="h-9 w-16 rounded-xl" />
        </div>
      </div>
    </div>
  )
}

export function PropertyGridSkeleton({ count = 6, label = "Loading properties…" }: { count?: number; label?: string }) {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: count }, (_, index) => (
          <PropertyCardSkeleton key={index} />
        ))}
      </div>
    </div>
  )
}

/** Compact list-row placeholder (map listings panel, account transactions). */
export function RowSkeleton({ image = true }: { image?: boolean }) {
  return (
    <div aria-hidden="true" className="flex gap-3 rounded-2xl border border-ab-border bg-ab-card-2 p-3">
      {image && <Skeleton className="h-20 w-20 shrink-0 rounded-xl" />}
      <div className="flex-1 space-y-2.5 py-1">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-3 w-1/2" />
        <Skeleton className="h-5 w-28" />
      </div>
    </div>
  )
}

/** "Loading …" with the brand spinner, for places without a skeleton. */
export function LoadingLabel({ text }: { text: string }) {
  return (
    <p role="status" className="flex items-center justify-center gap-2.5 py-10 text-sm text-ab-muted">
      <span className="ab-spinner h-5 w-5" aria-hidden="true" />
      {text}
    </p>
  )
}
