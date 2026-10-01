import { useEffect, useState } from "react"
import { CheckCircle2, LoaderCircle, UserRound, X } from "lucide-react"
import type { Property } from "../types"
import { API_URL } from "../config"
import { NearbyAgents } from "./NearbyAgents"
import { ApiError, useAuth } from "@/lib/auth"
import { Link } from "@/components/Link"

type Agent = {
  agent_id: string
  full_name: string
  agent_location?: string | null
}

type SubmissionResult = {
  transaction_id: string
  property_status: string
  already_recorded: boolean
  message: string
}

type Props = {
  property: Property
  initialType?: "RESERVED" | "SOLD"
  onClose: () => void
  onSubmitted: (result: SubmissionResult) => void
}

/** Reserve / purchase for a signed-in client. The backend re-validates the
 *  property, its status and the agent, records the transaction against the
 *  client's own record and updates the property status. */
export function ClientTransactionModal({ property, initialType = "RESERVED", onClose, onSubmitted }: Props) {
  const { client, authed } = useAuth()
  const [agents, setAgents] = useState<Agent[]>([])
  const [agentId, setAgentId] = useState("")
  const [agentChosen, setAgentChosen] = useState(false)
  // Re-check the status before showing the form; the backend validates again on submit.
  const [liveStatus, setLiveStatus] = useState<string | null>(null)
  const [transactionType, setTransactionType] = useState<"RESERVED" | "SOLD">(initialType)
  const [error, setError] = useState("")
  const [result, setResult] = useState<SubmissionResult | null>(null)
  const [isLoadingAgents, setIsLoadingAgents] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    let isCurrent = true
    fetch(`${API_URL}/api/v1/public/agents`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load available agents.")
        return (await response.json()) as Agent[]
      })
      .then((data) => {
        if (!isCurrent) return
        setAgents(data)
        setAgentId((chosen) => chosen || data[0]?.agent_id || "")
      })
      .catch((requestError: unknown) => {
        if (isCurrent) setError(requestError instanceof Error ? requestError.message : "Unable to load agents.")
      })
      .finally(() => {
        if (isCurrent) setIsLoadingAgents(false)
      })
    return () => {
      isCurrent = false
    }
  }, [])

  useEffect(() => {
    let isCurrent = true
    fetch(`${API_URL}/api/v1/public/properties/${property.listing_id}`)
      .then(async (response) => {
        if (response.status === 404) return "UNLISTED"
        if (!response.ok) throw new Error()
        return String(((await response.json()) as Property).status ?? "AVAILABLE")
      })
      .then((status) => isCurrent && setLiveStatus(status))
      .catch(() => isCurrent && setLiveStatus(property.status ?? "AVAILABLE")) // server re-validates on submit
    return () => {
      isCurrent = false
    }
  }, [property.listing_id, property.status])

  const chooseAgent = (id: string) => {
    setAgentChosen(true)
    setAgentId(id)
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError("")
    setIsSubmitting(true)
    try {
      const payload = await authed<SubmissionResult>("/transactions", {
        method: "POST",
        body: JSON.stringify({
          property_id: Number(property.listing_id),
          agent_id: agentId,
          transaction_type: transactionType,
        }),
      })
      setResult(payload)
      onSubmitted(payload)
    } catch (submitError: unknown) {
      setError(
        submitError instanceof ApiError && submitError.status === 401
          ? "Your session has expired. Please sign in again."
          : submitError instanceof Error
            ? submitError.message
            : "The transaction could not be submitted.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const formattedPrice = Number(property.price_total).toLocaleString("en-PH", {
    style: "currency",
    currency: "PHP",
    maximumFractionDigits: 0,
  })

  return (
    <div className="fixed inset-0 z-[2100] flex items-center justify-center bg-black/55 p-4 backdrop-blur-sm">
      <section
        aria-labelledby="client-transaction-title"
        aria-modal="true"
        className="ab-pop max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-ab-border bg-ab-card shadow-2xl"
        role="dialog"
      >
        <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-ab-border bg-ab-card px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ab-muted">Client transaction</p>
            <h2 className="mt-1 text-xl font-semibold text-ab-text" id="client-transaction-title">
              {transactionType === "RESERVED" ? "Reserve this property" : "Purchase this property"}
            </h2>
          </div>
          <button aria-label="Close form" className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover" onClick={onClose} type="button">
            <X className="h-4 w-4" />
          </button>
        </header>

        {!client ? (
          <div className="space-y-3 p-6 text-center">
            <p className="text-lg font-semibold text-ab-text">Sign in to continue</p>
            <p className="text-sm text-ab-muted">Reserving or purchasing requires an Abellar Realty client account.</p>
            <Link
              to={`/signin?next=${encodeURIComponent(`/map?property=${property.listing_id}&action=${transactionType}`)}`}
              className="inline-block rounded-xl bg-ab-accent px-5 py-2.5 text-sm font-semibold text-ab-ink"
            >
              Sign In
            </Link>
          </div>
        ) : result ? (
          <div className="space-y-4 p-6 text-center">
            <CheckCircle2 className="mx-auto h-12 w-12 text-ab-success" />
            <p className="text-lg font-semibold text-ab-text">{result.message}</p>
            <p className="text-sm text-ab-muted">
              Reference {result.transaction_id?.slice(0, 8)} · Property is now {result.property_status}.
            </p>
            <div className="flex justify-center gap-2">
              <Link to="/account#transactions" className="rounded-lg border border-ab-border-strong px-4 py-2 text-sm font-semibold text-ab-text">
                My Transactions
              </Link>
              <button className="rounded-lg bg-ab-accent px-4 py-2 text-sm font-semibold text-ab-ink" onClick={onClose} type="button">
                Done
              </button>
            </div>
          </div>
        ) : liveStatus === null ? (
          <p className="flex items-center gap-2 p-6 text-sm text-ab-muted" role="status">
            <LoaderCircle className="h-4 w-4 animate-spin text-ab-accent" /> Checking that this property is still available…
          </p>
        ) : liveStatus !== "AVAILABLE" ? (
          <div className="space-y-3 p-6 text-center">
            <p className="text-lg font-semibold text-ab-text">
              {liveStatus === "UNLISTED" ? "This property is no longer listed." : `This property is already ${liveStatus.toLowerCase()}.`}
            </p>
            <p className="text-sm text-ab-muted">It can't be reserved or purchased right now. You can still contact an agent below.</p>
            <div className="text-left">
              <NearbyAgents listingId={property.listing_id} />
            </div>
            <button className="rounded-lg bg-ab-card-2 px-4 py-2 text-sm font-semibold text-ab-text" onClick={onClose} type="button">
              Close
            </button>
          </div>
        ) : (
          <form className="space-y-5 p-5" onSubmit={handleSubmit}>
            <section className="rounded-xl border border-ab-border bg-ab-card-2 p-4" aria-label="Selected property">
              <p className="text-xs font-semibold uppercase tracking-wide text-ab-faint">
                Selected property · {property.listing_code ?? `#${property.listing_id}`}
              </p>
              <h3 className="mt-1 font-semibold text-ab-text">{property.title}</h3>
              <p className="mt-1 text-sm text-ab-muted">{property.category ?? "Property"} · {property.village_name}</p>
              <div className="mt-3 grid grid-cols-2 gap-2 text-sm text-ab-muted">
                <span>Price</span><strong className="text-right">{formattedPrice}</strong>
                <span>Bedrooms / baths</span><strong className="text-right">{property.num_bedrooms ?? "—"} / {property.num_bathrooms ?? "—"}</strong>
                <span>Monthly rate</span><strong className="text-right">{property.monthly_rate ? `₱${Number(property.monthly_rate).toLocaleString("en-PH")}` : "—"}</strong>
              </div>
            </section>

            <section className="flex items-center gap-3 rounded-xl border border-ab-border p-3" aria-label="Your details">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ab-accent-soft text-ab-accent">
                <UserRound className="h-5 w-5" />
              </span>
              <div className="min-w-0 text-sm">
                <p className="font-semibold text-ab-text">{client.full_name}</p>
                <p className="truncate text-xs text-ab-muted">
                  {[client.email, client.phone_number].filter(Boolean).join(" · ")} — your agent will use these to contact you
                </p>
              </div>
            </section>

            <NearbyAgents
              listingId={property.listing_id}
              selectedAgentId={agentId}
              onSelect={chooseAgent}
              onLoaded={(nearby) => {
                // Default to the nearest agent unless the client already picked one.
                if (!agentChosen && nearby.agents[0]) setAgentId(nearby.agents[0].agent_id)
              }}
            />

            <fieldset className="space-y-2">
              <legend className="text-sm font-medium text-ab-muted">Transaction</legend>
              <div className="grid grid-cols-2 gap-2">
                {(["RESERVED", "SOLD"] as const).map((value) => (
                  <button
                    aria-pressed={transactionType === value}
                    className={`rounded-lg border px-3 py-2.5 text-sm font-semibold transition ${transactionType === value ? "border-ab-accent bg-ab-accent-soft text-ab-text" : "border-ab-border bg-ab-card-2 text-ab-muted hover:bg-ab-card"}`}
                    key={value}
                    onClick={() => setTransactionType(value)}
                    type="button"
                  >
                    {value === "RESERVED" ? "Reserve" : "Purchase"}
                  </button>
                ))}
              </div>
              <p className="text-xs text-ab-faint">
                The listed price is recorded; your agent confirms payment terms and documents.
              </p>
            </fieldset>

            <label className="block space-y-1 text-sm font-medium text-ab-muted">
              Assigned Agent
              <select className="w-full rounded-lg border border-ab-border bg-ab-card-2 px-3 py-2.5 text-ab-text outline-none focus:border-ab-accent" disabled={isLoadingAgents || agents.length === 0} onChange={(event) => chooseAgent(event.target.value)} required value={agentId}>
                {isLoadingAgents && <option value="">Loading agents...</option>}
                {!isLoadingAgents && agents.length === 0 && <option value="">No active agents available</option>}
                {agents.map((agent) => (
                  <option key={agent.agent_id} value={agent.agent_id}>
                    {agent.full_name}{agent.agent_location ? ` — ${agent.agent_location}` : ""}
                  </option>
                ))}
              </select>
            </label>

            {error && <p aria-live="polite" className="rounded-lg border border-ab-danger/40 bg-ab-danger/10 px-3 py-2 text-sm text-ab-danger">{error}</p>}

            <footer className="flex justify-end gap-2 border-t border-ab-border pt-4">
              <button className="rounded-lg border border-ab-border bg-ab-card-2 px-4 py-2 text-sm font-medium text-ab-muted hover:bg-ab-card" onClick={onClose} type="button">Cancel</button>
              <button className="rounded-lg bg-ab-accent px-4 py-2 text-sm font-semibold text-ab-ink hover:bg-ab-accent-hover disabled:cursor-not-allowed disabled:opacity-50" disabled={isSubmitting || isLoadingAgents || agents.length === 0} type="submit">
                {isSubmitting ? "Submitting..." : transactionType === "RESERVED" ? "Submit Reservation" : "Submit Purchase"}
              </button>
            </footer>
          </form>
        )}
      </section>
    </div>
  )
}
