import { Star } from "lucide-react"

/** Read-only star rating (rounded to the nearest half for display). */
export function Stars({ value, size = "h-4 w-4", className = "" }: { value: number; size?: string; className?: string }) {
  const rounded = Math.round(value * 2) / 2
  return (
    <span className={`inline-flex items-center gap-0.5 text-ab-warning ${className}`} role="img" aria-label={`${value.toFixed(1)} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <span key={n} className="relative inline-flex">
          <Star className={`${size} text-ab-border-strong`} aria-hidden="true" />
          {rounded >= n - 0.5 && (
            <span className={`absolute inset-0 overflow-hidden ${rounded >= n ? "w-full" : "w-1/2"}`}>
              <Star className={`${size} fill-current`} aria-hidden="true" />
            </span>
          )}
        </span>
      ))}
    </span>
  )
}

/** Client rating summary: "★★★★☆ 4.3 · 12 reviews", or an honest empty label. */
export function RatingSummary({ rating, count, compact = false }: { rating: number | null; count: number; compact?: boolean }) {
  if (!count || rating == null) return <span className="text-xs text-ab-faint">No client reviews yet</span>
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5 text-sm">
      <Stars value={rating} size={compact ? "h-3.5 w-3.5" : "h-4 w-4"} />
      <strong className="tabular-nums text-ab-text">{rating.toFixed(1)}</strong>
      <span className="text-xs text-ab-muted">
        · {count} review{count === 1 ? "" : "s"}
      </span>
    </span>
  )
}
