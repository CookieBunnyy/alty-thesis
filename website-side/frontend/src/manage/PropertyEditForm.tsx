import { useState, type FormEvent, type ReactNode } from "react"
import { LoaderCircle, X } from "lucide-react"
import { CATEGORIES } from "@/lib/categories"
import { statusLabel } from "./format"
import { Button } from "./ui"
import { useStaffAuth } from "./staffContext"
import { t } from "./i18n"

export type Listing = {
  listing_id: number
  external_listing_id: string | null
  title: string | null
  category: string | null
  price_total: number | null
  initial_dp: number | null
  monthly_rate: number | null
  num_bedrooms: number | null
  num_bathrooms: number | null
  layout_type: string | null
  village_name: string | null
  lat: number | null
  lng: number | null
  photos: string[] | null
  amenity_list: string[] | Record<string, unknown> | null
  nearby_places: unknown
  nearby_establishments: unknown
  details: string | null
  has_balcony: boolean | null
  has_kitchen: boolean | null
  has_backyard: boolean | null
  has_garage: boolean | null
  garage_spaces: number | null
  status: string
  partner_id: number | null
  sync_status: string
  last_synced_at: string | null
  created_at: string | null
  updated_at: string | null
}

const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"
// RESERVED / SOLD come from reservation and sale documents (the API refuses
// them here), so only these can be chosen by hand.
const MANUAL = ["AVAILABLE", "ON_HOLD", "UNAVAILABLE"]

function Field({ label, children, wide }: { label: string; children: ReactNode; wide?: boolean }) {
  return (
    <label className={`block text-sm font-medium ${wide ? "sm:col-span-2" : ""}`}>
      {t(label)}
      {children}
    </label>
  )
}

const num = (value: string) => (value.trim() === "" ? null : Number(value))

/** Edit a listing (Administrator, General Manager, President, Filing Manager).
 *  Sends only the fields that changed, like the desktop edit dialog. */
export function PropertyEditForm({ listing, partners, onClose, onSaved }: {
  listing: Listing; partners: { id: number; name: string; status: string }[]; onClose: () => void; onSaved: (l: Listing) => void
}) {
  const { api } = useStaffAuth()
  const amenities = Array.isArray(listing.amenity_list) ? listing.amenity_list : listing.amenity_list ? Object.keys(listing.amenity_list) : []
  const [form, setForm] = useState({
    title: listing.title ?? "",
    category: listing.category ?? "", // kept as stored; the standard names are suggestions
    price_total: String(listing.price_total ?? ""),
    initial_dp: String(listing.initial_dp ?? ""),
    monthly_rate: String(listing.monthly_rate ?? ""),
    num_bedrooms: String(listing.num_bedrooms ?? ""),
    num_bathrooms: String(listing.num_bathrooms ?? ""),
    layout_type: listing.layout_type ?? "",
    village_name: listing.village_name ?? "",
    lat: listing.lat == null ? "" : String(listing.lat),
    lng: listing.lng == null ? "" : String(listing.lng),
    details: listing.details ?? "",
    amenities: amenities.join(", "),
    photos: (listing.photos ?? []).join("\n"),
    has_balcony: Boolean(listing.has_balcony),
    has_kitchen: Boolean(listing.has_kitchen),
    has_backyard: Boolean(listing.has_backyard),
    has_garage: Boolean(listing.has_garage),
    garage_spaces: String(listing.garage_spaces ?? 0),
    status: listing.status,
    partner_id: listing.partner_id == null ? "" : String(listing.partner_id),
  })
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }))
  const locked = listing.status === "SOLD"
  const statusOptions = [...new Set([listing.status, ...MANUAL])]

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError("")
    if (!form.title.trim()) return setError(t("Title is required."))
    const numbers = { price_total: num(form.price_total), initial_dp: num(form.initial_dp), monthly_rate: num(form.monthly_rate), num_bedrooms: num(form.num_bedrooms), num_bathrooms: num(form.num_bathrooms), garage_spaces: num(form.garage_spaces) }
    if (Object.values(numbers).some((v) => v !== null && (!Number.isFinite(v) || v < 0))) return setError(t("Prices, rooms and garage spaces must be zero or more."))
    const lat = num(form.lat)
    const lng = num(form.lng)
    if ((lat === null) !== (lng === null)) return setError(t("Enter both latitude and longitude, or neither."))
    if (lat !== null && (lat < -90 || lat > 90 || lng! < -180 || lng! > 180)) return setError(t("Latitude must be −90 to 90 and longitude −180 to 180."))

    const next: Record<string, unknown> = {
      title: form.title.trim(),
      category: form.category.trim() || null,
      ...numbers,
      layout_type: form.layout_type.trim() || null,
      village_name: form.village_name.trim() || null,
      lat, lng,
      details: form.details.trim() || null,
      amenity_list: form.amenities.split(",").map((a) => a.trim()).filter(Boolean),
      photos: form.photos.split("\n").map((p) => p.trim()).filter(Boolean),
      has_balcony: form.has_balcony, has_kitchen: form.has_kitchen, has_backyard: form.has_backyard, has_garage: form.has_garage,
      status: form.status,
      partner_id: form.partner_id ? Number(form.partner_id) : null,
    }
    const current: Record<string, unknown> = { ...listing, amenity_list: amenities, photos: listing.photos ?? [] }
    const changes = Object.fromEntries(
      Object.entries(next).filter(([key, value]) => JSON.stringify(value ?? null) !== JSON.stringify(current[key] ?? null)
        && !(typeof value === "number" && Number(current[key]) === value)),
    )
    if (!Object.keys(changes).length) return onClose()
    setBusy(true)
    try {
      onSaved(await api<Listing>(`/property-listings/${listing.listing_id}`, { method: "PUT", body: JSON.stringify(changes) }))
    } catch (saveError) {
      setError((saveError as Error).message)
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={t("Edit property")}>
      <button type="button" aria-label={t("Cancel")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={submit} noValidate className="ab-pop relative flex max-h-[94dvh] w-full max-w-3xl flex-col rounded-t-2xl border border-ab-border bg-ab-card shadow-2xl sm:rounded-2xl">
        <header className="flex items-center justify-between border-b border-ab-border px-5 py-4">
          <h2 className="text-lg font-bold">{t("Edit property #{id}", { id: listing.listing_id })}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close")} className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><X className="h-4 w-4" /></button>
        </header>
        <div className="grid flex-1 gap-4 overflow-y-auto p-5 sm:grid-cols-2">
          <Field label="Title *" wide><input className={field} value={form.title} onChange={(e) => set("title", e.target.value)} required /></Field>
          <Field label="Category">
            <input className={field} list="property-categories" value={form.category} onChange={(e) => set("category", e.target.value)} />
            <datalist id="property-categories">{CATEGORIES.map((c) => <option key={c.key} value={c.label} />)}</datalist>
          </Field>
          <Field label="Status">
            <select className={field} value={form.status} disabled={locked} onChange={(e) => set("status", e.target.value)}>
              {statusOptions.map((s) => <option key={s} value={s} disabled={!MANUAL.includes(s) && s !== listing.status}>{statusLabel(s)}</option>)}
            </select>
            <span className="mt-1 block text-xs font-normal text-ab-faint">
              {locked ? t("A sold property's status can't be changed.") : t("Reserved and Sold are set by reservation and sale documents.")}
            </span>
          </Field>
          <Field label="Developer / partner">
            <select className={field} value={form.partner_id} onChange={(e) => set("partner_id", e.target.value)}>
              <option value="">{t("Not set")}</option>
              {partners.filter((p) => p.status === "ACTIVE" || String(p.id) === form.partner_id).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </Field>
          <Field label="Total price (₱)"><input className={field} inputMode="decimal" value={form.price_total} onChange={(e) => set("price_total", e.target.value)} /></Field>
          <Field label="Initial down payment (₱)"><input className={field} inputMode="decimal" value={form.initial_dp} onChange={(e) => set("initial_dp", e.target.value)} /></Field>
          <Field label="Monthly rate (₱)"><input className={field} inputMode="decimal" value={form.monthly_rate} onChange={(e) => set("monthly_rate", e.target.value)} /></Field>
          <Field label="Layout type"><input className={field} value={form.layout_type} onChange={(e) => set("layout_type", e.target.value)} /></Field>
          <Field label="Bedrooms"><input className={field} inputMode="numeric" value={form.num_bedrooms} onChange={(e) => set("num_bedrooms", e.target.value)} /></Field>
          <Field label="Bathrooms"><input className={field} inputMode="numeric" value={form.num_bathrooms} onChange={(e) => set("num_bathrooms", e.target.value)} /></Field>
          <Field label="Village / location" wide><input className={field} value={form.village_name} onChange={(e) => set("village_name", e.target.value)} /></Field>
          <Field label="Latitude"><input className={field} inputMode="decimal" value={form.lat} onChange={(e) => set("lat", e.target.value)} /></Field>
          <Field label="Longitude"><input className={field} inputMode="decimal" value={form.lng} onChange={(e) => set("lng", e.target.value)} /></Field>
          <fieldset className="sm:col-span-2">
            <legend className="text-sm font-medium">{t("Features")}</legend>
            <div className="mt-2 flex flex-wrap items-center gap-4 text-sm">
              {(["has_balcony", "has_kitchen", "has_backyard", "has_garage"] as const).map((key) => (
                <label key={key} className="flex items-center gap-2">
                  <input type="checkbox" checked={form[key]} onChange={(e) => set(key, e.target.checked)} className="h-4 w-4 accent-[var(--color-ab-accent)]" />
                  {statusLabel(key.replace("has_", ""))}
                </label>
              ))}
              {form.has_garage && (
                <label className="flex items-center gap-2">{t("Spaces")}
                  <input className="w-16 rounded-lg border border-ab-border bg-ab-input px-2 py-1" inputMode="numeric" value={form.garage_spaces} onChange={(e) => set("garage_spaces", e.target.value)} />
                </label>
              )}
            </div>
          </fieldset>
          <Field label="Amenities (comma-separated)" wide><input className={field} value={form.amenities} onChange={(e) => set("amenities", e.target.value)} /></Field>
          <Field label="Description" wide><textarea className={`${field} min-h-24`} value={form.details} onChange={(e) => set("details", e.target.value)} /></Field>
          <Field label="Photo URLs (one per line)" wide><textarea className={`${field} min-h-20 font-mono text-xs`} value={form.photos} onChange={(e) => set("photos", e.target.value)} /></Field>
          <p className="text-xs text-ab-faint sm:col-span-2">{t("Nearby places and establishments are edited in the desktop app for now.")}</p>
        </div>
        {error && <p role="alert" className="mx-5 mb-2 rounded-lg border border-ab-danger/40 bg-ab-danger/10 px-3 py-2 text-sm text-ab-danger">{error}</p>}
        <footer className="flex justify-end gap-2 border-t border-ab-border px-5 py-3">
          <Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button>
          <Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Save changes")}</Button>
        </footer>
      </form>
    </div>
  )
}
