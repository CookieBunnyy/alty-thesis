import { useEffect, useState } from "react"
import { CheckCircle2, X } from "lucide-react"
import type { Property } from "../types"
import { API_URL } from "../config"

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
  onClose: () => void
  onSubmitted: (result: SubmissionResult) => void
}

const errorText = (payload: unknown, fallback: string) => {
  const detail = (payload as { detail?: unknown })?.detail
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) return detail.map((item) => item?.msg ?? String(item)).join("; ")
  return fallback
}

export function ClientTransactionModal({ property, onClose, onSubmitted }: Props) {
  const [agents, setAgents] = useState<Agent[]>([])
  const [agentId, setAgentId] = useState("")
  const [transactionType, setTransactionType] = useState<"RESERVED" | "SOLD">("RESERVED")
  const [fullName, setFullName] = useState("")
  const [location, setLocation] = useState("")
  const [phoneNumber, setPhoneNumber] = useState("")
  const [email, setEmail] = useState("")
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
        setAgentId(data[0]?.agent_id ?? "")
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

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError("")
    if (!email.trim() && !phoneNumber.trim()) {
      setError("Provide an email address or phone number so the agent can reach you.")
      return
    }
    setIsSubmitting(true)
    try {
      // The backend validates the property and its status, creates or matches
      // the client, records the transaction and updates the property status.
      const response = await fetch(`${API_URL}/api/v1/public/transactions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          property_id: Number(property.listing_id),
          agent_id: agentId,
          transaction_type: transactionType,
          full_name: fullName.trim(),
          location: location.trim() || null,
          phone_number: phoneNumber.trim() || null,
          email: email.trim() || null,
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(errorText(payload, "The transaction could not be submitted."))
      setResult(payload as SubmissionResult)
      onSubmitted(payload as SubmissionResult)
    } catch (submitError: unknown) {
      setError(submitError instanceof Error ? submitError.message : "The transaction could not be submitted.")
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
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/55 p-4 backdrop-blur-sm">
      <section
        aria-labelledby="client-transaction-title"
        aria-modal="true"
        className="max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-ab-border bg-ab-card shadow-2xl"
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

        {result ? (
          <div className="space-y-4 p-6 text-center">
            <CheckCircle2 className="mx-auto h-12 w-12 text-ab-text" />
            <p className="text-lg font-semibold text-ab-text">{result.message}</p>
            <p className="text-sm text-ab-muted">
              Reference {result.transaction_id?.slice(0, 8)} · Property is now {result.property_status}.
            </p>
            <button className="rounded-lg bg-ab-sidebar px-4 py-2 text-sm font-semibold text-ab-text" onClick={onClose} type="button">
              Done
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

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1 text-sm font-medium text-ab-muted sm:col-span-2">
                Full Name
                <input autoComplete="name" className="w-full rounded-lg border border-ab-border bg-ab-card-2 px-3 py-2.5 text-ab-text outline-none focus:border-ab-accent" minLength={2} onChange={(event) => setFullName(event.target.value)} required value={fullName} />
              </label>
              <label className="space-y-1 text-sm font-medium text-ab-muted sm:col-span-2">
                Address / Location
                <input autoComplete="street-address" className="w-full rounded-lg border border-ab-border bg-ab-card-2 px-3 py-2.5 text-ab-text outline-none focus:border-ab-accent" onChange={(event) => setLocation(event.target.value)} value={location} />
              </label>
              <label className="space-y-1 text-sm font-medium text-ab-muted">
                Phone Number
                <input autoComplete="tel" className="w-full rounded-lg border border-ab-border bg-ab-card-2 px-3 py-2.5 text-ab-text outline-none focus:border-ab-accent" onChange={(event) => setPhoneNumber(event.target.value)} value={phoneNumber} />
              </label>
              <label className="space-y-1 text-sm font-medium text-ab-muted">
                Email Address
                <input autoComplete="email" className="w-full rounded-lg border border-ab-border bg-ab-card-2 px-3 py-2.5 text-ab-text outline-none focus:border-ab-accent" onChange={(event) => setEmail(event.target.value)} type="email" value={email} />
              </label>
            </div>

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
              <select className="w-full rounded-lg border border-ab-border bg-ab-card-2 px-3 py-2.5 text-ab-text outline-none focus:border-ab-accent" disabled={isLoadingAgents || agents.length === 0} onChange={(event) => setAgentId(event.target.value)} required value={agentId}>
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
                {isSubmitting ? "Submitting..." : "Submit Transaction"}
              </button>
            </footer>
          </form>
        )}
      </section>
    </div>
  )
}
