import { BadgeCheck, Quote } from "lucide-react"
import { Link } from "@/components/Link"
import type { PublicReview } from "@/types"
import { Stars } from "./Stars"

const date = (value: string) =>
  new Intl.DateTimeFormat("en-PH", { month: "short", year: "numeric" }).format(new Date(value))

/** A real client review. Identity is "First L." plus a verified badge; no
 *  contact details, client ID or property are shown. */
export function ReviewCard({ review, showAgent = true, className = "", style }: {
  review: PublicReview
  showAgent?: boolean
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <figure style={style} className={`flex h-full flex-col rounded-2xl border border-ab-border bg-ab-card p-5 shadow-sm ${className}`}>
      <div className="flex items-center justify-between gap-2">
        <Stars value={review.rating} />
        <Quote className="h-5 w-5 text-ab-accent/40" aria-hidden="true" />
      </div>
      <blockquote className="mt-3 flex-1 text-sm leading-relaxed text-ab-text">
        {review.review ? `“${review.review}”` : <span className="italic text-ab-muted">Rated {review.rating} out of 5 — no written review.</span>}
      </blockquote>
      <figcaption className="mt-4 border-t border-ab-border pt-3 text-xs text-ab-muted">
        <span className="flex items-center gap-1 font-semibold text-ab-text">
          {review.reviewer}
          <BadgeCheck className="h-3.5 w-3.5 text-ab-success" aria-label="Verified client" />
          <span className="font-normal text-ab-muted">Verified client</span>
        </span>
        <span className="mt-0.5 block">
          {review.transaction_type === "SOLD" ? "Purchased" : review.transaction_type === "RESERVED" ? "Reserved" : "Client"} ·{" "}
          {date(review.created_at)}
          {showAgent && review.agent?.full_name && (
            <>
              {" "}· Agent{" "}
              <Link to={`/agents/${encodeURIComponent(review.agent.agent_id)}`} className="font-medium text-ab-accent hover:underline">
                {review.agent.full_name}
              </Link>
            </>
          )}
        </span>
      </figcaption>
    </figure>
  )
}
