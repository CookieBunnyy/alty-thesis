import { useCallback, useEffect, useState } from "react"
import { Building, LogOut, Mail, MapPin, Phone, Star } from "lucide-react"
import { useAuth } from "@/lib/auth"
import { Link } from "@/components/Link"
import { navigate, useLocation } from "@/lib/router"
import { peso, sizedImage } from "@/lib/media"
import { SiteHeader } from "@/components/SiteHeader"
import { SiteFooter } from "@/components/SiteFooter"
import { ReviewDialog } from "@/components/ReviewDialog"
import { Stars } from "@/components/Stars"
import { LoadingLabel, RowSkeleton } from "@/components/Skeleton"
import type { ClientTransaction } from "@/types"

const STATUS: Record<string, string> = {
  RESERVED: "bg-ab-warning/15 text-ab-warning",
  COMPLETED: "bg-ab-success/15 text-ab-success",
  CANCELLED: "bg-ab-danger/15 text-ab-danger",
}
const date = (value: string) => new Intl.DateTimeFormat("en-PH", { dateStyle: "medium" }).format(new Date(value))

/** The signed-in client's profile, transactions and reviews (live data). */
export function AccountPage() {
  const { client, isReady, authed, signOut } = useAuth()
  const { href } = useLocation()
  const [transactions, setTransactions] = useState<ClientTransaction[] | null>(null)
  const [error, setError] = useState("")
  const [reviewing, setReviewing] = useState<ClientTransaction | null>(null)

  useEffect(() => {
    if (isReady && !client) navigate(`/signin?next=${encodeURIComponent(href)}`, { replace: true })
  }, [isReady, client, href])

  const load = useCallback(() => {
    authed<ClientTransaction[]>("/transactions")
      .then((data) => {
        setTransactions(data)
        setError("")
      })
      .catch((loadError: Error) => setError(loadError.message))
  }, [authed])
  useEffect(() => {
    if (client) load()
  }, [client, load])

  // Jump to #transactions / #reviews once content exists.
  useEffect(() => {
    if (transactions && window.location.hash) document.querySelector(window.location.hash)?.scrollIntoView({ behavior: "smooth" })
  }, [transactions])

  const saveReview = async (transaction: ClientTransaction, rating: number, review: string) => {
    const body = JSON.stringify({ rating, review: review || null })
    if (transaction.review) await authed(`/reviews/${transaction.review.id}`, { method: "PUT", body })
    else await authed("/reviews", { method: "POST", body: JSON.stringify({ transaction_id: transaction.transaction_id, rating, review: review || null }) })
    setReviewing(null)
    load()
  }

  if (!client) {
    return (
      <div className="min-h-dvh bg-ab-bg">
        <SiteHeader />
        <LoadingLabel text="Loading your account…" />
      </div>
    )
  }
  const reviewed = (transactions ?? []).filter((t) => t.review)

  return (
    <div className="flex min-h-dvh flex-col bg-ab-bg text-ab-text">
      <SiteHeader />
      <main className="mx-auto w-full max-w-5xl flex-1 space-y-10 px-4 py-10">
        <section className="ab-pop flex flex-col gap-5 rounded-3xl border border-ab-border bg-ab-card p-6 md:flex-row md:items-center">
          <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-ab-accent text-2xl font-black text-ab-ink">
            {client.full_name.split(" ").map((part) => part[0]).slice(0, 2).join("")}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-bold uppercase tracking-[0.22em] text-ab-accent">My profile</p>
            <h1 className="text-2xl font-extrabold">{client.full_name}</h1>
            <p className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm text-ab-muted">
              {client.email && <span className="inline-flex items-center gap-1.5"><Mail className="h-4 w-4" />{client.email}</span>}
              {client.phone_number && <span className="inline-flex items-center gap-1.5"><Phone className="h-4 w-4" />{client.phone_number}</span>}
              {client.location && <span className="inline-flex items-center gap-1.5"><MapPin className="h-4 w-4" />{client.location}</span>}
            </p>
            <p className="mt-1 text-xs text-ab-faint">Member since {date(client.member_since)}</p>
          </div>
          <button type="button" onClick={() => { signOut(); navigate("/") }} className="inline-flex items-center gap-2 self-start rounded-xl border border-ab-border px-4 py-2 text-sm font-semibold text-ab-danger hover:bg-ab-hover">
            <LogOut className="h-4 w-4" /> Log out
          </button>
        </section>

        <section id="transactions" className="scroll-mt-24">
          <h2 className="text-xl font-bold">My transactions</h2>
          <p className="text-sm text-ab-muted">
            Reservations and purchases recorded by your agent from your documents, matched to your account's email or phone number.
          </p>
          {error && <p role="alert" className="mt-4 text-ab-danger">Unable to load your transactions: {error}</p>}
          {!transactions && !error && (
            <div role="status" className="mt-4 space-y-3">
              <span className="sr-only">Loading your transactions…</span>
              <RowSkeleton />
              <RowSkeleton />
            </div>
          )}
          {transactions?.length === 0 && (
            <p className="mt-4 rounded-2xl border border-dashed border-ab-border bg-ab-card p-8 text-center text-ab-muted">
              No transactions yet. When your agent submits your reservation or purchase documents, they'll appear here.{" "}
              <Link to="/properties" className="font-semibold text-ab-accent hover:underline">Browse properties</Link>
            </p>
          )}
          <div className="mt-4 space-y-3">
            {transactions?.map((t) => (
              <article key={t.transaction_id} className="ab-card-in flex flex-col gap-4 rounded-2xl border border-ab-border bg-ab-card p-4 sm:flex-row">
                {t.property.photo ? (
                  <img src={sizedImage(t.property.photo, 320)} alt="" loading="lazy" className="h-28 w-full rounded-xl object-cover sm:w-40" />
                ) : (
                  <span className="flex h-28 w-full items-center justify-center rounded-xl bg-ab-card-2 text-ab-faint sm:w-40"><Building className="h-8 w-8" /></span>
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-ab-accent-soft px-2 py-0.5 text-[10px] font-bold uppercase text-ab-accent">
                      {t.transaction_type === "SOLD" ? "Purchase" : "Reservation"}
                    </span>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${STATUS[t.status] ?? ""}`}>{t.status}</span>
                    <span className="text-xs text-ab-faint">{date(t.transaction_date)} · Ref {t.transaction_id.slice(0, 8)}</span>
                  </div>
                  <h3 className="mt-1 font-semibold">{t.property.title}</h3>
                  <p className="text-sm text-ab-muted">{t.property.village_name} · {peso(t.amount)}</p>
                  <p className="mt-2 text-sm">
                    Agent:{" "}
                    <Link to={`/agents/${encodeURIComponent(t.agent.agent_id)}`} className="font-semibold text-ab-accent hover:underline">{t.agent.full_name}</Link>
                    {t.agent.phone_number && (
                      <a href={`tel:${t.agent.phone_number.replace(/[^\d+]/g, "")}`} className="ml-2 inline-flex items-center gap-1 text-ab-muted hover:text-ab-text">
                        <Phone className="h-3.5 w-3.5" /> {t.agent.phone_number}
                      </a>
                    )}
                  </p>
                </div>
                <div className="flex shrink-0 flex-col items-start justify-center gap-2 sm:items-end">
                  {t.review ? (
                    <>
                      <Stars value={t.review.rating} />
                      <button type="button" onClick={() => setReviewing(t)} className="text-sm font-semibold text-ab-accent hover:underline">Edit review</button>
                    </>
                  ) : t.can_review ? (
                    <button type="button" onClick={() => setReviewing(t)} className="inline-flex items-center gap-1.5 rounded-xl bg-ab-accent px-4 py-2 text-sm font-semibold text-ab-ink">
                      <Star className="h-4 w-4" /> Rate agent
                    </button>
                  ) : (
                    <span className="max-w-[12rem] text-right text-xs text-ab-faint">
                      {t.status === "CANCELLED" ? "Cancelled transactions can't be reviewed." : "You can rate your agent once this is completed."}
                    </span>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>

        <section id="reviews" className="scroll-mt-24">
          <h2 className="text-xl font-bold">My reviews</h2>
          <p className="text-sm text-ab-muted">Shown publicly as your first name and last initial, marked “Verified client”.</p>
          {transactions && reviewed.length === 0 && (
            <p className="mt-4 rounded-2xl border border-dashed border-ab-border bg-ab-card p-8 text-center text-ab-muted">You haven't reviewed an agent yet.</p>
          )}
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {reviewed.map((t) => (
              <article key={t.transaction_id} className="rounded-2xl border border-ab-border bg-ab-card p-4">
                <div className="flex items-center justify-between">
                  <Stars value={t.review!.rating} />
                  <button type="button" onClick={() => setReviewing(t)} className="text-sm font-semibold text-ab-accent hover:underline">Edit</button>
                </div>
                <p className="mt-2 text-sm">{t.review!.review ? `“${t.review!.review}”` : <span className="italic text-ab-muted">No written review.</span>}</p>
                <p className="mt-2 text-xs text-ab-faint">{t.agent.full_name} · {t.property.title}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
      <SiteFooter />

      {reviewing && (
        <ReviewDialog
          agentName={reviewing.agent.full_name}
          propertyTitle={reviewing.property.title}
          initial={reviewing.review ?? undefined}
          onSubmit={(rating, review) => saveReview(reviewing, rating, review)}
          onClose={() => setReviewing(null)}
        />
      )}
    </div>
  )
}
