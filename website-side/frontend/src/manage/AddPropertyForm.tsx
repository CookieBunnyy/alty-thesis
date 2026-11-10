// Add a property (Administrator or seller), or let a seller finish the
// property they added until it is approved. Step 1: the details, starting
// with the developer the property belongs to. Step 2: photos, floor plans and
// amenity pictures, each checked for quality as it is uploaded.
import { useCallback, useState, type FormEvent, type ReactNode } from "react"
import { Building2, Check, LoaderCircle, MapPin, PencilRuler, X } from "lucide-react"
import { Link } from "@/components/Link"
import { CATEGORIES } from "@/lib/categories"
import { isManagement } from "./format"
import { Button } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData } from "./useApiData"
import { ListingImages } from "./listingImages"
import { LocationPicker } from "./LocationPicker"
import { BoundaryEditor } from "./BoundaryEditor"
import type { Listing } from "./PropertyEditForm"
import { lotAreaLong } from "@/lib/area"
import { t } from "./i18n"

type Developer = { id: number; name: string; status: string; accredited?: boolean; partner_type?: string | null; accreditation_status?: string }
export type DraftListing = {
  listing_id: number; title: string | null; category: string | null; project_name: string | null; partner_id: number | null
  price_total: number | string | null; initial_dp: number | string | null; monthly_rate: number | string | null
  num_bedrooms: number | null; num_bathrooms: number | null; layout_type: string | null; village_name: string | null
  lat: number | string | null; lng: number | string | null; amenity_list: unknown; details: string | null
  has_balcony: boolean | null; has_kitchen: boolean | null; has_backyard: boolean | null; has_garage: boolean | null
  garage_spaces: number | null; lot_area_sqm: number | string | null; floor_area_sqm: number | string | null
  boundary?: unknown
}

const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"
const str = (value: unknown) => (value === null || value === undefined ? "" : String(value))
const num = (value: string) => (value.trim() === "" ? null : Number(value.replace(/,/g, "")))
const amenityNames = (raw: unknown): string[] =>
  Array.isArray(raw) ? raw.map(String) : raw && typeof raw === "object" ? Object.keys(raw as Record<string, unknown>) : []

function Field({ label, children, wide, hint }: { label: string; children: ReactNode; wide?: boolean; hint?: ReactNode }) {
  return (
    <label className={`block text-sm font-medium ${wide ? "sm:col-span-2" : ""}`}>
      {t(label)}
      {children}
      {hint && <span className="mt-1 block text-xs font-normal text-ab-faint">{hint}</span>}
    </label>
  )
}

function useDevelopers() {
  const { api, user } = useStaffAuth()
  const management = isManagement(user?.role)
  const load = useCallback(async () => {
    if (!management) return api<Developer[]>("/seller/developers")
    const partners = await api<Developer[]>("/partners")
    return partners.filter((p) => (p.partner_type ?? "").toUpperCase() === "DEVELOPER" && p.status === "ACTIVE")
      .map((p) => ({ ...p, accredited: p.accreditation_status === "VERIFIED" }))
  }, [api, management])
  return { ...useApiData(load, management ? "developer-options" : "seller-developers"), management }
}

/** `listing` given: a seller edits the property they added (until approved). */
export function AddPropertyForm({ listing, onClose, onSaved }: { listing?: DraftListing; onClose: () => void; onSaved: (id: number) => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const developers = useDevelopers()
  const [step, setStep] = useState<"details" | "images">("details")
  const [savedId, setSavedId] = useState<number | null>(listing?.listing_id ?? null)
  const [form, setForm] = useState({
    partner_id: str(listing?.partner_id), title: str(listing?.title), category: str(listing?.category),
    project_name: str(listing?.project_name), price_total: str(listing?.price_total), initial_dp: str(listing?.initial_dp),
    monthly_rate: str(listing?.monthly_rate), num_bedrooms: str(listing?.num_bedrooms), num_bathrooms: str(listing?.num_bathrooms),
    layout_type: str(listing?.layout_type), village_name: str(listing?.village_name), lat: str(listing?.lat), lng: str(listing?.lng),
    floor_area_sqm: str(listing?.floor_area_sqm), lot_area_sqm: str(listing?.lot_area_sqm),
    amenities: amenityNames(listing?.amenity_list).join(", "), details: str(listing?.details),
    has_balcony: Boolean(listing?.has_balcony), has_kitchen: Boolean(listing?.has_kitchen),
    has_backyard: Boolean(listing?.has_backyard), has_garage: Boolean(listing?.has_garage), garage_spaces: str(listing?.garage_spaces ?? 0),
  })
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [picking, setPicking] = useState(false)
  const [drawing, setDrawing] = useState(false)
  // The saved listing, for the lot boundary drawn after saving the details.
  const [saved, setSaved] = useState<Listing | null>(listing ? (listing as unknown as Listing) : null)
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }))
  const developer = developers.data?.find((d) => String(d.id) === form.partner_id)
  const pinned = form.lat !== "" && form.lng !== ""

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError("")
    if (!form.partner_id) return setError(t("Choose the developer this property belongs to."))
    if (!form.title.trim()) return setError(t("Title is required."))
    if (!form.category.trim()) return setError(t("Category is required."))
    const numbers = { price_total: num(form.price_total), initial_dp: num(form.initial_dp), monthly_rate: num(form.monthly_rate), num_bedrooms: num(form.num_bedrooms), num_bathrooms: num(form.num_bathrooms), garage_spaces: num(form.garage_spaces) }
    if (Object.values(numbers).some((v) => v !== null && (!Number.isFinite(v) || v < 0))) return setError(t("Prices, rooms and garage spaces must be zero or more."))
    const areas = { lot_area_sqm: num(form.lot_area_sqm), floor_area_sqm: num(form.floor_area_sqm) }
    if (Object.values(areas).some((v) => v !== null && (!Number.isFinite(v) || v <= 0))) return setError(t("Areas must be more than zero (leave lot area blank for condominium units)."))
    const lat = num(form.lat)
    const lng = num(form.lng)
    if ((lat === null) !== (lng === null)) return setError(t("Enter both latitude and longitude, or neither."))
    const body = {
      partner_id: Number(form.partner_id), title: form.title.trim(), category: form.category.trim(),
      project_name: form.project_name.trim() || null, ...numbers, ...areas, lat, lng,
      layout_type: form.layout_type.trim() || null, village_name: form.village_name.trim() || null,
      amenity_list: form.amenities.split(",").map((a) => a.trim()).filter(Boolean), details: form.details.trim() || null,
      has_balcony: form.has_balcony, has_kitchen: form.has_kitchen, has_backyard: form.has_backyard, has_garage: form.has_garage,
    }
    setBusy(true)
    try {
      if (listing) {
        const updated = await api<Listing>(`/seller/listings/${listing.listing_id}`, { method: "PUT", body: JSON.stringify(body) })
        setSaved((current) => ({ ...(current ?? updated), ...updated, listing_id: listing.listing_id }))
        toast(t("Saved {name}.", { name: body.title }))
        onSaved(listing.listing_id)
        setStep("images")
      } else {
        const created = await api<Listing>("/property-listings", { method: "POST", body: JSON.stringify(body) })
        setSavedId(created.listing_id)
        setSaved(created)
        toast(t("Property added. Now add its photos, floor plans and amenities."))
        onSaved(created.listing_id)
        setStep("images")
      }
    } catch (saveError) {
      setError(t((saveError as Error).message))
    } finally {
      setBusy(false)
    }
  }

  const body = (
    <>
        <header className="border-b border-ab-border px-5 py-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-lg font-bold">{t(listing ? "Edit your property" : "Add a property")}</h2>
            <button type="button" onClick={onClose} aria-label={t("Close")} className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><X className="h-4 w-4" /></button>
          </div>
          <ol className="mt-2 flex gap-2 text-xs font-semibold" aria-label={t("Steps")}>
            {(["details", "images"] as const).map((key, index) => (
              <li key={key} aria-current={step === key ? "step" : undefined}
                className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 ${step === key ? "bg-ab-accent text-ab-ink" : "bg-ab-card-2 text-ab-muted"}`}>
                {index === 0 && step === "images" ? <Check className="h-3.5 w-3.5" /> : <span>{index + 1}</span>}
                {t(key === "details" ? "Details" : "Photos, floor plans & amenities")}
              </li>
            ))}
          </ol>
        </header>

        {step === "details" ? (
          <div className="grid flex-1 gap-4 overflow-y-auto p-5 sm:grid-cols-2">
            <div className="rounded-xl border border-ab-accent/40 bg-ab-accent-soft p-3 sm:col-span-2">
              <label className="block text-sm font-semibold" htmlFor="developer">
                <Building2 className="mr-1 inline h-4 w-4" aria-hidden />{t("Developer this property belongs to *")}
              </label>
              <select id="developer" className={field} value={form.partner_id} onChange={(e) => set("partner_id", e.target.value)} required>
                <option value="">{t(developers.loading && !developers.data ? "Loading developers…" : "Choose the developer")}</option>
                {(developers.data ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}{d.accredited ? "" : ` (${t("accreditation not verified")})`}</option>)}
              </select>
              <p className="mt-1 text-xs text-ab-muted">
                {developer && !developer.accredited
                  ? t("The Administrator can approve this property for the website once the developer's accreditation of Abellar Realty is verified.")
                  : developers.data?.length === 0
                    ? (developers.management
                      ? <>{t("No developers yet.")} <Link to="/manage/partners" className="font-semibold text-ab-accent hover:underline">{t("Add one in Partners / Developers")}</Link></>
                      : t("No developers yet. Ask the Administrator to add the developer."))
                    : t("Abellar markets developers' properties: the property is listed under this developer.")}
              </p>
            </div>
            <Field label="Title *" wide><input className={field} value={form.title} onChange={(e) => set("title", e.target.value)} placeholder={t("e.g. Metrotowne Studio Unit")} required /></Field>
            <Field label="Category *">
              <input className={field} list="add-categories" value={form.category} onChange={(e) => set("category", e.target.value)} required />
              <datalist id="add-categories">{CATEGORIES.map((c) => <option key={c.key} value={c.label} />)}</datalist>
            </Field>
            <Field label="Project name"><input className={field} value={form.project_name} onChange={(e) => set("project_name", e.target.value)} placeholder={t("e.g. Metrotowne")} /></Field>
            <Field label="Total contract price (₱)"><input className={field} inputMode="decimal" value={form.price_total} onChange={(e) => set("price_total", e.target.value)} /></Field>
            <Field label="Initial down payment (₱)"><input className={field} inputMode="decimal" value={form.initial_dp} onChange={(e) => set("initial_dp", e.target.value)} /></Field>
            <Field label="Monthly rate (₱)"><input className={field} inputMode="decimal" value={form.monthly_rate} onChange={(e) => set("monthly_rate", e.target.value)} /></Field>
            <Field label="Layout / unit type"><input className={field} value={form.layout_type} onChange={(e) => set("layout_type", e.target.value)} placeholder={t("e.g. Studio, 2-BR")} /></Field>
            <Field label="Bedrooms"><input className={field} inputMode="numeric" value={form.num_bedrooms} onChange={(e) => set("num_bedrooms", e.target.value)} /></Field>
            <Field label="Bathrooms"><input className={field} inputMode="numeric" value={form.num_bathrooms} onChange={(e) => set("num_bathrooms", e.target.value)} /></Field>
            <Field label="Floor area (sqm)"><input className={field} inputMode="decimal" value={form.floor_area_sqm} onChange={(e) => set("floor_area_sqm", e.target.value)} /></Field>
            <Field label="Lot area (sqm)" hint={t("Leave blank for condominium units.")}><input className={field} inputMode="decimal" value={form.lot_area_sqm} onChange={(e) => set("lot_area_sqm", e.target.value)} /></Field>
            <Field label="Village / location" wide><input className={field} value={form.village_name} onChange={(e) => set("village_name", e.target.value)} placeholder={t("e.g. Las Piñas City")} /></Field>
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-ab-border bg-ab-card-2 p-3 sm:col-span-2">
              <p className="min-w-0 text-sm">
                <span className="font-medium">{t("Location on the map")}</span>
                <span className="block text-xs text-ab-muted">
                  {pinned ? <><MapPin className="mr-0.5 inline h-3.5 w-3.5 text-ab-danger" aria-hidden />{t("Pinned")} · {Number(form.lat).toFixed(5)}, {Number(form.lng).toFixed(5)}</>
                    : t("Optional, but needed for the website map, travel times and the nearest agents.")}
                </span>
              </p>
              <span className="flex gap-2">
                {pinned && <Button onClick={() => setForm((f) => ({ ...f, lat: "", lng: "" }))}>{t("Remove pin")}</Button>}
                <Button onClick={() => setPicking(true)}><MapPin className="h-4 w-4" /> {t(pinned ? "Move pin" : "Find on map")}</Button>
              </span>
            </div>
            <fieldset className="sm:col-span-2">
              <legend className="text-sm font-medium">{t("Features")}</legend>
              <div className="mt-2 flex flex-wrap items-center gap-4 text-sm">
                {(["has_balcony", "has_kitchen", "has_backyard", "has_garage"] as const).map((key) => (
                  <label key={key} className="flex items-center gap-2">
                    <input type="checkbox" checked={form[key]} onChange={(e) => set(key, e.target.checked)} className="h-4 w-4 accent-[var(--color-ab-accent)]" />
                    {t({ has_balcony: "Balcony", has_kitchen: "Kitchen", has_backyard: "Backyard", has_garage: "Garage" }[key])}
                  </label>
                ))}
                {form.has_garage && <label className="flex items-center gap-2">{t("Spaces")}<input className="w-16 rounded-lg border border-ab-border bg-ab-input px-2 py-1" inputMode="numeric" value={form.garage_spaces} onChange={(e) => set("garage_spaces", e.target.value)} /></label>}
              </div>
            </fieldset>
            <Field label="Amenities (comma-separated)" wide hint={t("Pictures of the amenities can be added in the next step.")}>
              <input className={field} value={form.amenities} onChange={(e) => set("amenities", e.target.value)} placeholder={t("e.g. Swimming pool, Basketball court, 24-hr security")} />
            </Field>
            <Field label="Description" wide><textarea className={`${field} min-h-24`} value={form.details} onChange={(e) => set("details", e.target.value)} /></Field>
            <p className="text-xs text-ab-faint sm:col-span-2">
              {t("New properties are saved as not approved: they appear on the website once the Administrator approves them for marketing.")}
            </p>
          </div>
        ) : (
          <div className="flex-1 space-y-5 overflow-y-auto p-5">
            {saved && (
              <section className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-ab-border p-3" aria-labelledby="lot-boundary">
                <div className="min-w-0">
                  <h3 id="lot-boundary" className="text-sm font-bold">{t("Lot boundary (optional)")}</h3>
                  <p className="text-xs text-ab-faint">
                    {saved.boundary
                      ? t("Drawn · lot area {area}", { area: lotAreaLong(saved.lot_area_sqm) ?? "—" })
                      : t("Outline the lot on the satellite map in red to measure its area and sides. Skip for condominium units.")}
                  </p>
                </div>
                <Button onClick={() => setDrawing(true)}><PencilRuler className="h-4 w-4" /> {t(saved.boundary ? "Redraw lot boundary" : "Draw lot boundary")}</Button>
              </section>
            )}
            {savedId && <ListingImages listingId={savedId} editable />}
          </div>
        )}

        {error && <p role="alert" className="mx-5 mb-2 rounded-lg border border-ab-danger/40 bg-ab-danger/10 px-3 py-2 text-sm text-ab-danger">{error}</p>}
        <footer className="flex justify-end gap-2 border-t border-ab-border px-5 py-3">
          {step === "details" ? (
            <>
              <Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button>
              {listing && <Button onClick={() => setStep("images")} disabled={busy}>{t("Skip to images")}</Button>}
              <Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t(listing ? "Save and continue" : "Save and add images")}</Button>
            </>
          ) : (
            <>
              <Button onClick={() => setStep("details")}>{t("Back to details")}</Button>
              <Button variant="primary" onClick={onClose}><Check className="h-4 w-4" /> {t("Done")}</Button>
            </>
          )}
        </footer>
    </>
  )

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={t(listing ? "Edit your property" : "Add a property")}>
      <button type="button" aria-label={t("Close")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      {/* The images step holds its own dialogs (with forms), so only the details step is a form. */}
      {step === "details" ? (
        <form onSubmit={submit} noValidate className="ab-pop relative flex max-h-[94dvh] w-full max-w-3xl flex-col rounded-t-2xl border border-ab-border bg-ab-card shadow-2xl sm:rounded-2xl">{body}</form>
      ) : (
        <div className="ab-pop relative flex max-h-[94dvh] w-full max-w-3xl flex-col rounded-t-2xl border border-ab-border bg-ab-card shadow-2xl sm:rounded-2xl">{body}</div>
      )}
      {picking && (
        <LocationPicker title={t("Where is the property?")}
          initial={pinned ? { lat: Number(form.lat), lng: Number(form.lng) } : null}
          initialQuery={[form.project_name, form.village_name].filter(Boolean).join(", ")}
          onClose={() => setPicking(false)}
          onPick={(picked) => {
            setForm((f) => ({ ...f, lat: String(picked.lat), lng: String(picked.lng),
              village_name: f.village_name.trim() || (picked.address ?? "").split(",").slice(0, 3).join(",").trim() }))
            setPicking(false)
          }} />
      )}
      {drawing && saved && (
        <BoundaryEditor listing={saved} onClose={() => setDrawing(false)}
          onSaved={(updated) => { setSaved(updated); setForm((f) => ({ ...f, lot_area_sqm: str(updated.lot_area_sqm) })); setDrawing(false) }} />
      )}
    </div>
  )
}
