import { useEffect, useState } from "react"
import { X } from "lucide-react"
import type { Property } from "../types"

const BACKEND_URL = "https://alty-thesis.onrender.com"

type Agent = {
  agent_id: string
  full_name: string
}

type Props = {
  property: Property
  onClose: () => void
  onSubmitted: () => void
}

export function ClientTransactionModal({ property, onClose, onSubmitted }: Props) {
  const [agents, setAgents] = useState<Agent[]>([])
  const [agentId, setAgentId] = useState("")
  const [transactionType, setTransactionType] = useState<"RESERVED" | "SOLD">("RESERVED")
  const [transactionDate, setTransactionDate] = useState(
    new Date().toISOString().slice(0, 10),
  )
  const [fullName, setFullName] = useState("")
  const [location, setLocation] = useState("")
  const [phoneNumber, setPhoneNumber] = useState("")
  const [email, setEmail] = useState("")
  const [error, setError] = useState("")
  const [isLoadingAgents, setIsLoadingAgents] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    let isCurrent = true
    fetch(`${BACKEND_URL}/agents`)
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
        if (isCurrent) {
          setError(requestError instanceof Error ? requestError.message : "Unable to load agents.")
        }
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
    setIsSubmitting(true)
    try {
      const response = await fetch(`${BACKEND_URL}/client-transactions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: fullName.trim(),
          location: location.trim() || null,
          phone_number: phoneNumber.trim() || null,
          email: email.trim() || null,
          property_id: Number(property.listing_id),
          agent_id: agentId,
          transaction_type: transactionType,
          transaction_date: `${transactionDate}T12:00:00+08:00`,
        }),
      })
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        throw new Error(payload.detail ?? "The transaction could not be submitted.")
      }
      onSubmitted()
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
        className="max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-[#d8d1c8] bg-[#f5f3ee] shadow-2xl"
        role="dialog"
      >
        <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-[#d8d1c8] bg-[#f5f3ee] px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#60756c]">Client transaction</p>
            <h2 className="mt-1 text-xl font-semibold text-[#183c32]" id="client-transaction-title">Submit an inquiry</h2>
          </div>
          <button aria-label="Close form" className="rounded-lg p-2 text-[#234b42] hover:bg-[#e7e3dc]" onClick={onClose} type="button">
            <X className="h-4 w-4" />
          </button>
        </header>

        <form className="space-y-5 p-5" onSubmit={handleSubmit}>
          <section className="rounded-xl border border-[#d8d1c8] bg-white p-4" aria-label="Selected property">
            <p className="text-xs font-semibold uppercase tracking-wide text-[#71817a]">Selected property · #{property.listing_id}</p>
            <h3 className="mt-1 font-semibold text-[#183c32]">{property.title}</h3>
            <p className="mt-1 text-sm text-[#60756c]">{property.category ?? "Property"} · {property.village_name}</p>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm text-[#234b42]">
              <span>Price</span><strong className="text-right">{formattedPrice}</strong>
              <span>Bedrooms / baths</span><strong className="text-right">{property.num_bedrooms} / {property.num_bathrooms}</strong>
              <span>Monthly rate</span><strong className="text-right">{property.monthly_rate ? `₱${Number(property.monthly_rate).toLocaleString("en-PH")}` : "—"}</strong>
            </div>
          </section>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-sm font-medium text-[#234b42] sm:col-span-2">
              Full Name
              <input autoComplete="name" className="w-full rounded-lg border border-[#c9c2b9] bg-white px-3 py-2.5 text-[#183c32] outline-none focus:border-[#567b6d]" onChange={(event) => setFullName(event.target.value)} required value={fullName} />
            </label>
            <label className="space-y-1 text-sm font-medium text-[#234b42]">
              Location
              <input autoComplete="address-level2" className="w-full rounded-lg border border-[#c9c2b9] bg-white px-3 py-2.5 text-[#183c32] outline-none focus:border-[#567b6d]" onChange={(event) => setLocation(event.target.value)} value={location} />
            </label>
            <label className="space-y-1 text-sm font-medium text-[#234b42]">
              Phone Number
              <input autoComplete="tel" className="w-full rounded-lg border border-[#c9c2b9] bg-white px-3 py-2.5 text-[#183c32] outline-none focus:border-[#567b6d]" onChange={(event) => setPhoneNumber(event.target.value)} value={phoneNumber} />
            </label>
            <label className="space-y-1 text-sm font-medium text-[#234b42]">
              Email Address
              <input autoComplete="email" className="w-full rounded-lg border border-[#c9c2b9] bg-white px-3 py-2.5 text-[#183c32] outline-none focus:border-[#567b6d]" onChange={(event) => setEmail(event.target.value)} type="email" value={email} />
            </label>
            <label className="space-y-1 text-sm font-medium text-[#234b42]">
              Transaction Date
              <input className="w-full rounded-lg border border-[#c9c2b9] bg-white px-3 py-2.5 text-[#183c32] outline-none focus:border-[#567b6d]" onChange={(event) => setTransactionDate(event.target.value)} required type="date" value={transactionDate} />
            </label>
          </div>

          <fieldset className="space-y-2">
            <legend className="text-sm font-medium text-[#234b42]">Transaction Intent</legend>
            <div className="grid grid-cols-2 gap-2">
              {(["RESERVED", "SOLD"] as const).map((value) => (
                <button
                  aria-pressed={transactionType === value}
                  className={`rounded-lg border px-3 py-2.5 text-sm font-semibold transition ${transactionType === value ? "border-[#214e40] bg-[#dcebd3] text-[#183c32]" : "border-[#d8d1c8] bg-white text-[#60756c] hover:bg-[#f9f6f2]"}`}
                  key={value}
                  onClick={() => setTransactionType(value)}
                  type="button"
                >
                  {value === "RESERVED" ? "Reserve" : "Purchase / Sold"}
                </button>
              ))}
            </div>
          </fieldset>

          <label className="block space-y-1 text-sm font-medium text-[#234b42]">
            Assigned Agent
            <select className="w-full rounded-lg border border-[#c9c2b9] bg-white px-3 py-2.5 text-[#183c32] outline-none focus:border-[#567b6d]" disabled={isLoadingAgents || agents.length === 0} onChange={(event) => setAgentId(event.target.value)} required value={agentId}>
              {isLoadingAgents && <option value="">Loading agents...</option>}
              {!isLoadingAgents && agents.length === 0 && <option value="">No active agents available</option>}
              {agents.map((agent) => <option key={agent.agent_id} value={agent.agent_id}>{agent.full_name} — {agent.agent_id}</option>)}
            </select>
          </label>

          {error && <p aria-live="polite" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}

          <footer className="flex justify-end gap-2 border-t border-[#d8d1c8] pt-4">
            <button className="rounded-lg border border-[#c9c2b9] bg-white px-4 py-2 text-sm font-medium text-[#234b42] hover:bg-[#f9f6f2]" onClick={onClose} type="button">Cancel</button>
            <button className="rounded-lg bg-[#0d3529] px-4 py-2 text-sm font-semibold text-white hover:bg-[#173f32] disabled:cursor-not-allowed disabled:opacity-50" disabled={isSubmitting || isLoadingAgents || agents.length === 0} type="submit">
              {isSubmitting ? "Submitting..." : "Submit Transaction"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}
