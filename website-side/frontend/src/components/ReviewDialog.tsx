import { useState } from "react"
import { Star, X } from "lucide-react"

const LABELS = ["", "Poor", "Fair", "Good", "Very good", "Excellent"]
const MAX = 1000

type Props = {
  agentName: string
  propertyTitle: string
  initial?: { rating: number; review: string | null }
  onSubmit: (rating: number, review: string) => Promise<void>
  onClose: () => void
}

/** 1–5 stars + optional review. The backend re-checks eligibility. */
export function ReviewDialog({ agentName, propertyTitle, initial, onSubmit, onClose }: Props) {
  const [rating, setRating] = useState(initial?.rating ?? 0)
  const [hover, setHover] = useState(0)
  const [review, setReview] = useState(initial?.review ?? "")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const shown = hover || rating

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!rating) {
      setError("Choose a rating from 1 to 5 stars.")
      return
    }
    setBusy(true)
    setError("")
    try {
      await onSubmit(rating, review.trim())
    } catch (submitError) {
      setError((submitError as Error).message)
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[2200] flex items-end justify-center bg-black/55 backdrop-blur-sm sm:items-center sm:p-4" onClick={onClose}>
      <form
        onSubmit={submit}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="review-title"
        className="ab-pop w-full max-w-md rounded-t-2xl border border-ab-border bg-ab-card p-5 shadow-2xl sm:rounded-2xl"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-ab-faint">{initial ? "Edit your review" : "Rate your agent"}</p>
            <h2 id="review-title" className="text-lg font-bold text-ab-text">{agentName}</h2>
            <p className="text-xs text-ab-muted">For {propertyTitle}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-full p-2 text-ab-muted hover:bg-ab-hover">
            <X className="h-4 w-4" />
          </button>
        </div>

        <fieldset className="mt-4">
          <legend className="sr-only">Rating</legend>
          <div className="flex items-center gap-1" onMouseLeave={() => setHover(0)}>
            {[1, 2, 3, 4, 5].map((n) => (
              <label key={n} className="cursor-pointer p-1" onMouseEnter={() => setHover(n)}>
                <input type="radio" name="rating" value={n} checked={rating === n} onChange={() => setRating(n)} className="sr-only" />
                <Star className={`h-9 w-9 transition ${n <= shown ? "fill-ab-warning text-ab-warning" : "text-ab-border-strong"}`} aria-hidden="true" />
                <span className="sr-only">{n} star{n > 1 ? "s" : ""}</span>
              </label>
            ))}
            <span className="ml-2 text-sm font-semibold text-ab-text">{LABELS[shown]}</span>
          </div>
        </fieldset>

        <label className="mt-4 block text-sm font-medium text-ab-muted">
          Review <span className="text-ab-faint">(optional)</span>
          <textarea
            value={review}
            onChange={(event) => setReview(event.target.value.slice(0, MAX))}
            rows={4}
            placeholder="How did your agent help you?"
            className="mt-1 w-full resize-none rounded-xl border border-ab-border bg-ab-input p-3 text-sm text-ab-text placeholder:text-ab-faint focus:border-ab-accent focus:outline-none"
          />
          <span className="block text-right text-[11px] text-ab-faint">{review.length}/{MAX}</span>
        </label>
        <p className="text-[11px] text-ab-faint">Your review is shown publicly as your first name and last initial, marked “Verified client”.</p>

        {error && <p role="alert" className="mt-3 rounded-lg border border-ab-danger/40 bg-ab-danger/10 px-3 py-2 text-sm text-ab-danger">{error}</p>}

        <div className="mt-4 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-xl border border-ab-border px-4 py-2 text-sm font-medium text-ab-text">Cancel</button>
          <button type="submit" disabled={busy} className="rounded-xl bg-ab-accent px-4 py-2 text-sm font-semibold text-ab-ink disabled:opacity-60">
            {busy ? "Saving…" : initial ? "Save changes" : "Submit review"}
          </button>
        </div>
      </form>
    </div>
  )
}
