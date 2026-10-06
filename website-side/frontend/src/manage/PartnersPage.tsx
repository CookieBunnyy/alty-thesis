import { useCallback, useMemo, useState, type FormEvent } from "react"
import { Building2, ExternalLink, LoaderCircle, Mail, Pencil, Phone, Plus, Trash2, X } from "lucide-react"
import { Link } from "@/components/Link"
import { categoryLabel } from "@/lib/categories"
import { contains, dateTime, isManagement, peso, pesoShort, text } from "./format"
import { Badge, Button, Confirm, DataTable, Drawer, Facts, LoadState, PageHeader, SearchBox, Section, Select, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData, useOpenRecord } from "./useApiData"

export type Partner = {
  id: number; name: string; partner_type: string | null; status: string
  contact_person: string | null; email: string | null; phone_number: string | null; website: string | null; address: string | null; notes: string | null
  created_at: string; updated_at: string
  listings: number; available_listings: number; transactions: number; completed_sales: number; sales_value: number
}
type PartnerDetail = Partner & { listing_rows: { listing_id: number; title: string | null; category: string | null; status: string; price_total: number | null; village_name: string | null }[] }

const TYPES: Record<string, string> = { DEVELOPER: "Developer", BROKERAGE: "Brokerage", BANK: "Bank / Financing", CONTRACTOR: "Contractor", OTHER: "Other partner" }
const typeLabel = (t: string | null) => (t ? TYPES[t] ?? t : "Type not set")

export function PartnersPage() {
  const { api, user } = useStaffAuth()
  const { id, open, close } = useOpenRecord()
  const canManage = isManagement(user?.role)
  const [search, setSearch] = useState("")
  const [type, setType] = useState("")
  const [status, setStatus] = useState("")
  const [editing, setEditing] = useState<Partner | "new" | null>(null)
  const load = useCallback(() => api<Partner[]>("/partners"), [api])
  const { data, error, loading, reload } = useApiData(load)
  const partners = useMemo(() => data ?? [], [data])
  const shown = partners.filter((p) => (!type || (type === "NONE" ? !p.partner_type : p.partner_type === type)) && (!status || p.status === status) &&
    contains([p.name, p.contact_person, p.email, p.phone_number, p.address, typeLabel(p.partner_type)], search))
  const selected = id ? partners.find((p) => String(p.id) === id) ?? null : null

  const columns: Column<Partner>[] = [
    {
      key: "name", label: "Partner", sort: (p) => p.name.toLowerCase(),
      render: (p) => (
        <span className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-ab-accent-soft text-ab-accent"><Building2 className="h-4 w-4" /></span>
          <span className="min-w-0">
            <span className="block truncate font-semibold">{p.name}</span>
            <span className="block truncate text-xs text-ab-faint">{typeLabel(p.partner_type)}{p.contact_person ? ` · ${p.contact_person}` : ""}</span>
          </span>
        </span>
      ),
    },
    { key: "contact", label: "Contact", sort: (p) => p.phone_number ?? p.email ?? "", render: (p) => text(p.phone_number ?? p.email), hideOnPhone: true },
    { key: "listings", label: "Listings", align: "right", sort: (p) => p.listings, render: (p) => (p.listings ? `${p.listings} (${p.available_listings} available)` : "0") },
    { key: "sales", label: "Completed sales", align: "right", sort: (p) => p.completed_sales, render: (p) => p.completed_sales, hideOnPhone: true },
    { key: "value", label: "Sales value", align: "right", sort: (p) => p.sales_value, render: (p) => (p.sales_value ? pesoShort(p.sales_value) : "—") },
    { key: "status", label: "Status", sort: (p) => p.status, render: (p) => <Badge value={p.status} /> },
  ]

  const unset = partners.filter((p) => !p.partner_type).length
  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Partners / Developers"
        subtitle="Developers and partner companies Abellar Realty works with. Link a listing to its developer from the Properties page."
        actions={canManage && <Button variant="primary" onClick={() => setEditing("new")}><Plus className="h-4 w-4" /> New partner</Button>}
      />
      {data && (
        <Tiles items={[
          { label: "Partners", value: partners.length, onClick: () => setStatus(""), active: !status },
          { label: "Active", value: partners.filter((p) => p.status === "ACTIVE").length, onClick: () => setStatus(status === "ACTIVE" ? "" : "ACTIVE"), active: status === "ACTIVE" },
          { label: "Developers", value: partners.filter((p) => p.partner_type === "DEVELOPER").length, onClick: () => setType(type === "DEVELOPER" ? "" : "DEVELOPER"), active: type === "DEVELOPER" },
          { label: "With listings", value: partners.filter((p) => p.listings > 0).length },
          { label: "Details missing", value: unset, detail: unset ? "Type not set yet" : "All typed", onClick: unset ? () => setType(type === "NONE" ? "" : "NONE") : undefined, active: type === "NONE" },
        ]} />
      )}
      <div className="flex flex-wrap gap-2 sm:flex-nowrap">
        <div className="w-full sm:w-auto sm:flex-1"><SearchBox value={search} onChange={setSearch} placeholder="Search name, contact, phone or address" /></div>
        <Select label="Type" value={type} onChange={setType} options={[{ value: "", label: "All types" }, ...Object.entries(TYPES).map(([value, label]) => ({ value, label })), { value: "NONE", label: "Type not set" }]} />
        <Select label="Status" value={status} onChange={setStatus} options={[{ value: "", label: "Any status" }, { value: "ACTIVE", label: "Active" }, { value: "INACTIVE", label: "Inactive" }]} />
      </div>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <>
          <p className="text-xs text-ab-faint">{shown.length} of {partners.length} partners</p>
          <DataTable rows={shown} columns={columns} rowKey={(p) => String(p.id)} onOpen={(p) => open(String(p.id))} empty="No partners match these filters." initialSort={{ key: "name", dir: "asc" }} />
        </>
      )}
      {selected && <PartnerDrawer partner={selected} canManage={canManage} onClose={close} onEdit={() => setEditing(selected)} onDeleted={() => { close(); void reload() }} />}
      {editing && (
        <PartnerForm partner={editing === "new" ? null : editing} onClose={() => setEditing(null)}
          onSaved={(p) => { setEditing(null); void reload().then(() => open(String(p.id))) }} />
      )}
    </div>
  )
}

function PartnerDrawer({ partner, canManage, onClose, onEdit, onDeleted }: { partner: Partner; canManage: boolean; onClose: () => void; onEdit: () => void; onDeleted: () => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const loadDetail = useCallback(() => api<PartnerDetail>(`/partners/${partner.id}`), [api, partner.id])
  const detail = useApiData(loadDetail)
  const remove = async () => {
    setBusy(true)
    try {
      await api(`/partners/${partner.id}`, { method: "DELETE" })
      toast(`Deleted ${partner.name}.`)
      onDeleted()
    } catch (deleteError) {
      toast((deleteError as Error).message, "error")
      setBusy(false)
      setConfirm(false)
    }
  }
  return (
    <Drawer
      title={partner.name}
      subtitle={<span className="flex items-center gap-2"><Badge value={partner.status} /> {typeLabel(partner.partner_type)}</span>}
      onClose={onClose}
      footer={canManage && (
        <>
          <Button variant="danger" onClick={() => setConfirm(true)}><Trash2 className="h-4 w-4" /> Delete</Button>
          <Button variant="primary" onClick={onEdit}><Pencil className="h-4 w-4" /> Edit</Button>
        </>
      )}
    >
      <div className="flex flex-wrap gap-2 text-sm">
        {partner.phone_number && <a href={`tel:${partner.phone_number.replace(/[^\d+]/g, "")}`} className="inline-flex items-center gap-1.5 rounded-full border border-ab-border bg-ab-card px-3 py-1 hover:border-ab-accent"><Phone className="h-3.5 w-3.5 text-ab-accent" />{partner.phone_number}</a>}
        {partner.email && <a href={`mailto:${partner.email}`} className="inline-flex items-center gap-1.5 rounded-full border border-ab-border bg-ab-card px-3 py-1 hover:border-ab-accent"><Mail className="h-3.5 w-3.5 text-ab-accent" />{partner.email}</a>}
        {partner.website && <a href={partner.website} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-full border border-ab-border bg-ab-card px-3 py-1 hover:border-ab-accent"><ExternalLink className="h-3.5 w-3.5 text-ab-accent" />Website</a>}
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {([["Listings", partner.listings], ["Available", partner.available_listings], ["Completed sales", partner.completed_sales], ["Sales value", partner.sales_value ? peso(partner.sales_value) : "—"]] as const).map(([label, value]) => (
          <div key={label} className="rounded-xl border border-ab-border bg-ab-card p-3"><p className="text-[11px] text-ab-faint">{label}</p><p className="mt-0.5 font-bold tabular-nums">{value}</p></div>
        ))}
      </div>
      <Section title="Details">
        <Facts items={[
          ["Type", partner.partner_type ? typeLabel(partner.partner_type) : null],
          ["Contact person", partner.contact_person],
          ["Phone", partner.phone_number],
          ["Email", partner.email],
          ["Website", partner.website],
          ["Address", partner.address],
          ["Notes", partner.notes],
          ["Last updated", dateTime(partner.updated_at)],
        ]} />
      </Section>
      <Section title="Listings by this partner">
        <LoadState loading={detail.loading} error={detail.error} onRetry={detail.reload} />
        {detail.data && (detail.data.listing_rows.length === 0 ? (
          <p className="text-sm italic text-ab-faint">No listings linked yet. Open a property and choose this partner as its developer.</p>
        ) : (
          <ul className="space-y-2">
            {detail.data.listing_rows.map((l) => (
              <li key={l.listing_id} className="flex items-center justify-between gap-2 rounded-xl border border-ab-border p-3 text-sm">
                <span className="min-w-0">
                  <Link to={`/manage/properties?id=${l.listing_id}`} className="block truncate font-semibold hover:underline">{l.title ?? `#${l.listing_id}`}</Link>
                  <span className="text-xs text-ab-faint">{categoryLabel(l.category)} · {text(l.village_name)} · {peso(l.price_total)}</span>
                </span>
                <Badge value={l.status} />
              </li>
            ))}
          </ul>
        ))}
      </Section>
      {confirm && (
        <Confirm title="Delete partner?" confirmLabel="Delete" busy={busy} onConfirm={remove} onCancel={() => setConfirm(false)}
          message={<>Delete {partner.name}? Partners linked to listings can't be deleted — mark them <strong>Inactive</strong> instead.</>} />
      )}
    </Drawer>
  )
}

const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"

function PartnerForm({ partner, onClose, onSaved }: { partner: Partner | null; onClose: () => void; onSaved: (p: Partner) => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const [form, setForm] = useState({
    name: partner?.name ?? "", partner_type: partner?.partner_type ?? "", status: partner?.status ?? "ACTIVE",
    contact_person: partner?.contact_person ?? "", phone_number: partner?.phone_number ?? "", email: partner?.email ?? "",
    website: partner?.website ?? "", address: partner?.address ?? "", notes: partner?.notes ?? "",
  })
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value }))
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!form.name.trim()) return setError("Enter the partner's name.")
    setBusy(true)
    setError("")
    try {
      const body = JSON.stringify({ ...form, partner_type: form.partner_type || null })
      const saved = partner
        ? await api<Partner>(`/partners/${partner.id}`, { method: "PUT", body })
        : await api<Partner>("/partners", { method: "POST", body })
      toast(`${partner ? "Saved" : "Added"} ${saved.name}.`)
      onSaved(saved)
    } catch (saveError) {
      setError((saveError as Error).message)
      setBusy(false)
    }
  }
  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={partner ? "Edit partner" : "New partner"}>
      <button type="button" aria-label="Cancel" className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={submit} noValidate className="ab-pop relative flex max-h-[94dvh] w-full max-w-2xl flex-col rounded-t-2xl border border-ab-border bg-ab-card shadow-2xl sm:rounded-2xl">
        <header className="flex items-center justify-between border-b border-ab-border px-5 py-4">
          <h2 className="text-lg font-bold">{partner ? `Edit ${partner.name}` : "New partner"}</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><X className="h-4 w-4" /></button>
        </header>
        <div className="grid gap-3 overflow-y-auto p-5 sm:grid-cols-2">
          <label className="text-sm font-medium sm:col-span-2">Name *<input className={field} value={form.name} onChange={set("name")} /></label>
          <label className="text-sm font-medium">Type
            <select className={field} value={form.partner_type} onChange={set("partner_type")}>
              <option value="">Not set</option>
              {Object.entries(TYPES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium">Status
            <select className={field} value={form.status} onChange={set("status")}><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option></select>
          </label>
          <label className="text-sm font-medium">Contact person<input className={field} value={form.contact_person} onChange={set("contact_person")} /></label>
          <label className="text-sm font-medium">Phone<input className={field} value={form.phone_number} onChange={set("phone_number")} /></label>
          <label className="text-sm font-medium">Email<input className={field} type="email" value={form.email} onChange={set("email")} /></label>
          <label className="text-sm font-medium">Website<input className={field} value={form.website} onChange={set("website")} placeholder="https://" /></label>
          <label className="text-sm font-medium sm:col-span-2">Address<input className={field} value={form.address} onChange={set("address")} /></label>
          <label className="text-sm font-medium sm:col-span-2">Notes<textarea className={`${field} min-h-20`} value={form.notes} onChange={set("notes")} /></label>
        </div>
        {error && <p role="alert" className="mx-5 mb-2 rounded-lg border border-ab-danger/40 bg-ab-danger/10 px-3 py-2 text-sm text-ab-danger">{error}</p>}
        <footer className="flex justify-end gap-2 border-t border-ab-border px-5 py-3">
          <Button onClick={onClose} disabled={busy}>Cancel</Button>
          <Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {partner ? "Save" : "Add partner"}</Button>
        </footer>
      </form>
    </div>
  )
}
