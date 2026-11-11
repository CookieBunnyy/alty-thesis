// Deals from inquiry to closing (/deals). Company staff see every deal;
// sellers see and work only their own (inquiries, viewings, lost).
import { useCallback, useMemo, useState, type FormEvent } from "react"
import { ArrowRight, CircleX, LoaderCircle, Plus, X } from "lucide-react"
import { Link } from "@/components/Link"
import { contains, date, dateTime, isManagement, statusLabel, text } from "./format"
import { Badge, Button, DataTable, Drawer, Facts, LoadState, PageHeader, SearchBox, Section, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData, useOpenRecord } from "./useApiData"
import { t } from "./i18n"
import { DealSteps } from "./dealSteps"
import { FINANCING_LABEL, nextStep, type Milestone } from "./dealStepsData"

type Deal = {
  id: number; stage: string; client_id: string; buyer_name: string | null; buyer_phone: string | null; buyer_email: string | null
  listing_id: number | null; property_title: string | null; project_name: string | null; agent_id: string | null; seller_name: string | null
  inquiry_date: string | null; viewing_type: string | null; viewing_at: string | null; reservation_date: string | null
  reservation_status: string | null; developer_status: string; closing_date: string | null; lost_reason: string | null
  reservation_transaction_id: string | null; sale_transaction_id: string | null; notes: string | null; created_by: string | null
  created_at: string; updated_at: string
  financing_type: string | null; equity_terms_months: number | null; milestones?: Milestone[]
  events?: { id: number; from_stage: string | null; to_stage: string | null; changes: Record<string, { old: string | null; new: string | null }>; note: string | null; actor: string | null; created_at: string }[]
}
type Summary = { by_stage: Record<string, number>; stages: string[]; viewing_types: string[]; developer_statuses: string[]; financing_types: string[] }
type Option = { id: string; label: string }

const STAGE_LABEL: Record<string, string> = {
  INQUIRY: "Inquiry", VIEWING: "Viewing", RESERVED: "Reserved", DEVELOPER_PROCESSING: "Under evaluation", CLOSED: "Closed", LOST: "Lost",
}
const DEV_LABEL: Record<string, string> = { NOT_STARTED: "Not started", SUBMITTED: "Submitted", IN_PROCESS: "In process", APPROVED: "Approved", RETURNED: "Returned" }
const stageLabel = (s: string) => t(STAGE_LABEL[s] ?? s)

/** The seller's own deals. */
export function SellerDealsPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageHeader title="Your deals, from inquiry to closing" subtitle="Record your buyers' inquiries and viewings (physical or virtual), and follow each sale: pending, reserved, under evaluation, closed. Abellar Realty records the reservation, the steps after it and the closing." />
      <DealsPipeline mode="seller" />
    </div>
  )
}

export function DealsPipeline({ mode }: { mode: "company" | "seller" }) {
  const { api, user } = useStaffAuth()
  const { id, open, close } = useOpenRecord()
  const [search, setSearch] = useState("")
  const [stage, setStage] = useState("")
  const [creating, setCreating] = useState(false)
  const canManage = mode === "company" && isManagement(user?.role)
  const load = useCallback(() => Promise.all([api<Deal[]>("/deals"), api<Summary>("/deals/summary")]), [api])
  const { data, error, loading, reload } = useApiData(load, `deals:${mode}`)
  const [deals, summary] = data ?? [null, null]
  const rows = useMemo(() => deals ?? [], [deals])
  const shown = rows.filter((d) => (!stage || d.stage === stage) && contains([d.buyer_name, d.property_title, d.project_name, d.seller_name], search))
  const selected = id ? rows.find((d) => String(d.id) === id) ?? null : null

  const columns: Column<Deal>[] = [
    { key: "buyer", label: "Buyer", sort: (d) => d.buyer_name ?? "", render: (d) => <span className="font-semibold">{text(d.buyer_name)}</span> },
    { key: "property", label: "Property / project", sort: (d) => d.property_title ?? "", render: (d) => <span className="min-w-0"><span className="block truncate">{text(d.property_title)}</span>{d.project_name && <span className="block truncate text-xs text-ab-faint">{d.project_name}</span>}</span> },
    ...(mode === "company" ? [{ key: "seller", label: "Seller", sort: (d: Deal) => d.seller_name ?? "", render: (d: Deal) => text(d.seller_name), hideOnPhone: true }] : []),
    { key: "stage", label: "Stage", sort: (d) => d.stage, render: (d) => <span className="inline-flex items-center gap-1.5"><Badge value={d.stage} />{(d.stage === "INQUIRY" || d.stage === "VIEWING") && <span className="text-xs text-ab-faint">{t("Pending")}</span>}</span> },
    { key: "next", label: "Next step", sort: (d) => nextStep(d.milestones) ?? "", render: (d) => (["RESERVED", "DEVELOPER_PROCESSING", "CLOSED"].includes(d.stage) ? text(nextStep(d.milestones) ? t(nextStep(d.milestones)!) : null) : "—"), hideOnPhone: true },
    { key: "viewing", label: "Viewing", sort: (d) => d.viewing_at ?? "", render: (d) => (d.viewing_type ? `${statusLabel(d.viewing_type)}${d.viewing_at ? ` · ${dateTime(d.viewing_at)}` : ""}` : "—"), hideOnPhone: true },
    { key: "inquiry", label: "Inquiry date", sort: (d) => d.inquiry_date ?? "", render: (d) => (d.inquiry_date ? date(d.inquiry_date) : "—"), hideOnPhone: true },
    { key: "updated", label: "Last update", sort: (d) => d.updated_at, render: (d) => date(d.updated_at) },
  ]

  return (
    <div className="space-y-4">
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {summary && (
        <>
          <Tiles items={[...summary.stages, "LOST"].map((s) => ({ label: stageLabel(s), value: summary.by_stage[s] ?? 0, onClick: () => setStage(stage === s ? "" : s), active: stage === s }))} />
          <div className="flex flex-wrap items-center gap-2">
            <div className="w-full sm:w-auto sm:flex-1"><SearchBox value={search} onChange={setSearch} placeholder="Search buyer, property, project or seller" /></div>
            {(mode === "seller" || canManage) && <Button variant="primary" onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> {t("New inquiry")}</Button>}
          </div>
          <DataTable exportTitle="Deals from inquiry to closing" rows={shown} columns={columns} rowKey={(d) => String(d.id)} onOpen={(d) => open(String(d.id))}
            empty={rows.length ? "No deals match these filters." : "No deals yet. Record a buyer's inquiry to start one."} initialSort={{ key: "updated", dir: "desc" }} />
        </>
      )}
      {selected && summary && <DealDrawer deal={selected} summary={summary} mode={mode} canManage={canManage} onClose={close} onChanged={() => void reload()} />}
      {creating && summary && <DealForm mode={mode} summary={summary} onClose={() => setCreating(false)} onSaved={(d) => { setCreating(false); void reload().then(() => open(String(d.id))) }} />}
    </div>
  )
}

function Stepper({ stage, stages }: { stage: string; stages: string[] }) {
  const reached = stages.indexOf(stage)
  return (
    <ol className="flex flex-wrap items-center gap-1.5 text-xs" aria-label={t("Deal stage")}>
      {stages.map((s, index) => (
        <li key={s} className="flex items-center gap-1.5">
          <span className={`rounded-full px-2.5 py-1 font-semibold ${stage !== "LOST" && index <= reached ? "bg-ab-accent text-ab-ink" : "bg-ab-card-2 text-ab-muted"}`}>{stageLabel(s)}</span>
          {index < stages.length - 1 && <span className="text-ab-faint" aria-hidden>›</span>}
        </li>
      ))}
      {stage === "LOST" && <li><Badge value="LOST" /></li>}
    </ol>
  )
}

function DealDrawer({ deal: listed, summary, mode, canManage, onClose, onChanged }: { deal: Deal; summary: Summary; mode: "company" | "seller"; canManage: boolean; onClose: () => void; onChanged: () => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const load = useCallback(() => api<Deal>(`/deals/${listed.id}`), [api, listed.id])
  const detail = useApiData(load)
  const deal = detail.data ?? listed
  const [busy, setBusy] = useState(false)
  const [viewing, setViewing] = useState(false)
  const [losing, setLosing] = useState(false)
  const closed = deal.stage === "CLOSED" || deal.stage === "LOST"
  const run = async (request: Promise<unknown>, done: string) => {
    setBusy(true)
    try {
      await request
      toast(done)
      await detail.reload()
      onChanged()
    } catch (actionError) {
      toast(t((actionError as Error).message), "error")
    } finally {
      setBusy(false)
    }
  }
  const move = (stage: string) => run(api(`/deals/${deal.id}/stage`, { method: "POST", body: JSON.stringify({ stage }) }), t("Moved to {stage}.", { stage: stageLabel(stage) }))
  return (
    <Drawer title={text(deal.buyer_name)} subtitle={<span className="flex flex-wrap items-center gap-2"><Badge value={deal.stage} /> {text(deal.property_title)}</span>} onClose={onClose}
      footer={!closed && (
        <>
          <Button variant="danger" onClick={() => setLosing(true)}><CircleX className="h-4 w-4" /> {t("Buyer didn't proceed")}</Button>
          <Button onClick={() => setViewing(true)}>{t(deal.viewing_type ? "Change viewing" : "Arrange viewing")}</Button>
          {canManage && (deal.stage === "INQUIRY" || deal.stage === "VIEWING") && <Button variant="primary" disabled={busy} onClick={() => void move("RESERVED")}><ArrowRight className="h-4 w-4" /> {t("Mark reserved")}</Button>}
        </>
      )}>
      <Stepper stage={deal.stage} stages={summary.stages} />
      <Section title="Deal">
        <Facts items={[
          ["Buyer", deal.buyer_name],
          ["Contact", [deal.buyer_phone, deal.buyer_email].filter(Boolean).join(" · ") || null],
          ["Property", deal.listing_id && mode === "company" ? <Link to={`/manage/properties?id=${deal.listing_id}`} className="hover:underline">{text(deal.property_title)}</Link> : deal.property_title],
          ["Project", deal.project_name],
          ["Seller", deal.seller_name],
          ["Inquiry date", deal.inquiry_date ? date(deal.inquiry_date) : null],
          ["Viewing", deal.viewing_type ? `${statusLabel(deal.viewing_type)}${deal.viewing_at ? ` · ${dateTime(deal.viewing_at)}` : ""}` : null],
          ["Reservation date", deal.reservation_date ? date(deal.reservation_date) : null],
          ["Reservation status", deal.reservation_status ? statusLabel(deal.reservation_status) : null],
          ["Financing", deal.financing_type ? t(FINANCING_LABEL[deal.financing_type] ?? deal.financing_type) : null],
          ["Developer processing", t(DEV_LABEL[deal.developer_status] ?? deal.developer_status)],
          ["Closing date", deal.closing_date ? date(deal.closing_date) : null],
          ["Why it was lost", deal.lost_reason],
          ["Notes", deal.notes],
        ]} />
        {mode === "company" && (deal.reservation_transaction_id || deal.sale_transaction_id) && (
          <p className="mt-2 flex flex-wrap gap-3 text-xs">
            {deal.reservation_transaction_id && <Link to={`/manage/transactions?id=${deal.reservation_transaction_id}`} className="font-semibold text-ab-accent hover:underline">{t("Open the reservation record")}</Link>}
            {deal.sale_transaction_id && <Link to={`/manage/transactions?id=${deal.sale_transaction_id}`} className="font-semibold text-ab-accent hover:underline">{t("Open the sale record")}</Link>}
          </p>
        )}
      </Section>
      {canManage && !closed && (deal.stage === "RESERVED" || deal.stage === "DEVELOPER_PROCESSING") && (
        <Section title="Processing with the developer">
          <label className="block text-sm font-medium">{t("Developer processing status")}
            <select value={deal.developer_status} disabled={busy} onChange={(e) => void run(api(`/deals/${deal.id}`, { method: "PUT", body: JSON.stringify({ developer_status: e.target.value }) }), t("Saved."))}
              className="mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm">
              {summary.developer_statuses.map((s) => <option key={s} value={s}>{t(DEV_LABEL[s] ?? s)}</option>)}
            </select>
          </label>
          <p className="mt-2 text-xs text-ab-faint">{t("The deal closes when its sale is recorded: from the sale document, or Proceed to sale on the reservation.")}</p>
        </Section>
      )}
      <DealSteps deal={deal} financingTypes={summary.financing_types ?? []} onChanged={async () => { await detail.reload(); onChanged() }} />
      <Section title="History">
        <LoadState loading={detail.loading && !detail.data} error={detail.error} onRetry={detail.reload} />
        <ol className="space-y-2">
          {[...(deal.events ?? [])].reverse().map((e) => (
            <li key={e.id} className="rounded-xl border border-ab-border p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold">{e.to_stage ? `${e.from_stage ? `${stageLabel(e.from_stage)} → ` : ""}${stageLabel(e.to_stage)}` : t("Updated")}</span>
                <span className="text-xs text-ab-faint">{dateTime(e.created_at)} · {text(e.actor)}</span>
              </div>
              {e.note && <p className="mt-1 break-words text-ab-muted">{e.note}</p>}
              {Object.keys(e.changes ?? {}).length > 0 && (
                <ul className="mt-1 text-xs text-ab-muted">{Object.entries(e.changes).map(([k, v]) => <li key={k}>{t(k.replace(/_/g, " "))}: {text(v.old)} → {text(v.new)}</li>)}</ul>
              )}
            </li>
          ))}
        </ol>
      </Section>
      {viewing && <ViewingDialog deal={deal} summary={summary} onClose={() => setViewing(false)} onSaved={() => { setViewing(false); void detail.reload(); onChanged() }} />}
      {losing && <LostDialog busy={busy} onClose={() => setLosing(false)} onConfirm={(note) => { setLosing(false); void run(api(`/deals/${deal.id}/stage`, { method: "POST", body: JSON.stringify({ stage: "LOST", note }) }), t("Marked as lost.")) }} />}
    </Drawer>
  )
}

const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"

function Modal({ title, onClose, onSubmit, children, footer }: { title: string; onClose: () => void; onSubmit: (e: FormEvent) => void; children: React.ReactNode; footer: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" aria-label={t("Cancel")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={onSubmit} noValidate className="ab-pop relative flex max-h-[94dvh] w-full max-w-2xl flex-col rounded-t-2xl border border-ab-border bg-ab-card shadow-2xl sm:rounded-2xl">
        <header className="flex items-center justify-between border-b border-ab-border px-5 py-4">
          <h2 className="text-lg font-bold">{title}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close")} className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><X className="h-4 w-4" /></button>
        </header>
        <div className="overflow-y-auto">{children}</div>
        <footer className="flex justify-end gap-2 border-t border-ab-border px-5 py-3">{footer}</footer>
      </form>
    </div>
  )
}

const localInput = (iso: string | null) => (iso ? iso.slice(0, 16) : "")

function ViewingDialog({ deal, summary, onClose, onSaved }: { deal: Deal; summary: Summary; onClose: () => void; onSaved: () => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const [type, setType] = useState(deal.viewing_type ?? "PHYSICAL")
  const [at, setAt] = useState(localInput(deal.viewing_at))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    try {
      await api(`/deals/${deal.id}`, { method: "PUT", body: JSON.stringify({ viewing_type: type, viewing_at: at || null }) })
      toast(t("Viewing saved."))
      onSaved()
    } catch (saveError) {
      setError(t((saveError as Error).message))
      setBusy(false)
    }
  }
  return (
    <Modal title={t("Viewing")} onClose={onClose} onSubmit={submit}
      footer={<><Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button><Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Save")}</Button></>}>
      <div className="grid gap-3 p-5 sm:grid-cols-2">
        <fieldset className="sm:col-span-2">
          <legend className="text-sm font-medium">{t("Viewing type")}</legend>
          <div className="mt-1 flex gap-2">
            {summary.viewing_types.map((v) => (
              <label key={v} className={`flex min-h-10 flex-1 cursor-pointer items-center justify-center gap-2 rounded-xl border px-3 text-sm font-semibold ${type === v ? "border-ab-accent bg-ab-accent-soft text-ab-accent" : "border-ab-border"}`}>
                <input type="radio" name="viewing" value={v} checked={type === v} onChange={() => setType(v)} className="sr-only" />{t(v === "PHYSICAL" ? "Physical (on site)" : "Virtual (online)")}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="text-sm font-medium sm:col-span-2">{t("Schedule")}<input type="datetime-local" className={field} value={at} onChange={(e) => setAt(e.target.value)} /></label>
        {error && <p role="alert" className="text-sm text-ab-danger sm:col-span-2">{error}</p>}
      </div>
    </Modal>
  )
}

function LostDialog({ busy, onClose, onConfirm }: { busy: boolean; onClose: () => void; onConfirm: (note: string) => void }) {
  const [note, setNote] = useState("")
  const [error, setError] = useState("")
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!note.trim()) return setError(t("Say why the buyer didn't proceed."))
    onConfirm(note.trim())
  }
  return (
    <Modal title={t("Buyer didn't proceed")} onClose={onClose} onSubmit={submit}
      footer={<><Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button><Button type="submit" variant="danger" disabled={busy}>{t("Mark as lost")}</Button></>}>
      <div className="p-5">
        <label className="block text-sm font-medium">{t("Reason *")}<textarea className={`${field} min-h-24`} value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("e.g. Chose another project")} /></label>
        {error && <p role="alert" className="mt-2 text-sm text-ab-danger">{error}</p>}
      </div>
    </Modal>
  )
}

function DealForm({ mode, summary, onClose, onSaved }: { mode: "company" | "seller"; summary: Summary; onClose: () => void; onSaved: (d: Deal) => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const loadOptions = useCallback(async (): Promise<[Option[], Option[]]> => {
    if (mode === "seller") {
      const listings = await api<{ listing_id: number; title: string | null; project_name: string | null }[]>("/seller/listings")
      return [listings.map((l) => ({ id: String(l.listing_id), label: [l.title, l.project_name].filter(Boolean).join(" · ") })), []]
    }
    const [listings, sellers] = await Promise.all([
      api<{ listing_id: number; title: string | null; project_name?: string | null }[]>("/property-listings?limit=5000"),
      api<{ agent_id: string; full_name: string; status: string }[]>("/agents"),
    ])
    return [listings.map((l) => ({ id: String(l.listing_id), label: [l.title, l.project_name].filter(Boolean).join(" · ") || `#${l.listing_id}` })),
      sellers.filter((s) => s.status === "ACTIVE").map((s) => ({ id: s.agent_id, label: s.full_name }))]
  }, [api, mode])
  const options = useApiData(loadOptions)
  const [listingsOptions, sellerOptions] = options.data ?? [[], []]
  const [form, setForm] = useState({ full_name: "", phone_number: "", email: "", listing_id: "", agent_id: "", inquiry_date: new Date().toISOString().slice(0, 10), viewing_type: "", viewing_at: "", notes: "" })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value }))
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (form.full_name.trim().length < 2) return setError(t("Enter the buyer's name."))
    if (!form.listing_id) return setError(t("Choose the property the buyer asked about."))
    setBusy(true)
    setError("")
    try {
      const saved = await api<Deal>("/deals", {
        method: "POST",
        body: JSON.stringify({
          buyer: { full_name: form.full_name.trim(), phone_number: form.phone_number.trim() || null, email: form.email.trim() || null },
          listing_id: Number(form.listing_id), agent_id: mode === "company" ? form.agent_id || null : null,
          inquiry_date: form.inquiry_date || null, viewing_type: form.viewing_type || null, viewing_at: form.viewing_at || null, notes: form.notes.trim() || null,
        }),
      })
      toast(t("Inquiry recorded for {name}.", { name: saved.buyer_name ?? "" }))
      onSaved(saved)
    } catch (saveError) {
      setError(t((saveError as Error).message))
      setBusy(false)
    }
  }
  return (
    <Modal title={t("New inquiry")} onClose={onClose} onSubmit={submit}
      footer={<><Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button><Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Record inquiry")}</Button></>}>
      <div className="grid gap-3 p-5 sm:grid-cols-2">
        <label className="text-sm font-medium sm:col-span-2">{t("Buyer's full name *")}<input className={field} value={form.full_name} onChange={set("full_name")} /></label>
        <label className="text-sm font-medium">{t("Phone")}<input className={field} value={form.phone_number} onChange={set("phone_number")} /></label>
        <label className="text-sm font-medium">{t("Email")}<input type="email" className={field} value={form.email} onChange={set("email")} /></label>
        <label className="text-sm font-medium sm:col-span-2">{t("Property *")}
          <select className={field} value={form.listing_id} onChange={set("listing_id")}>
            <option value="">{t("Choose a property…")}</option>
            {listingsOptions.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
        </label>
        {mode === "company" && (
          <label className="text-sm font-medium sm:col-span-2">{t("Seller handling the buyer")}
            <select className={field} value={form.agent_id} onChange={set("agent_id")}>
              <option value="">{t("Not assigned yet")}</option>
              {sellerOptions.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
            </select>
          </label>
        )}
        <label className="text-sm font-medium">{t("Inquiry date")}<input type="date" className={field} value={form.inquiry_date} onChange={set("inquiry_date")} /></label>
        <label className="text-sm font-medium">{t("Viewing type")}
          <select className={field} value={form.viewing_type} onChange={set("viewing_type")}>
            <option value="">{t("Not arranged yet")}</option>
            {summary.viewing_types.map((v) => <option key={v} value={v}>{t(v === "PHYSICAL" ? "Physical (on site)" : "Virtual (online)")}</option>)}
          </select>
        </label>
        {form.viewing_type && <label className="text-sm font-medium sm:col-span-2">{t("Viewing schedule")}<input type="datetime-local" className={field} value={form.viewing_at} onChange={set("viewing_at")} /></label>}
        <label className="text-sm font-medium sm:col-span-2">{t("Notes")}<textarea className={`${field} min-h-20`} value={form.notes} onChange={set("notes")} /></label>
        {error && <p role="alert" className="text-sm text-ab-danger sm:col-span-2">{error}</p>}
      </div>
    </Modal>
  )
}
