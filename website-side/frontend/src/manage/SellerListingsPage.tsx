import { useCallback, useMemo, useState, type FormEvent } from "react"
import { LoaderCircle, Pencil, X } from "lucide-react"
import { categoryLabel } from "@/lib/categories"
import { lotAreaLong } from "@/lib/area"
import { publicUrl } from "@/config"
import { contains, peso, statusLabel, text } from "./format"
import { Badge, Button, DataTable, Drawer, Facts, LoadState, PageHeader, SearchBox, Section, Select, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData, useOpenRecord } from "./useApiData"
import { t } from "./i18n"

type SellerListing = {
  listing_id: number; listing_code: string | null; title: string | null; category: string | null; project_name: string | null
  price_total: number | null; initial_dp: number | null; monthly_rate: number | null; num_bedrooms: number | null; num_bathrooms: number | null
  village_name: string | null; lot_area_sqm: number | null; floor_area_sqm: number | null; details: string | null
  amenity_list: unknown; photos: string[]; media: string[]; status: string; developer: string | null
  assigned: boolean; editable_fields: string[]
}

const amenityNames = (raw: unknown): string[] =>
  Array.isArray(raw) ? raw.map(String) : raw && typeof raw === "object" ? Object.entries(raw as Record<string, unknown>).filter(([, on]) => on).map(([k]) => k.replace(/_/g, " ")) : []

/** A seller's listings: those assigned to them, plus every listing approved for marketing. */
export function SellerListingsPage() {
  const { api } = useStaffAuth()
  const { id, open, close } = useOpenRecord()
  const [search, setSearch] = useState("")
  const [scope, setScope] = useState("")
  const load = useCallback(() => api<SellerListing[]>("/seller/listings"), [api])
  const { data, error, loading, reload } = useApiData(load, "seller-listings")
  const rows = useMemo(() => data ?? [], [data])
  const shown = rows.filter((l) => (!scope || (scope === "ASSIGNED" ? l.assigned : !l.assigned)) &&
    contains([l.title, l.project_name, l.village_name, l.developer, l.listing_code], search))
  const selected = id ? rows.find((l) => String(l.listing_id) === id) ?? null : null

  const columns: Column<SellerListing>[] = [
    {
      key: "title", label: "Property", sort: (l) => l.title ?? "",
      render: (l) => (
        <span className="min-w-0">
          <span className="block truncate font-semibold">{text(l.title)}</span>
          <span className="block truncate text-xs text-ab-faint">{[l.project_name, l.developer].filter(Boolean).join(" · ") || text(l.village_name)}</span>
        </span>
      ),
    },
    { key: "category", label: "Category", sort: (l) => categoryLabel(l.category), render: (l) => t(categoryLabel(l.category)), hideOnPhone: true },
    { key: "price", label: "Price", align: "right", sort: (l) => l.price_total ?? 0, render: (l) => peso(l.price_total) },
    { key: "status", label: "Status", sort: (l) => l.status, render: (l) => <Badge value={l.status} /> },
    { key: "mine", label: "Assigned", sort: (l) => (l.assigned ? 1 : 0), render: (l) => (l.assigned ? <span className="rounded-full bg-ab-accent-soft px-2 py-0.5 text-[11px] font-semibold text-ab-accent">{t("Assigned to you")}</span> : <span className="text-xs text-ab-faint">{t("Available to market")}</span>) },
  ]

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageHeader title="Your listings" subtitle="Listings assigned to you, and every other listing currently approved for marketing. You can update the description and amenities of listings assigned to you." />
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <>
          <Tiles items={[
            { label: "Assigned to you", value: rows.filter((l) => l.assigned).length, onClick: () => setScope(scope === "ASSIGNED" ? "" : "ASSIGNED"), active: scope === "ASSIGNED" },
            { label: "Available to market", value: rows.filter((l) => !l.assigned).length, onClick: () => setScope(scope === "OTHER" ? "" : "OTHER"), active: scope === "OTHER" },
          ]} />
          <div className="flex flex-wrap gap-2 sm:flex-nowrap">
            <div className="w-full sm:w-auto sm:flex-1"><SearchBox value={search} onChange={setSearch} placeholder="Search property, project, developer or location" /></div>
            <Select label="Show" value={scope} onChange={setScope} options={[{ value: "", label: "All" }, { value: "ASSIGNED", label: "Assigned to you" }, { value: "OTHER", label: "Available to market" }]} />
          </div>
          <DataTable rows={shown} columns={columns} rowKey={(l) => String(l.listing_id)} onOpen={(l) => open(String(l.listing_id))}
            empty="No listings yet. Listings assigned to you and listings approved for marketing appear here." initialSort={{ key: "mine", dir: "desc" }} />
        </>
      )}
      {selected && <SellerListingDrawer listing={selected} onClose={close} onSaved={() => void reload()} />}
    </div>
  )
}

function SellerListingDrawer({ listing, onClose, onSaved }: { listing: SellerListing; onClose: () => void; onSaved: () => void }) {
  const [editing, setEditing] = useState(false)
  const photo = listing.photos[0] ?? (listing.media[0] ? publicUrl(listing.media[0]) : null)
  const amenities = amenityNames(listing.amenity_list)
  return (
    <Drawer title={text(listing.title)} subtitle={<span className="flex flex-wrap items-center gap-2"><Badge value={listing.status} /> {t(categoryLabel(listing.category))}</span>} onClose={onClose}
      footer={listing.editable_fields.length > 0 && <Button variant="primary" onClick={() => setEditing(true)}><Pencil className="h-4 w-4" /> {t("Update details")}</Button>}>
      {photo && <img src={photo} alt="" className="aspect-video w-full rounded-2xl object-cover" />}
      <Section title="Details">
        <Facts items={[
          ["Developer", listing.developer],
          ["Project", listing.project_name],
          ["Location", listing.village_name],
          ["Price", peso(listing.price_total)],
          ["Down payment", listing.initial_dp ? peso(listing.initial_dp) : null],
          ["Monthly", listing.monthly_rate ? peso(listing.monthly_rate) : null],
          ["Bedrooms / bathrooms", `${listing.num_bedrooms ?? "—"} / ${listing.num_bathrooms ?? "—"}`],
          ["Lot area", lotAreaLong(listing.lot_area_sqm)],
          ["Floor area", listing.floor_area_sqm ? `${listing.floor_area_sqm.toLocaleString()} sqm` : null],
          ["Status", statusLabel(listing.status)],
        ]} />
      </Section>
      <Section title="Description & amenities">
        {listing.details ? <p className="whitespace-pre-line text-sm text-ab-muted">{listing.details}</p> : <p className="text-sm italic text-ab-faint">{t("No description yet.")}</p>}
        {amenities.length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">{amenities.map((a) => <span key={a} className="rounded-full border border-ab-border bg-ab-card-2 px-2.5 py-1 text-xs">{a}</span>)}</div>}
      </Section>
      {!listing.assigned && <p className="text-xs text-ab-faint">{t("This listing isn't assigned to you, so you can view it but not change it.")}</p>}
      {editing && <SellerListingForm listing={listing} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); onSaved() }} />}
    </Drawer>
  )
}

const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"

function SellerListingForm({ listing, onClose, onSaved }: { listing: SellerListing; onClose: () => void; onSaved: () => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const [details, setDetails] = useState(listing.details ?? "")
  const [amenities, setAmenities] = useState(amenityNames(listing.amenity_list).join(", "))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const can = (name: string) => listing.editable_fields.includes(name)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError("")
    const body: Record<string, unknown> = {}
    if (can("details")) body.details = details.trim() || null
    if (can("amenity_list")) body.amenity_list = amenities.split(",").map((a) => a.trim()).filter(Boolean)
    try {
      await api(`/seller/listings/${listing.listing_id}`, { method: "PUT", body: JSON.stringify(body) })
      toast(t("Saved {name}.", { name: listing.title ?? "" }))
      onSaved()
    } catch (saveError) {
      setError(t((saveError as Error).message))
      setBusy(false)
    }
  }
  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={t("Update details")}>
      <button type="button" aria-label={t("Cancel")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={submit} noValidate className="ab-pop relative flex max-h-[94dvh] w-full max-w-xl flex-col rounded-t-2xl border border-ab-border bg-ab-card shadow-2xl sm:rounded-2xl">
        <header className="flex items-center justify-between border-b border-ab-border px-5 py-4">
          <h2 className="text-lg font-bold">{t("Update {name}", { name: listing.title ?? "" })}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close")} className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><X className="h-4 w-4" /></button>
        </header>
        <div className="space-y-3 overflow-y-auto p-5">
          {can("details") && <label className="block text-sm font-medium">{t("Description")}<textarea className={`${field} min-h-32`} value={details} onChange={(e) => setDetails(e.target.value)} /></label>}
          {can("amenity_list") && <label className="block text-sm font-medium">{t("Amenities (comma-separated)")}<input className={field} value={amenities} onChange={(e) => setAmenities(e.target.value)} /></label>}
          <p className="text-xs text-ab-faint">{t("Prices, status and other details are managed by Abellar Realty.")}</p>
          {error && <p role="alert" className="text-sm text-ab-danger">{error}</p>}
        </div>
        <footer className="flex justify-end gap-2 border-t border-ab-border px-5 py-3">
          <Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button>
          <Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Save")}</Button>
        </footer>
      </form>
    </div>
  )
}
