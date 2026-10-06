import { useEffect } from "react"
import { FileText, LoaderCircle, LockKeyhole, Phone, X } from "lucide-react"
import type { Property } from "../types"
import { NearbyAgents } from "./NearbyAgents"
import { categoryLabel } from "@/lib/categories"
import { useAuth } from "@/lib/auth"
import { Link } from "./Link"

type Props = {
  property: Property
  onClose: () => void
}

/** "Reserve / Purchase": signed-in clients see the agents near the property
 *  and call or text one of them. Nothing is booked on the website: the agent
 *  records the reservation or sale from the client's documents, which the
 *  filing manager uploads to the Document Repository. Visitors who aren't
 *  signed in are asked to sign in first and come back to this property. */
export function ContactAgentsModal({ property, onClose }: Props) {
  const { client, isReady } = useAuth()
  // After signing in: the map, this property selected, this window open again.
  const next = encodeURIComponent(`/map?property=${property.listing_id}&reserve=1`)
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose()
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  const formattedPrice = Number(property.price_total).toLocaleString("en-PH", {
    style: "currency",
    currency: "PHP",
    maximumFractionDigits: 0,
  })

  return (
    <div className="fixed inset-0 z-[2100] flex items-end justify-center bg-black/55 backdrop-blur-sm sm:items-center sm:p-4" onClick={onClose}>
      <section
        aria-labelledby="contact-agent-title"
        aria-modal="true"
        role="dialog"
        onClick={(event) => event.stopPropagation()}
        className="ab-pop max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-t-2xl border border-ab-border bg-ab-card shadow-2xl sm:rounded-2xl"
      >
        <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-ab-border bg-ab-card px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ab-muted">Interested in this property?</p>
            <h2 className="mt-1 text-xl font-semibold text-ab-text" id="contact-agent-title">
              {client ? "Reserve or purchase" : "Sign in to continue"}
            </h2>
          </div>
          <button aria-label="Close" className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover" onClick={onClose} type="button">
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="space-y-5 p-5">
          <section className="rounded-xl border border-ab-border bg-ab-card-2 p-4" aria-label="Selected property">
            <p className="text-xs font-semibold uppercase tracking-wide text-ab-faint">
              Property · {property.listing_code ?? `#${property.listing_id}`}
            </p>
            <h3 className="mt-1 font-semibold text-ab-text">{property.title}</h3>
            <p className="mt-1 text-sm text-ab-muted">
              {categoryLabel(property.category)} · {property.village_name}
            </p>
            <p className="mt-2 text-lg font-bold text-ab-accent">{formattedPrice}</p>
          </section>

          {!isReady ? (
            <p className="flex items-center gap-2 text-sm text-ab-muted" role="status">
              <LoaderCircle className="h-4 w-4 animate-spin text-ab-accent" /> Checking your account…
            </p>
          ) : !client ? (
            <section className="rounded-xl border border-ab-accent/40 bg-ab-accent-soft p-5 text-center" aria-label="Sign in required">
              <LockKeyhole className="mx-auto h-7 w-7 text-ab-accent" />
              <p className="mt-2 font-semibold text-ab-text">Sign in to continue</p>
              <p className="mt-1 text-sm text-ab-muted">
                Please sign in or create an account to proceed with your property reservation.
              </p>
              <div className="mt-4 flex flex-col justify-center gap-2 sm:flex-row">
                <Link to={`/signin?next=${next}`} className="rounded-xl bg-ab-accent px-5 py-2.5 text-sm font-semibold text-ab-ink transition hover:bg-ab-accent-hover">
                  Sign In
                </Link>
                <Link to={`/signup?next=${next}`} className="rounded-xl border border-ab-border-strong px-5 py-2.5 text-sm font-semibold text-ab-text transition hover:bg-ab-hover">
                  Create account
                </Link>
              </div>
            </section>
          ) : (
            <NearbyAgents listingId={property.listing_id} />
          )}

          <section className="rounded-xl border border-ab-border p-4 text-sm text-ab-muted" aria-label="How reservations work">
            <p className="mb-2 font-semibold text-ab-text">How reserving or buying works</p>
            <ol className="space-y-2">
              <li className="flex gap-2">
                <Phone className="mt-0.5 h-4 w-4 shrink-0 text-ab-accent" />
                Call or text an agent near the property. Mention the property code so they know which one you mean.
              </li>
              <li className="flex gap-2">
                <FileText className="mt-0.5 h-4 w-4 shrink-0 text-ab-accent" />
                Your agent prepares the reservation or purchase documents with you and submits them to Abellar Realty,
                which records the transaction.
              </li>
            </ol>
            <p className="mt-3 text-xs text-ab-faint">
              With a client account you can follow your recorded transactions and rate your agent afterwards.
            </p>
          </section>
        </div>
      </section>
    </div>
  )
}
