// Tripping schedule: site visits with buyers, like the office whiteboard
// (date, pick-up, time, subdivision, agent). The board updates live: it checks
// for changes every few seconds. Agents schedule and update their trips and
// notify the buyers (in their website account, or by text message).
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react"
import { BellRing, Check, Copy, LoaderCircle, MessageSquareText, Pencil, Plus, Search, Trash2, UserPlus, X } from "lucide-react"
import { date, isSeller } from "./format"
import { Button, Confirm, LoadState, PageHeader, Select } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData } from "./useApiData"
import { t, locale } from "./i18n"

type Buyer = { id?: number; client_id: string | null; name: string; phone: string | null; notified_at?: string | null }
type Trip = {
  id: number; trip_date: string; pickup_time: string; pickup_point: string; subdivision: string
  listing_id: number | null; listing_title: string | null; partner_id: number | null; partner_name: string | null
  agent_id: string; agent_name: string; agent_phone: string | null; status: string; notes: string | null
  buyers: Buyer[]; needs_notice: boolean; updated_at: string; updated_by: string | null
}
type Notice = { name: string; phone: string | null; in_app: boolean; text: string; sms_link: string | null }
const STATUSES = ["SCHEDULED", "CONFIRMED", "ONGOING", "DONE", "CANCELLED"]
const POLL_MS = 8000

const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Manila" })
const daysAgo = (days: number) => new Date(new Date().getTime() - days * 86400000).toLocaleDateString("en-CA", { timeZone: "Asia/Manila" })
const clock = (hhmm: string) => {
  const [h, m] = hhmm.split(":").map(Number)
  return new Date(2000, 0, 1, h, m).toLocaleTimeString(locale(), { hour: "numeric", minute: "2-digit" })
}
const dayLabel = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(locale(), { weekday: "short", month: "short", day: "numeric" })

/** Re-run `reload` whenever /trips/version changes. */
function useLiveTrips(reload: () => Promise<unknown> | void, version: string | undefined) {
  const { api } = useStaffAuth()
  const [checkedAt, setCheckedAt] = useState<Date | null>(null)
  const [live, setLive] = useState(true)
  useEffect(() => {
    if (!version) return
    let alive = true
    const timer = window.setInterval(async () => {
      if (document.hidden) return
      try {
        const { version: latest } = await api<{ version: string }>("/trips/version")
        if (!alive) return
        setLive(true)
        setCheckedAt(new Date())
        if (latest !== version) void reload()
      } catch {
        if (alive) setLive(false)
      }
    }, POLL_MS)
    return () => { alive = false; window.clearInterval(timer) }
  }, [api, reload, version])
  return { live, checkedAt }
}

export function TripsPage() {
  const { api, user } = useStaffAuth()
  const company = !isSeller(user?.role)
  const [range, setRange] = useState("upcoming")
  const [agent, setAgent] = useState("")
  const [editing, setEditing] = useState<Trip | "new" | null>(null)
  const [notifying, setNotifying] = useState<{ trip: Trip; messages: Notice[]; inApp: number } | null>(null)
  const [deleting, setDeleting] = useState<Trip | null>(null)
  const toast = useToast()
  const from = range === "past" ? daysAgo(60) : range === "upcoming" ? today() : daysAgo(7)
  const load = useCallback(() => api<{ trips: Trip[]; version: string }>(`/trips?from=${from}`), [api, from])
  const { data, error, loading, reload } = useApiData(load, `trips:${from}`)
  const { live, checkedAt } = useLiveTrips(reload, data?.version)
  const trips = useMemo(() => (data?.trips ?? []).filter((trip) => (!agent || trip.agent_id === agent) && (range !== "past" || trip.trip_date < today())), [data, agent, range])
  const agents = useMemo(() => [...new Map((data?.trips ?? []).map((trip) => [trip.agent_id, trip.agent_name])).entries()], [data])
  const byDay = useMemo(() => {
    const groups = new Map<string, Trip[]>()
    for (const trip of trips) groups.set(trip.trip_date, [...(groups.get(trip.trip_date) ?? []), trip])
    return [...groups.entries()]
  }, [trips])

  const notify = async (trip: Trip) => {
    try {
      const result = await api<{ sent_in_app: number; messages: Notice[] }>(`/trips/${trip.id}/notify`, { method: "POST", body: JSON.stringify({}) })
      setNotifying({ trip, messages: result.messages, inApp: result.sent_in_app })
      void reload()
    } catch (notifyError) {
      toast(t((notifyError as Error).message), "error")
    }
  }
  const setStatus = async (trip: Trip, status: string) => {
    try {
      await api(`/trips/${trip.id}/status`, { method: "POST", body: JSON.stringify({ status }) })
      void reload()
    } catch (statusError) {
      toast(t((statusError as Error).message), "error")
    }
  }
  const remove = async () => {
    if (!deleting) return
    try {
      await api(`/trips/${deleting.id}`, { method: "DELETE" })
      setDeleting(null)
      void reload()
    } catch (deleteError) {
      toast(t((deleteError as Error).message), "error")
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Tripping schedule"
        subtitle="Site visits with buyers: date, pick-up, time, subdivision and agent. The board updates live for everyone. Agents schedule their trips and notify their buyers."
        actions={<Button variant="primary" onClick={() => setEditing("new")}><Plus className="h-4 w-4" /> {t("Schedule a trip")}</Button>}
      />
      <div className="flex flex-wrap items-center gap-2">
        <Select label="Show" value={range} onChange={setRange} options={[{ value: "upcoming", label: "Today and upcoming" }, { value: "week", label: "From last week" }, { value: "past", label: "Past trips" }]} />
        {company && agents.length > 1 && <Select label="Agent" value={agent} onChange={setAgent} options={[{ value: "", label: "All agents" }, ...agents.map(([id, name]) => ({ value: id, label: name }))]} />}
        <span className="ml-auto flex items-center gap-1.5 text-xs text-ab-muted" role="status">
          <span className={`h-2 w-2 rounded-full ${live ? "animate-pulse bg-ab-success" : "bg-ab-danger"}`} aria-hidden />
          {live ? t("Live") : t("Reconnecting…")}{checkedAt ? ` · ${t("checked {time}", { time: checkedAt.toLocaleTimeString(locale(), { hour: "numeric", minute: "2-digit", second: "2-digit" }) })}` : ""}
        </span>
      </div>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && trips.length === 0 && (
        <div className="rounded-2xl border border-dashed border-ab-border px-4 py-14 text-center text-sm text-ab-muted">
          {t(range === "past" ? "No past trips." : "No trips scheduled.")} <button type="button" onClick={() => setEditing("new")} className="font-semibold text-ab-accent hover:underline">{t("Schedule a trip")}</button>
        </div>
      )}
      {trips.length > 0 && (
        <ul className="space-y-3 md:hidden" aria-label={t("Tripping schedule")}>
          {trips.map((trip) => (
            <li key={trip.id} className={`rounded-2xl border bg-ab-card p-4 ${trip.trip_date === today() ? "border-ab-accent" : "border-ab-border"} ${trip.status === "CANCELLED" ? "opacity-60" : ""}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-xs font-bold uppercase tracking-wide text-ab-accent">{dayLabel(trip.trip_date)} · {clock(trip.pickup_time)}{trip.trip_date === today() ? ` · ${t("Today")}` : ""}</p>
                  <p className="text-base font-bold">{trip.subdivision}</p>
                  <p className="text-sm text-ab-muted">{t("Pick-up")}: {trip.pickup_point}</p>
                  <p className="text-sm text-ab-muted">{t("Agent")}: {trip.agent_name}</p>
                  {trip.buyers.length > 0 && <p className="text-xs text-ab-faint">{t("Buyers")}: {trip.buyers.map((b) => b.name).join(", ")}</p>}
                </div>
                <select aria-label={t("Status")} value={trip.status} onChange={(e) => void setStatus(trip, e.target.value)}
                  className="shrink-0 rounded-lg border border-ab-border bg-ab-input px-2 py-1 text-xs font-semibold">
                  {STATUSES.map((s) => <option key={s} value={s}>{t(s.charAt(0) + s.slice(1).toLowerCase())}</option>)}
                </select>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <button type="button" onClick={() => void notify(trip)} disabled={!trip.buyers.length}
                  className={`inline-flex min-h-9 items-center gap-1 rounded-lg px-3 text-xs font-semibold disabled:opacity-40 ${trip.needs_notice && trip.buyers.length ? "bg-ab-accent text-ab-ink" : "border border-ab-border"}`}>
                  <BellRing className="h-3.5 w-3.5" /> {t(trip.needs_notice ? "Notify" : "Notify again")}
                </button>
                <button type="button" onClick={() => setEditing(trip)} aria-label={t("Edit trip")} className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><Pencil className="h-4 w-4" /></button>
                <button type="button" onClick={() => setDeleting(trip)} aria-label={t("Delete trip")} className="rounded-lg p-2 text-ab-danger hover:bg-ab-hover"><Trash2 className="h-4 w-4" /></button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {trips.length > 0 && (
        <div className="hidden overflow-x-auto rounded-2xl border-2 border-ab-text/80 bg-ab-card md:block">
          <table className="w-full min-w-[860px] border-collapse text-sm">
            <caption className="sr-only">{t("Tripping schedule")}</caption>
            <thead>
              <tr className="border-b-2 border-ab-text/80 text-left">
                {["Date", "Pick-up", "Time", "Subdivision", "Agent", "Buyers", "Status", ""].map((label) => (
                  <th key={label} scope="col" className="border-r-2 border-ab-text/80 px-3 py-2.5 text-xs font-black uppercase tracking-wider last:border-r-0">{label ? t(label) : <span className="sr-only">{t("Actions")}</span>}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {byDay.map(([day, items]) => items.map((trip, index) => {
                return (
                  <tr key={trip.id} className={`border-t border-ab-border align-top ${trip.status === "CANCELLED" ? "text-ab-faint line-through decoration-ab-danger/60" : ""} ${day === today() ? "bg-ab-accent-soft/40" : ""}`}>
                    <td className="border-r-2 border-ab-text/80 px-3 py-2 font-semibold">{index === 0 ? <>{dayLabel(day)}{day === today() && <span className="block text-[10px] font-bold uppercase text-ab-accent">{t("Today")}</span>}</> : ""}</td>
                    <td className="border-r-2 border-ab-text/80 px-3 py-2">{trip.pickup_point}</td>
                    <td className="whitespace-nowrap border-r-2 border-ab-text/80 px-3 py-2 font-semibold">{clock(trip.pickup_time)}</td>
                    <td className="border-r-2 border-ab-text/80 px-3 py-2">
                      <span className="font-semibold">{trip.subdivision}</span>
                      {trip.partner_name && <span className="block text-xs text-ab-faint">{trip.partner_name}</span>}
                      {trip.notes && <span className="block text-xs italic text-ab-muted">{trip.notes}</span>}
                    </td>
                    <td className="border-r-2 border-ab-text/80 px-3 py-2">{trip.agent_name}</td>
                    <td className="border-r-2 border-ab-text/80 px-3 py-2 text-xs">
                      {trip.buyers.length ? trip.buyers.map((b) => <span key={b.id ?? b.name} className="block">{b.name}{b.notified_at ? <Check className="ml-1 inline h-3 w-3 text-ab-success" aria-label={t("notified")} /> : null}</span>) : <span className="text-ab-faint">—</span>}
                    </td>
                    <td className="border-r-2 border-ab-text/80 px-3 py-2">
                      {(
                        <select aria-label={t("Status")} value={trip.status} onChange={(e) => void setStatus(trip, e.target.value)}
                          className="rounded-lg border border-ab-border bg-ab-input px-2 py-1 text-xs font-semibold no-underline">
                          {STATUSES.map((s) => <option key={s} value={s}>{t(s.charAt(0) + s.slice(1).toLowerCase())}</option>)}
                        </select>
                      )}
                    </td>
                    <td className="px-2 py-2">
                      <span className="flex items-center gap-1 no-underline">
                        <button type="button" onClick={() => void notify(trip)} disabled={!trip.buyers.length}
                          title={trip.buyers.length ? t("Notify the buyers") : t("Add buyers first")}
                          className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold disabled:opacity-40 ${trip.needs_notice && trip.buyers.length ? "bg-ab-accent text-ab-ink" : "border border-ab-border hover:bg-ab-hover"}`}>
                          <BellRing className="h-3.5 w-3.5" /> {t(trip.needs_notice ? "Notify" : "Notify again")}
                        </button>
                        <button type="button" onClick={() => setEditing(trip)} aria-label={t("Edit trip")} className="rounded-lg p-1.5 text-ab-muted hover:bg-ab-hover"><Pencil className="h-4 w-4" /></button>
                        <button type="button" onClick={() => setDeleting(trip)} aria-label={t("Delete trip")} className="rounded-lg p-1.5 text-ab-danger hover:bg-ab-hover"><Trash2 className="h-4 w-4" /></button>
                      </span>
                    </td>
                  </tr>
                )
              }))}
            </tbody>
          </table>
        </div>
      )}
      {editing && <TripForm trip={editing === "new" ? null : editing} company={company} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void reload() }} />}
      {notifying && <NotifyResult {...notifying} onClose={() => setNotifying(null)} />}
      {deleting && <Confirm title="Delete trip?" message={t("Delete the trip to {place} on {date}? Buyers aren't told automatically.", { place: deleting.subdivision, date: date(deleting.trip_date) })} confirmLabel="Delete" onConfirm={() => void remove()} onCancel={() => setDeleting(null)} />}
    </div>
  )
}

const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"
type BuyerOption = { client_id: string; name: string; phone: string | null; has_account: boolean }
type AgentOption = { agent_id: string; full_name: string; status: string }

function TripForm({ trip, company, onClose, onSaved }: { trip: Trip | null; company: boolean; onClose: () => void; onSaved: () => void }) {
  const { api, user } = useStaffAuth()
  const toast = useToast()
  const loadAgents = useCallback(() => (company ? api<AgentOption[]>("/agents") : Promise.resolve([] as AgentOption[])), [api, company])
  const agents = useApiData(loadAgents, company ? "trip-agents" : undefined)
  const [form, setForm] = useState({
    trip_date: trip?.trip_date ?? today(), pickup_time: trip?.pickup_time ?? "08:00", pickup_point: trip?.pickup_point ?? "Abellar Realty office",
    subdivision: trip?.subdivision ?? "", agent_id: trip?.agent_id ?? user?.agent_id ?? "", status: trip?.status ?? "SCHEDULED", notes: trip?.notes ?? "",
  })
  const [buyers, setBuyers] = useState<Buyer[]>(trip?.buyers.map((b) => ({ client_id: b.client_id, name: b.name, phone: b.phone })) ?? [])
  const [query, setQuery] = useState("")
  const [found, setFound] = useState<BuyerOption[]>([])
  const [manual, setManual] = useState({ name: "", phone: "" })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }))

  useEffect(() => {
    let alive = true
    const timer = window.setTimeout(async () => {
      try {
        const rows = await api<BuyerOption[]>(`/trips/buyer-options?q=${encodeURIComponent(query)}`)
        if (alive) setFound(rows)
      } catch { if (alive) setFound([]) }
    }, 250)
    return () => { alive = false; window.clearTimeout(timer) }
  }, [api, query])

  const add = (buyer: Buyer) => setBuyers((all) => (all.some((b) => (buyer.client_id ? b.client_id === buyer.client_id : b.name.toLowerCase() === buyer.name.toLowerCase())) ? all : [...all, buyer]))

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError("")
    if (!form.subdivision.trim()) return setError(t("Enter the subdivision / project."))
    if (!form.pickup_point.trim()) return setError(t("Enter the pick-up point."))
    if (company && !form.agent_id) return setError(t("Choose the agent."))
    setBusy(true)
    try {
      const body = { ...form, subdivision: form.subdivision.trim(), pickup_point: form.pickup_point.trim(), notes: form.notes.trim() || null,
        agent_id: form.agent_id || null, buyers: buyers.map((b) => (b.client_id ? { client_id: b.client_id } : { name: b.name, phone: b.phone })) }
      await api(trip ? `/trips/${trip.id}` : "/trips", { method: trip ? "PUT" : "POST", body: JSON.stringify(body) })
      toast(t(trip ? "Trip updated. Notify the buyers about the change." : "Trip scheduled. Notify the buyers when ready."))
      onSaved()
    } catch (saveError) {
      setError(t((saveError as Error).message))
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={t(trip ? "Edit trip" : "Schedule a trip")}>
      <button type="button" aria-label={t("Cancel")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={submit} noValidate className="ab-pop relative flex max-h-[94dvh] w-full max-w-2xl flex-col rounded-t-2xl border border-ab-border bg-ab-card shadow-2xl sm:rounded-2xl">
        <header className="flex items-center justify-between border-b border-ab-border px-5 py-4">
          <h2 className="text-lg font-bold">{t(trip ? "Edit trip" : "Schedule a trip")}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close")} className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><X className="h-4 w-4" /></button>
        </header>
        <div className="grid flex-1 gap-3 overflow-y-auto p-5 sm:grid-cols-2">
          <label className="block text-sm font-medium">{t("Date")}<input type="date" className={field} value={form.trip_date} onChange={(e) => set("trip_date", e.target.value)} /></label>
          <label className="block text-sm font-medium">{t("Pick-up time")}<input type="time" className={field} value={form.pickup_time} onChange={(e) => set("pickup_time", e.target.value)} /></label>
          <label className="block text-sm font-medium">{t("Pick-up point")}<input className={field} value={form.pickup_point} onChange={(e) => set("pickup_point", e.target.value)} /></label>
          <label className="block text-sm font-medium">{t("Subdivision / project")}<input className={field} value={form.subdivision} onChange={(e) => set("subdivision", e.target.value)} placeholder={t("e.g. Casa Feliz, Lipa")} /></label>
          {company ? (
            <label className="block text-sm font-medium">{t("Agent")}
              <select className={field} value={form.agent_id} onChange={(e) => set("agent_id", e.target.value)}>
                <option value="">{t("Choose the agent")}</option>
                {(agents.data ?? []).filter((a) => a.status === "ACTIVE" || a.agent_id === form.agent_id).map((a) => <option key={a.agent_id} value={a.agent_id}>{a.full_name}</option>)}
              </select>
            </label>
          ) : <p className="self-end text-sm text-ab-muted">{t("Agent: you")}</p>}
          <label className="block text-sm font-medium">{t("Status")}
            <select className={field} value={form.status} onChange={(e) => set("status", e.target.value)}>
              {STATUSES.map((s) => <option key={s} value={s}>{t(s.charAt(0) + s.slice(1).toLowerCase())}</option>)}
            </select>
          </label>
          <fieldset className="space-y-2 rounded-xl border border-ab-border p-3 sm:col-span-2">
            <legend className="px-1 text-sm font-semibold">{t("Buyers joining")}</legend>
            {buyers.length > 0 && (
              <ul className="flex flex-wrap gap-1.5">
                {buyers.map((b) => (
                  <li key={b.client_id ?? b.name} className="flex items-center gap-1 rounded-full bg-ab-card-2 py-1 pl-3 pr-1 text-xs font-semibold">
                    {b.name}{b.phone && <span className="font-normal text-ab-faint">· {b.phone}</span>}
                    <button type="button" onClick={() => setBuyers((all) => all.filter((x) => x !== b))} aria-label={t("Remove {name}", { name: b.name })} className="rounded-full p-0.5 hover:bg-ab-hover"><X className="h-3 w-3" /></button>
                  </li>
                ))}
              </ul>
            )}
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 mt-0.5 h-4 w-4 -translate-y-1/2 text-ab-faint" />
              <input aria-label={t("Find a buyer")} className={`${field} pl-9`} value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t(company ? "Search buyers by name or number" : "Search your buyers by name or number")} />
            </div>
            {found.length > 0 && (
              <ul className="max-h-36 overflow-y-auto rounded-xl border border-ab-border">
                {found.filter((o) => !buyers.some((b) => b.client_id === o.client_id)).slice(0, 8).map((o) => (
                  <li key={o.client_id}>
                    <button type="button" onClick={() => add({ client_id: o.client_id, name: o.name, phone: o.phone })} className="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm hover:bg-ab-hover">
                      <span>{o.name} <span className="text-xs text-ab-faint">{o.phone}</span></span>
                      {o.has_account && <span className="rounded-full bg-ab-accent-soft px-2 py-0.5 text-[10px] font-semibold text-ab-accent">{t("has website account")}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div className="grid grid-cols-[1fr_1fr_auto] gap-2">
              <input aria-label={t("Buyer's name")} className={field} value={manual.name} onChange={(e) => setManual((m) => ({ ...m, name: e.target.value }))} placeholder={t("Or type a name")} />
              <input aria-label={t("Mobile number")} className={field} inputMode="tel" value={manual.phone} onChange={(e) => setManual((m) => ({ ...m, phone: e.target.value }))} placeholder="0917 123 4567" />
              <Button onClick={() => { if (manual.name.trim()) { add({ client_id: null, name: manual.name.trim(), phone: manual.phone.trim() || null }); setManual({ name: "", phone: "" }) } }}><UserPlus className="h-4 w-4" /> {t("Add")}</Button>
            </div>
          </fieldset>
          <label className="block text-sm font-medium sm:col-span-2">{t("Notes")}<textarea className={`${field} min-h-16`} value={form.notes} onChange={(e) => set("notes", e.target.value)} placeholder={t("e.g. Bring 2 valid IDs; van plate ABC 1234")} /></label>
        </div>
        {error && <p role="alert" className="mx-5 mb-2 rounded-lg border border-ab-danger/40 bg-ab-danger/10 px-3 py-2 text-sm text-ab-danger">{error}</p>}
        <footer className="flex justify-end gap-2 border-t border-ab-border px-5 py-3">
          <Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button>
          <Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t(trip ? "Save" : "Schedule")}</Button>
        </footer>
      </form>
    </div>
  )
}

function NotifyResult({ trip, messages, inApp, onClose }: { trip: Trip; messages: Notice[]; inApp: number; onClose: () => void }) {
  const toast = useToast()
  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast(t("Message copied."))
    } catch {
      toast(t("Couldn't copy. Select the message and copy it."), "error")
    }
  }
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={t("Buyers notified")}>
      <button type="button" aria-label={t("Close")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <div className="ab-pop relative flex max-h-[90dvh] w-full max-w-lg flex-col rounded-2xl border border-ab-border bg-ab-card shadow-2xl">
        <header className="border-b border-ab-border px-5 py-4">
          <h2 className="text-lg font-bold">{t("Buyers notified")}</h2>
          <p className="text-xs text-ab-muted">{trip.subdivision} · {dayLabel(trip.trip_date)} · {clock(trip.pickup_time)}</p>
        </header>
        <div className="space-y-3 overflow-y-auto p-5">
          {inApp > 0 && <p className="rounded-xl bg-ab-success/10 px-3 py-2 text-sm"><Check className="mr-1 inline h-4 w-4 text-ab-success" />{t("{n} buyer(s) see the schedule in their website account right away.", { n: inApp })}</p>}
          {messages.map((m) => (
            <div key={m.name} className="rounded-xl border border-ab-border p-3">
              <p className="text-sm font-semibold">{m.name} {m.phone && <span className="font-normal text-ab-faint">· {m.phone}</span>}</p>
              <p className="mt-1 whitespace-pre-line rounded-lg bg-ab-card-2 p-2 text-xs">{m.text}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {m.sms_link && <a href={m.sms_link} className="inline-flex items-center gap-1 rounded-lg bg-ab-accent px-2.5 py-1 text-xs font-semibold text-ab-ink"><MessageSquareText className="h-3.5 w-3.5" /> {t("Send as text message")}</a>}
                <button type="button" onClick={() => void copy(m.text)} className="inline-flex items-center gap-1 rounded-lg border border-ab-border px-2.5 py-1 text-xs font-semibold hover:bg-ab-hover"><Copy className="h-3.5 w-3.5" /> {t("Copy for Messenger / Viber")}</button>
              </div>
            </div>
          ))}
        </div>
        <footer className="flex justify-end border-t border-ab-border px-5 py-3"><Button variant="primary" onClick={onClose}>{t("Done")}</Button></footer>
      </div>
    </div>
  )
}
