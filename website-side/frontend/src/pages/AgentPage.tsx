import { useEffect, useState } from "react"
import { ArrowLeft, LogIn, MapPin, MessageSquareText, Phone } from "lucide-react"
import { API_URL } from "@/config"
import { requestJson, useAuth } from "@/lib/auth"
import { AgentPhoto } from "@/components/AgentPhoto"
import { Link } from "@/components/Link"
import { SiteHeader } from "@/components/SiteHeader"
import { SiteFooter } from "@/components/SiteFooter"
import { SignInToContact } from "@/components/SignInToContact"
import { ReviewCard } from "@/components/ReviewCard"
import { RatingSummary } from "@/components/Stars"
import { Skeleton } from "@/components/Skeleton"
import type { AgentProfile, PublicReview } from "@/types"
import { CallButton } from "@/components/CallButton"

const PAGE = 10

/** Public agent profile with real client reviews. */
export function AgentPage({ agentId }: { agentId: string }) {
  const [agent, setAgent] = useState<AgentProfile | null>(null)
  const [reviews, setReviews] = useState<PublicReview[]>([])
  const [error, setError] = useState("")
  const [loadingMore, setLoadingMore] = useState(false)
  const { token, isReady } = useAuth()
  const url = `${API_URL}/api/v1/public/agents/${encodeURIComponent(agentId)}`

  useEffect(() => {
    let current = true
    if (!isReady) return // wait until a saved sign-in has been restored
    requestJson<AgentProfile>(`${url}?limit=${PAGE}`, {}, token)
      .then((data) => {
        if (!current) return
        setAgent(data)
        setReviews(data.reviews)
      })
      .catch((loadError: Error) => current && setError(loadError.message))
    return () => {
      current = false
    }
  }, [url, token, isReady])

  const loadMore = async () => {
    setLoadingMore(true)
    try {
      const data = await requestJson<AgentProfile>(`${url}?limit=${PAGE}&offset=${reviews.length}`, {}, token)
      setReviews((current) => [...current, ...data.reviews])
    } finally {
      setLoadingMore(false)
    }
  }

  const phone = agent?.phone_number?.replace(/[^\d+]/g, "")

  return (
    <div className="flex min-h-dvh flex-col bg-ab-bg text-ab-text">
      <SiteHeader />
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10">
        <Link to="/" className="inline-flex items-center gap-1 text-sm text-ab-muted hover:text-ab-text">
          <ArrowLeft className="h-4 w-4" /> Home
        </Link>
        {error && <p role="alert" className="mt-8 text-center text-ab-danger">Unable to load agent information: {error}</p>}
        {!agent && !error && (
          <div role="status" className="mt-4 space-y-8">
            <span className="sr-only">Loading agent profile…</span>
            <div className="flex items-center gap-5 rounded-3xl border border-ab-border bg-ab-card p-6" aria-hidden="true">
              <Skeleton className="h-20 w-20 rounded-3xl" />
              <div className="flex-1 space-y-3">
                <Skeleton className="h-3 w-32" />
                <Skeleton className="h-8 w-56" />
                <Skeleton className="h-4 w-40" />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2" aria-hidden="true">
              {[0, 1].map((index) => (
                <div key={index} className="space-y-3 rounded-2xl border border-ab-border bg-ab-card p-5">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/4" />
                </div>
              ))}
            </div>
          </div>
        )}
        {agent && (
          <>
            <section className="ab-pop mt-4 flex flex-col gap-5 rounded-3xl border border-ab-border bg-ab-card p-6 md:flex-row md:items-center">
              <AgentPhoto name={agent.full_name} photoUrl={agent.photo_url} className="h-20 w-20 rounded-3xl text-3xl" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-ab-accent">Abellar Realty agent</p>
                <h1 className="text-3xl font-extrabold">{agent.full_name}</h1>
                {agent.agent_location && (
                  <p className="mt-1 flex items-center gap-1 text-ab-muted"><MapPin className="h-4 w-4" /> {agent.agent_location}</p>
                )}
                <div className="mt-2"><RatingSummary rating={agent.client_rating} count={agent.review_count} /></div>
              </div>
              {!phone && agent.contact_requires_sign_in && agent.has_phone && (
                <SignInToContact>
                  <LogIn className="h-4 w-4" /> Sign in to call or text
                </SignInToContact>
              )}
              {phone && (
                <div className="flex gap-2">
                  <CallButton phone={phone} name={agent.full_name} className="inline-flex items-center gap-2 rounded-xl bg-ab-accent px-4 py-2.5 text-sm font-semibold text-ab-ink"><Phone className="h-4 w-4" /> Call</CallButton>
                  <CallButton kind="text" phone={phone} name={agent.full_name} className="inline-flex items-center gap-2 rounded-xl border border-ab-border-strong px-4 py-2.5 text-sm font-semibold"><MessageSquareText className="h-4 w-4" /> Text</CallButton>
                </div>
              )}
            </section>

            <section className="mt-10">
              <h2 className="text-xl font-bold">Client reviews</h2>
              <p className="text-sm text-ab-muted">From clients whose transactions with {agent.full_name.split(" ")[0]} were completed.</p>
              {reviews.length === 0 ? (
                <p className="mt-4 rounded-2xl border border-dashed border-ab-border bg-ab-card p-8 text-center text-ab-muted">No client reviews yet.</p>
              ) : (
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  {reviews.map((review, index) => (
                    <ReviewCard key={review.id} review={review} showAgent={false} className="ab-card-in" style={{ animationDelay: `${Math.min(index, 6) * 60}ms` }} />
                  ))}
                </div>
              )}
              {reviews.length < agent.review_count && (
                <button type="button" onClick={loadMore} disabled={loadingMore} className="mx-auto mt-6 block rounded-xl border border-ab-border-strong px-5 py-2.5 text-sm font-semibold hover:bg-ab-hover">
                  {loadingMore ? "Loading…" : "Show more reviews"}
                </button>
              )}
            </section>
          </>
        )}
      </main>
      <SiteFooter />
    </div>
  )
}
