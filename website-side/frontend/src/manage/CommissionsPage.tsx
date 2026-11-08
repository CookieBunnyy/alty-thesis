// Commission records (sales and rentals), their approval and release, the
// supporting vouchers, and configurable commission structures (/commissions).
import { useCallback, useMemo, useState, type FormEvent } from "react"
import { BadgeCheck, FileCheck2, LoaderCircle, Plus, X } from "lucide-react"
import { Link } from "@/components/Link"
import { contains, date, dateTime, isManagement, peso, pesoShort, statusLabel, text } from "./format"
import { Badge, Button, DataTable, Drawer, Facts, LoadState, PageHeader, SearchBox, Section, Select, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData, useOpenRecord } from "./useApiData"
import { t } from "./i18n"

type Record_ = {
  id: number; kind: "SALE" | "RENTAL"; transaction_id: string | null; transaction_date: string | null; buyer_name: string | null
  agent_id: string | null; seller_name: string | null; listing_id: number | null; property_title: string | null; project_name: string | null
  property_description: string | null; lessor_name: string | null; lessee_name: string | null; monthly_rent: number | null; lease_term_months: number | null
  basis_amount: number | null; structure_id: number | null; rate_percent: number | null; amount: number; seller_share_amount: number | null
  agreement_reference: string | null; agreement_notes: string | null; status: string; approval_status: string
  approved_by: string | null; approved_at: string | null; approval_note: string | null; released_amount: number | null; released_on: string | null
  voucher_document_id: number | null; voucher: { id: number; document_id: string; name: string } | null
  record_date: string; created_by: string | null; updated_at: string
}
type Summary = {
  pending_approval: { count: number; amount: number }; approved_unreleased: { count: number; amount: number }
  released: { count: number; amount: number }; without_voucher: number
  kinds: string[]; statuses: string[]; approval_statuses: string[]; bases: string[]
}
type Structure = {
  id: number; name: string; kind: string; partner_id: number | null; partner_name: string | null; listing_id: number | null; basis: string
  rate_percent: number | null; fixed_amount: number | null; months_of_rent: number | null; seller_share_percent: number | null
  effective_from: string | null; effective_until: string | null; is_active: boolean; notes: string | null
}

const BASIS: Record<string, string> = { PERCENT_OF_PRICE: "% of the price", FIXED_AMOUNT: "Fixed amount", MONTHS_OF_RENT: "Months of rent", AS_AGREED: "As agreed (no formula)" }
const APPROVAL_TONE: Record<string, string> = { PENDING: "bg-ab-warning/15 text-ab-warning", APPROVED: "bg-ab-success/15 text-ab-success", REJECTED: "bg-ab-danger/10 text-ab-danger" }
const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"
const describe = (r: Record_) => (r.kind === "RENTAL" ? r.property_description ?? r.property_title : r.property_title) ?? "—"

export function CommissionsPage() {
  const { api, user } = useStaffAuth()
  const { id, open, close } = useOpenRecord()
  const canManage = isManagement(user?.role)
  const [view, setView] = useState<"records" | "structures">("records")
  const [search, setSearch] = useState("")
  const [kind, setKind] = useState("")
  const [state, setState] = useState("")
  const [creating, setCreating] = useState(false)
  const load = useCallback(() => Promise.all([api<Record_[]>("/commissions"), api<Summary>("/commissions/summary"), api<Structure[]>("/commissions/structures")]), [api])
  const { data, error, loading, reload } = useApiData(load, "commissions")
  const [records, summary, structures] = data ?? [null, null, null]
  const rows = useMemo(() => records ?? [], [records])
  const shown = rows.filter((r) => (!kind || r.kind === kind) &&
    (!state || (state === "NO_VOUCHER" ? !r.voucher_document_id && r.status !== "CANCELLED" : state === "PENDING" ? r.approval_status === "PENDING" && r.status !== "CANCELLED" : r.status === state)) &&
    contains([r.seller_name, r.property_title, r.project_name, r.property_description, r.buyer_name, r.lessor_name, r.agreement_reference], search))
  const selected = id ? rows.find((r) => String(r.id) === id) ?? null : null

  const columns: Column<Record_>[] = [
    { key: "date", label: "Date", sort: (r) => r.transaction_date ?? r.record_date, render: (r) => date(r.transaction_date ?? r.record_date) },
    { key: "kind", label: "Kind", sort: (r) => r.kind, render: (r) => t(r.kind === "RENTAL" ? "Rental" : "Sale") },
    { key: "seller", label: "Seller", sort: (r) => r.seller_name ?? "", render: (r) => <span className="font-semibold">{text(r.seller_name)}</span> },
    { key: "property", label: "Property", sort: (r) => describe(r), render: (r) => <span className="min-w-0"><span className="block truncate">{describe(r)}</span>{r.project_name && <span className="block truncate text-xs text-ab-faint">{r.project_name}</span>}</span>, hideOnPhone: true },
    { key: "amount", label: "Commission", align: "right", sort: (r) => r.amount, render: (r) => <span className="font-semibold tabular-nums">{peso(r.amount)}</span> },
    { key: "approval", label: "Approval", sort: (r) => r.approval_status, render: (r) => <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ${APPROVAL_TONE[r.approval_status] ?? ""}`}>{statusLabel(r.approval_status)}</span> },
    { key: "status", label: "Release", sort: (r) => r.status, render: (r) => <Badge value={r.status} /> },
    { key: "voucher", label: "Voucher", sort: (r) => (r.voucher_document_id ? 1 : 0), render: (r) => (r.voucher_document_id ? <FileCheck2 className="h-4 w-4 text-ab-success" aria-label={t("Voucher attached")} /> : <span className="text-xs text-ab-faint">{t("None")}</span>) },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Commissions and their vouchers"
        subtitle="Each sale or rental commission with its agreed amount, approval, release and supporting commission voucher. ALTY doesn't assume any commission rate: amounts are entered as agreed, or suggested by a structure management sets up."
        actions={canManage && <Button variant="primary" onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> {t("New commission")}</Button>}
      />
      <div role="tablist" aria-label={t("Commissions view")} className="flex w-fit rounded-xl border border-ab-border bg-ab-card p-1">
        {([["records", "Commission records"], ["structures", "Commission structures"]] as const).map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={view === key} onClick={() => setView(key)}
            className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${view === key ? "bg-ab-accent text-ab-ink" : "text-ab-muted hover:text-ab-text"}`}>{t(label)}</button>
        ))}
      </div>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {summary && view === "records" && (
        <>
          <Tiles items={[
            { label: "Waiting for approval", value: summary.pending_approval.count, detail: pesoShort(summary.pending_approval.amount), onClick: () => setState(state === "PENDING" ? "" : "PENDING"), active: state === "PENDING" },
            { label: "Approved, not yet released", value: summary.approved_unreleased.count, detail: pesoShort(summary.approved_unreleased.amount), onClick: () => setState(state === "UNRELEASED" ? "" : "UNRELEASED"), active: state === "UNRELEASED" },
            { label: "Released", value: summary.released.count, detail: pesoShort(summary.released.amount), onClick: () => setState(state === "RELEASED" ? "" : "RELEASED"), active: state === "RELEASED" },
            { label: "Without a voucher", value: summary.without_voucher, onClick: () => setState(state === "NO_VOUCHER" ? "" : "NO_VOUCHER"), active: state === "NO_VOUCHER" },
          ]} />
          <div className="flex flex-wrap gap-2 sm:flex-nowrap">
            <div className="w-full sm:w-auto sm:flex-1"><SearchBox value={search} onChange={setSearch} placeholder="Search seller, property, buyer, lessor or reference" /></div>
            <Select label="Kind" value={kind} onChange={setKind} options={[{ value: "", label: "Sales and rentals" }, { value: "SALE", label: "Sales" }, { value: "RENTAL", label: "Rentals" }]} />
          </div>
          <DataTable exportTitle="Commission records" rows={shown} columns={columns} rowKey={(r) => String(r.id)} onOpen={(r) => open(String(r.id))}
            empty={rows.length ? "No commissions match these filters." : "No commissions recorded yet."} initialSort={{ key: "date", dir: "desc" }} />
        </>
      )}
      {structures && view === "structures" && <Structures structures={structures} canManage={canManage} onChanged={() => void reload()} />}
      {selected && summary && <RecordDrawer record={selected} canManage={canManage} onClose={close} onChanged={() => void reload()} />}
      {creating && structures && <RecordForm structures={structures} onClose={() => setCreating(false)} onSaved={(r) => { setCreating(false); void reload().then(() => open(String(r.id))) }} />}
    </div>
  )
}

function RecordDrawer({ record: r, canManage, onClose, onChanged }: { record: Record_; canManage: boolean; onClose: () => void; onChanged: () => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [dialog, setDialog] = useState<"reject" | "release" | "voucher" | null>(null)
  const run = async (request: Promise<unknown>, done: string) => {
    setBusy(true)
    try {
      await request
      toast(done)
      setDialog(null)
      onChanged()
    } catch (actionError) {
      toast(t((actionError as Error).message), "error")
    } finally {
      setBusy(false)
    }
  }
  const open_ = r.status !== "RELEASED" && r.status !== "CANCELLED"
  return (
    <Drawer title={`${t(r.kind === "RENTAL" ? "Rental commission" : "Sale commission")} · ${peso(r.amount)}`}
      subtitle={<span className="flex flex-wrap items-center gap-2"><Badge value={r.status} /> <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${APPROVAL_TONE[r.approval_status] ?? ""}`}>{statusLabel(r.approval_status)}</span></span>}
      onClose={onClose}
      footer={(
        <>
          <Button onClick={() => setDialog("voucher")}><FileCheck2 className="h-4 w-4" /> {t(r.voucher ? "Change voucher" : "Attach voucher")}</Button>
          {canManage && open_ && r.approval_status !== "APPROVED" && (
            <>
              <Button variant="danger" onClick={() => setDialog("reject")}>{t("Reject")}</Button>
              <Button variant="primary" disabled={busy} onClick={() => void run(api(`/commissions/${r.id}/approval`, { method: "POST", body: JSON.stringify({ decision: "APPROVED" }) }), t("Commission approved."))}><BadgeCheck className="h-4 w-4" /> {t("Approve")}</Button>
            </>
          )}
          {canManage && open_ && r.approval_status === "APPROVED" && <Button variant="primary" onClick={() => setDialog("release")}>{t("Record release")}</Button>}
        </>
      )}>
      <Section title="Commission">
        <Facts items={[
          ["Seller", r.agent_id ? <Link to={`/manage/agents?id=${r.agent_id}`} className="hover:underline">{text(r.seller_name)}</Link> : null],
          ["Property", r.listing_id ? <Link to={`/manage/properties?id=${r.listing_id}`} className="hover:underline">{describe(r)}</Link> : describe(r)],
          ["Project", r.project_name],
          ["Sale", r.transaction_id ? <Link to={`/manage/transactions?id=${r.transaction_id}`} className="hover:underline">{t("{buyer} · {d}", { buyer: r.buyer_name ?? "—", d: date(r.transaction_date) })}</Link> : null],
          ["Lessor", r.lessor_name],
          ["Lessee", r.lessee_name],
          ["Monthly rent", r.monthly_rent ? peso(r.monthly_rent) : null],
          ["Lease term", r.lease_term_months ? t("{n} month(s)", { n: r.lease_term_months }) : null],
          ["Based on", r.basis_amount ? peso(r.basis_amount) : null],
          ["Rate", r.rate_percent != null ? `${r.rate_percent}%` : null],
          ["Commission", peso(r.amount)],
          ["Seller's share", r.seller_share_amount != null ? peso(r.seller_share_amount) : null],
          ["Agreement", [r.agreement_reference, r.agreement_notes].filter(Boolean).join(" · ") || null],
        ]} />
      </Section>
      <Section title="Approval and release">
        <Facts items={[
          ["Approval", `${statusLabel(r.approval_status)}${r.approved_by ? ` · ${r.approved_by}, ${dateTime(r.approved_at)}` : ""}`],
          ["Approval note", r.approval_note],
          ["Released", r.released_amount ? `${peso(r.released_amount)} · ${date(r.released_on)}` : null],
          ["Recorded by", r.created_by ? `${r.created_by} · ${date(r.record_date)}` : null],
        ]} />
      </Section>
      <Section title="Commission voucher">
        {r.voucher ? (
          <p className="text-sm"><Link to={`/manage/documents?id=${r.voucher.document_id}`} className="font-semibold text-ab-accent hover:underline">{r.voucher.name}</Link></p>
        ) : <p className="text-sm italic text-ab-faint">{t("No voucher attached yet. Upload it in the Document Repository as a Commission Voucher, then attach it here.")}</p>}
      </Section>
      {dialog === "reject" && <NoteDialog title={t("Reject commission")} label={t("Reason *")} busy={busy} onClose={() => setDialog(null)}
        onConfirm={(note) => void run(api(`/commissions/${r.id}/approval`, { method: "POST", body: JSON.stringify({ decision: "REJECTED", note }) }), t("Commission rejected."))} />}
      {dialog === "release" && <ReleaseDialog record={r} busy={busy} onClose={() => setDialog(null)}
        onConfirm={(body) => void run(api(`/commissions/${r.id}/release`, { method: "POST", body: JSON.stringify(body) }), t("Release recorded."))} />}
      {dialog === "voucher" && <VoucherDialog record={r} busy={busy} onClose={() => setDialog(null)}
        onConfirm={(documentId) => void run(api(`/commissions/${r.id}/voucher`, { method: "PUT", body: JSON.stringify({ document_id: documentId }) }), t("Voucher saved."))} />}
    </Drawer>
  )
}

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

function NoteDialog({ title, label, busy, onClose, onConfirm }: { title: string; label: string; busy: boolean; onClose: () => void; onConfirm: (note: string) => void }) {
  const [note, setNote] = useState("")
  const [error, setError] = useState("")
  return (
    <Modal title={title} onClose={onClose} onSubmit={(e) => { e.preventDefault(); if (!note.trim()) return setError(t("Enter the reason.")); onConfirm(note.trim()) }}
      footer={<><Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button><Button type="submit" variant="danger" disabled={busy}>{t("Confirm")}</Button></>}>
      <div className="p-5"><label className="block text-sm font-medium">{label}<textarea className={`${field} min-h-24`} value={note} onChange={(e) => setNote(e.target.value)} /></label>
        {error && <p role="alert" className="mt-2 text-sm text-ab-danger">{error}</p>}</div>
    </Modal>
  )
}

function ReleaseDialog({ record, busy, onClose, onConfirm }: { record: Record_; busy: boolean; onClose: () => void; onConfirm: (body: { released_on: string; amount: string | null }) => void }) {
  const remaining = record.amount - (record.released_amount ?? 0)
  const [day, setDay] = useState(new Date().toISOString().slice(0, 10))
  const [amount, setAmount] = useState(String(remaining))
  return (
    <Modal title={t("Record release")} onClose={onClose} onSubmit={(e) => { e.preventDefault(); onConfirm({ released_on: day, amount: amount || null }) }}
      footer={<><Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button><Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Save")}</Button></>}>
      <div className="grid gap-3 p-5 sm:grid-cols-2">
        <label className="text-sm font-medium">{t("Release date")}<input type="date" className={field} value={day} onChange={(e) => setDay(e.target.value)} /></label>
        <label className="text-sm font-medium">{t("Amount released")}<input className={field} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
        <p className="text-xs text-ab-faint sm:col-span-2">{t("Still unpaid: {v}.", { v: peso(remaining) })}</p>
      </div>
    </Modal>
  )
}

function VoucherDialog({ record, busy, onClose, onConfirm }: { record: Record_; busy: boolean; onClose: () => void; onConfirm: (documentId: number | null) => void }) {
  const { api } = useStaffAuth()
  const load = useCallback(() => api<{ id: number; document_id: string; document_name: string; document_type: string; created_at: string }[]>("/documents?limit=500"), [api])
  const docs = useApiData(load)
  const vouchers = (docs.data ?? []).filter((d) => ["COMMISSION_VOUCHER", "VOUCHER"].includes(d.document_type))
  const [pick, setPick] = useState(record.voucher_document_id ? String(record.voucher_document_id) : "")
  return (
    <Modal title={t("Commission voucher")} onClose={onClose} onSubmit={(e) => { e.preventDefault(); onConfirm(pick ? Number(pick) : null) }}
      footer={<><Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button><Button type="submit" variant="primary" disabled={busy}>{t("Save")}</Button></>}>
      <div className="space-y-2 p-5">
        <LoadState loading={docs.loading && !docs.data} error={docs.error} onRetry={docs.reload} />
        <label className="block text-sm font-medium">{t("Voucher document")}
          <select className={field} value={pick} onChange={(e) => setPick(e.target.value)}>
            <option value="">{t("No voucher")}</option>
            {vouchers.map((d) => <option key={d.id} value={d.id}>{d.document_name} · {date(d.created_at)}</option>)}
          </select>
        </label>
        <p className="text-xs text-ab-faint">{t("Only documents uploaded as Commission Voucher (or Voucher) are listed.")}</p>
      </div>
    </Modal>
  )
}

function RecordForm({ structures, onClose, onSaved }: { structures: Structure[]; onClose: () => void; onSaved: (r: Record_) => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const loadOptions = useCallback(() => Promise.all([
    api<{ transaction_id: string; transaction_type: string; status: string; client_name: string | null; property_title: string | null; agent_name: string | null; amount: number; transaction_date: string }[]>("/transactions?limit=2000"),
    api<{ agent_id: string; full_name: string; status: string }[]>("/agents"),
  ]), [api])
  const options = useApiData(loadOptions)
  const [txs, sellers] = options.data ?? [[], []]
  const sales = txs.filter((tx) => tx.transaction_type === "SOLD" && tx.status !== "CANCELLED")
  const [form, setForm] = useState({ kind: "SALE", transaction_id: "", agent_id: "", property_description: "", lessor_name: "", lessee_name: "", monthly_rent: "", lease_term_months: "",
    basis_amount: "", structure_id: "", amount: "", seller_share_amount: "", agreement_reference: "", agreement_notes: "" })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [suggested, setSuggested] = useState<string | null>(null)
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value }))
  const sale = sales.find((tx) => tx.transaction_id === form.transaction_id)
  const usable = structures.filter((s) => s.is_active && s.kind === form.kind)
  const suggest = async (structureId: string) => {
    setForm((f) => ({ ...f, structure_id: structureId }))
    setSuggested(null)
    if (!structureId) return
    try {
      const result = await api<{ amount: number | null; seller_share_amount: number | null }>("/commissions/preview", { method: "POST",
        body: JSON.stringify({ structure_id: Number(structureId), basis_amount: form.basis_amount || (sale ? String(sale.amount) : null), monthly_rent: form.monthly_rent || null }) })
      if (result.amount != null) {
        setSuggested(peso(result.amount))
        setForm((f) => ({ ...f, amount: String(result.amount), seller_share_amount: result.seller_share_amount != null ? String(result.seller_share_amount) : f.seller_share_amount }))
      }
    } catch { /* the amount stays as typed */ }
  }
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (form.kind === "SALE" && !form.transaction_id) return setError(t("Choose the sale this commission is for."))
    if (form.kind === "RENTAL" && !form.property_description.trim()) return setError(t("Describe the rented property."))
    if (!form.amount && !form.structure_id) return setError(t("Enter the agreed commission amount."))
    setBusy(true)
    setError("")
    const body: Record<string, unknown> = { kind: form.kind }
    for (const [key, value] of Object.entries(form)) if (key !== "kind" && value !== "") body[key] = key === "structure_id" || key === "lease_term_months" ? Number(value) : value
    try {
      const saved = await api<Record_>("/commissions", { method: "POST", body: JSON.stringify(body) })
      toast(t("Commission recorded."))
      onSaved(saved)
    } catch (saveError) {
      setError(t((saveError as Error).message))
      setBusy(false)
    }
  }
  return (
    <Modal title={t("New commission")} onClose={onClose} onSubmit={submit}
      footer={<><Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button><Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Record commission")}</Button></>}>
      <div className="grid gap-3 p-5 sm:grid-cols-2">
        <fieldset className="sm:col-span-2">
          <legend className="text-sm font-medium">{t("Commission for")}</legend>
          <div className="mt-1 flex gap-2">
            {(["SALE", "RENTAL"] as const).map((k) => (
              <label key={k} className={`flex min-h-10 flex-1 cursor-pointer items-center justify-center rounded-xl border px-3 text-sm font-semibold ${form.kind === k ? "border-ab-accent bg-ab-accent-soft text-ab-accent" : "border-ab-border"}`}>
                <input type="radio" name="kind" className="sr-only" checked={form.kind === k} onChange={() => setForm((f) => ({ ...f, kind: k, structure_id: "" }))} />{t(k === "SALE" ? "A sale" : "A rental")}
              </label>
            ))}
          </div>
        </fieldset>
        <LoadState loading={options.loading && !options.data} error={options.error} onRetry={options.reload} />
        {form.kind === "SALE" ? (
          <label className="text-sm font-medium sm:col-span-2">{t("Sale *")}
            <select className={field} value={form.transaction_id} onChange={set("transaction_id")}>
              <option value="">{t("Choose a recorded sale…")}</option>
              {sales.map((tx) => <option key={tx.transaction_id} value={tx.transaction_id}>{[date(tx.transaction_date), tx.property_title, tx.client_name, tx.agent_name, peso(tx.amount)].filter(Boolean).join(" · ")}</option>)}
            </select>
          </label>
        ) : (
          <>
            <label className="text-sm font-medium">{t("Seller")}
              <select className={field} value={form.agent_id} onChange={set("agent_id")}>
                <option value="">{t("Not set")}</option>
                {sellers.filter((s) => s.status === "ACTIVE").map((s) => <option key={s.agent_id} value={s.agent_id}>{s.full_name}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium">{t("Rented property *")}<input className={field} value={form.property_description} onChange={set("property_description")} /></label>
            <label className="text-sm font-medium">{t("Lessor")}<input className={field} value={form.lessor_name} onChange={set("lessor_name")} /></label>
            <label className="text-sm font-medium">{t("Lessee")}<input className={field} value={form.lessee_name} onChange={set("lessee_name")} /></label>
            <label className="text-sm font-medium">{t("Monthly rent")}<input className={field} inputMode="decimal" value={form.monthly_rent} onChange={set("monthly_rent")} /></label>
            <label className="text-sm font-medium">{t("Lease term (months)")}<input className={field} inputMode="numeric" value={form.lease_term_months} onChange={set("lease_term_months")} /></label>
          </>
        )}
        <label className="text-sm font-medium sm:col-span-2">{t("Commission structure (optional)")}
          <select className={field} value={form.structure_id} onChange={(e) => void suggest(e.target.value)}>
            <option value="">{t("None: enter the agreed amount")}</option>
            {usable.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          {suggested && <span className="mt-1 block text-xs font-normal text-ab-faint">{t("Suggested by the structure: {v}. You can change it.", { v: suggested })}</span>}
        </label>
        <label className="text-sm font-medium">{t("Commission amount *")}<input className={field} inputMode="decimal" value={form.amount} onChange={set("amount")} /></label>
        <label className="text-sm font-medium">{t("Seller's share (if agreed)")}<input className={field} inputMode="decimal" value={form.seller_share_amount} onChange={set("seller_share_amount")} /></label>
        <label className="text-sm font-medium">{t("Agreement reference")}<input className={field} value={form.agreement_reference} onChange={set("agreement_reference")} /></label>
        <label className="text-sm font-medium sm:col-span-2">{t("Commission agreement")}<textarea className={`${field} min-h-16`} value={form.agreement_notes} onChange={set("agreement_notes")} placeholder={t("e.g. what was agreed with the developer or lessor")} /></label>
        {error && <p role="alert" className="text-sm text-ab-danger sm:col-span-2">{error}</p>}
      </div>
    </Modal>
  )
}

function Structures({ structures, canManage, onChanged }: { structures: Structure[]; canManage: boolean; onChanged: () => void }) {
  const [editing, setEditing] = useState<Structure | "new" | null>(null)
  const columns: Column<Structure>[] = [
    { key: "name", label: "Structure", sort: (s) => s.name, render: (s) => <span className="font-semibold">{s.name}</span> },
    { key: "kind", label: "For", sort: (s) => s.kind, render: (s) => t(s.kind === "RENTAL" ? "Rentals" : "Sales") },
    { key: "applies", label: "Applies to", sort: (s) => s.partner_name ?? "", render: (s) => s.partner_name ?? (s.listing_id ? t("Listing #{id}", { id: s.listing_id }) : t("Any")) },
    { key: "basis", label: "Basis", sort: (s) => s.basis, render: (s) => `${t(BASIS[s.basis] ?? s.basis)}${s.rate_percent != null ? ` · ${s.rate_percent}%` : ""}${s.fixed_amount != null ? ` · ${peso(s.fixed_amount)}` : ""}${s.months_of_rent != null ? ` · ${s.months_of_rent}` : ""}` },
    { key: "share", label: "Seller's share", sort: (s) => s.seller_share_percent ?? -1, render: (s) => (s.seller_share_percent != null ? `${s.seller_share_percent}%` : "—"), hideOnPhone: true },
    { key: "active", label: "Status", sort: (s) => (s.is_active ? 1 : 0), render: (s) => <Badge value={s.is_active ? "ACTIVE" : "INACTIVE"} /> },
  ]
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="max-w-3xl text-sm text-ab-muted">{t("Optional. Set up a structure only for an arrangement Abellar Realty has confirmed (for example a developer's commission terms). It suggests the amount on new records; nothing is applied automatically.")}</p>
        {canManage && <Button onClick={() => setEditing("new")}><Plus className="h-4 w-4" /> {t("New structure")}</Button>}
      </div>
      <DataTable rows={structures} columns={columns} rowKey={(s) => String(s.id)} onOpen={canManage ? (s) => setEditing(s) : undefined}
        empty="No commission structures yet." initialSort={{ key: "name", dir: "asc" }} />
      {editing && <StructureForm structure={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); onChanged() }} />}
    </div>
  )
}

function StructureForm({ structure, onClose, onSaved }: { structure: Structure | null; onClose: () => void; onSaved: () => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const loadPartners = useCallback(() => api<{ id: number; name: string; partner_type: string | null }[]>("/partners"), [api])
  const partners = (useApiData(loadPartners, "partner-options").data ?? []).filter((p) => p.partner_type === "DEVELOPER")
  const [form, setForm] = useState({
    name: structure?.name ?? "", kind: structure?.kind ?? "SALE", partner_id: structure?.partner_id ? String(structure.partner_id) : "", basis: structure?.basis ?? "AS_AGREED",
    rate_percent: structure?.rate_percent != null ? String(structure.rate_percent) : "", fixed_amount: structure?.fixed_amount != null ? String(structure.fixed_amount) : "",
    months_of_rent: structure?.months_of_rent != null ? String(structure.months_of_rent) : "", seller_share_percent: structure?.seller_share_percent != null ? String(structure.seller_share_percent) : "",
    effective_from: structure?.effective_from ?? "", effective_until: structure?.effective_until ?? "", is_active: structure?.is_active ?? true, notes: structure?.notes ?? "",
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value }))
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!form.name.trim()) return setError(t("Name the structure."))
    setBusy(true)
    const body = { ...form, partner_id: form.partner_id ? Number(form.partner_id) : null,
      rate_percent: form.basis === "PERCENT_OF_PRICE" && form.rate_percent ? form.rate_percent : null,
      fixed_amount: form.basis === "FIXED_AMOUNT" && form.fixed_amount ? form.fixed_amount : null,
      months_of_rent: form.basis === "MONTHS_OF_RENT" && form.months_of_rent ? form.months_of_rent : null,
      seller_share_percent: form.seller_share_percent || null, effective_from: form.effective_from || null, effective_until: form.effective_until || null, notes: form.notes || null }
    try {
      await api(structure ? `/commissions/structures/${structure.id}` : "/commissions/structures", { method: structure ? "PUT" : "POST", body: JSON.stringify(body) })
      toast(t("Saved {name}.", { name: form.name }))
      onSaved()
    } catch (saveError) {
      setError(t((saveError as Error).message))
      setBusy(false)
    }
  }
  return (
    <Modal title={structure ? t("Edit {name}", { name: structure.name }) : t("New structure")} onClose={onClose} onSubmit={submit}
      footer={<><Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button><Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Save")}</Button></>}>
      <div className="grid gap-3 p-5 sm:grid-cols-2">
        <label className="text-sm font-medium sm:col-span-2">{t("Name *")}<input className={field} value={form.name} onChange={set("name")} /></label>
        <label className="text-sm font-medium">{t("For")}<select className={field} value={form.kind} onChange={set("kind")}><option value="SALE">{t("Sales")}</option><option value="RENTAL">{t("Rentals")}</option></select></label>
        <label className="text-sm font-medium">{t("Developer")}<select className={field} value={form.partner_id} onChange={set("partner_id")}><option value="">{t("Any")}</option>{partners.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        <label className="text-sm font-medium">{t("Basis")}<select className={field} value={form.basis} onChange={set("basis")}>{Object.entries(BASIS).map(([k, label]) => <option key={k} value={k}>{t(label)}</option>)}</select></label>
        {form.basis === "PERCENT_OF_PRICE" && <label className="text-sm font-medium">{t("Rate (%)")}<input className={field} inputMode="decimal" value={form.rate_percent} onChange={set("rate_percent")} /></label>}
        {form.basis === "FIXED_AMOUNT" && <label className="text-sm font-medium">{t("Amount")}<input className={field} inputMode="decimal" value={form.fixed_amount} onChange={set("fixed_amount")} /></label>}
        {form.basis === "MONTHS_OF_RENT" && <label className="text-sm font-medium">{t("Months of rent")}<input className={field} inputMode="decimal" value={form.months_of_rent} onChange={set("months_of_rent")} /></label>}
        <label className="text-sm font-medium">{t("Seller's share (%) (if defined)")}<input className={field} inputMode="decimal" value={form.seller_share_percent} onChange={set("seller_share_percent")} /></label>
        <label className="text-sm font-medium">{t("Effective from")}<input type="date" className={field} value={form.effective_from} onChange={set("effective_from")} /></label>
        <label className="text-sm font-medium">{t("Effective until")}<input type="date" className={field} value={form.effective_until} onChange={set("effective_until")} /></label>
        <label className="flex items-center gap-2 text-sm font-medium sm:col-span-2"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))} className="h-4 w-4 accent-[var(--color-ab-accent)]" />{t("Active (offered on new commission records)")}</label>
        <label className="text-sm font-medium sm:col-span-2">{t("Notes")}<textarea className={`${field} min-h-16`} value={form.notes} onChange={set("notes")} /></label>
        {error && <p role="alert" className="text-sm text-ab-danger sm:col-span-2">{error}</p>}
      </div>
    </Modal>
  )
}

/** The seller's own commissions, when management shares them. */
export function SellerCommissionsPage() {
  const { api } = useStaffAuth()
  const load = useCallback(() => api<Record_[]>("/seller/commissions"), [api])
  const { data, error, loading, reload } = useApiData(load, "seller-commissions")
  const columns: Column<Record_>[] = [
    { key: "date", label: "Date", sort: (r) => r.transaction_date ?? r.record_date, render: (r) => date(r.transaction_date ?? r.record_date) },
    { key: "property", label: "Property", sort: (r) => describe(r), render: (r) => describe(r) },
    { key: "amount", label: "Commission", align: "right", sort: (r) => r.amount, render: (r) => peso(r.amount) },
    { key: "share", label: "Your share", align: "right", sort: (r) => r.seller_share_amount ?? 0, render: (r) => (r.seller_share_amount != null ? peso(r.seller_share_amount) : "—") },
    { key: "status", label: "Release", sort: (r) => r.status, render: (r) => <Badge value={r.status} /> },
  ]
  const blocked = error && /aren't shared/.test(error)
  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <PageHeader title="Your commissions" subtitle="Your own commission records, when Abellar Realty's management shares them with you." />
      {blocked ? (
        <div className="rounded-2xl border border-dashed border-ab-border bg-ab-card p-6 text-center text-sm text-ab-muted">{t("Your commission records aren't shared with you yet. Ask Abellar Realty's management.")}</div>
      ) : (
        <>
          <LoadState loading={loading && !data} error={error} onRetry={reload} />
          {data && <DataTable rows={data} columns={columns} rowKey={(r) => String(r.id)} empty="No commission records yet." initialSort={{ key: "date", dir: "desc" }} />}
        </>
      )}
    </div>
  )
}
