import { useEffect, useMemo, useState } from "react"
import { MapContainer, TileLayer, useMap } from "react-leaflet"
import L from "leaflet"
import "@geoman-io/leaflet-geoman-free"
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css"
import { LoaderCircle, Map as MapIcon, RotateCcw, Satellite, Trash2, X } from "lucide-react"
import { lotAreaLong } from "@/lib/area"
import { LOT_STYLE, crossesItself, formatLength, fromCorners, measure, toLatLngs, type Boundary } from "@/lib/lotGeometry"
import { SATELLITE_ATTRIBUTION, SATELLITE_MAX_ZOOM, SATELLITE_TILES, STREET_TILES, type Basemap } from "@/lib/mapTiles"
import { Button, Confirm } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { t } from "./i18n"
import type { Listing } from "./PropertyEditForm"

const PH_CENTER: [number, number] = [14.5995, 120.9842]

// The property's own map pin: a white outlined pin (seen on satellite and
// street maps), shown for orientation only.
const PIN_ICON = L.divIcon({
  className: "lot-editor-pin",
  html: `<svg width="34" height="44" viewBox="0 0 34 44" aria-hidden="true">
    <path d="M17 42c-1.2-1.6-13-14.6-13-24.5a13 13 0 0 1 26 0C30 27.4 18.2 40.4 17 42Z" fill="rgba(0,0,0,0.28)" stroke="#fff" stroke-width="3" stroke-linejoin="round"/>
    <circle cx="17" cy="17" r="5" fill="none" stroke="#fff" stroke-width="3"/></svg>`,
  iconSize: [34, 44],
  iconAnchor: [17, 42],
})

/** The property's pin, for orientation. It never takes clicks, so corners can
 *  be placed right on it, and the drawing tool ignores it (no snapping). */
function PropertyPin({ position }: { position: [number, number] }) {
  const map = useMap()
  useEffect(() => {
    const pin = L.marker(position, { icon: PIN_ICON, interactive: false, keyboard: false, pmIgnore: true, zIndexOffset: 1000 }).addTo(map)
    return () => { pin.remove() }
  }, [map, position])
  return null
}

/** Ray casting: is the [lng, lat] point inside the outline's corners? */
const contains = (corners: number[][], [x, y]: number[]) => {
  let inside = false
  for (let i = 0, j = corners.length - 1; i < corners.length; j = i++) {
    const [xi, yi] = corners[i]
    const [xj, yj] = corners[j]
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

/** Corner points ([lng, lat]) of a Leaflet polygon layer. */
const cornersOf = (layer: L.Polygon): number[][] => {
  const rings = layer.getLatLngs() as L.LatLng[][]
  return (rings[0] ?? []).map((point) => [Number(point.lng.toFixed(8)), Number(point.lat.toFixed(8))])
}

/** Geoman on the map: draws a new outline, or edits the given one. */
function DrawingLayer({ initial, round, onChange }: { initial: Boundary | null; round: number; onChange: (points: number[][] | null) => void }) {
  const map = useMap()
  useEffect(() => {
    map.pm.setGlobalOptions({ allowSelfIntersection: false, snappable: true, pathOptions: LOT_STYLE, templineStyle: { color: LOT_STYLE.color }, hintlineStyle: { color: LOT_STYLE.color, dashArray: "5 5" } })
    let layer: L.Polygon | null = null
    const watch = (polygon: L.Polygon) => {
      layer = polygon
      polygon.setStyle(LOT_STYLE)
      polygon.pm.enable({ allowSelfIntersection: false, snappable: true })
      const emit = () => onChange(cornersOf(polygon))
      polygon.on("pm:edit pm:vertexadded pm:vertexremoved pm:markerdragend pm:change", emit)
      emit()
    }
    const onCreate = (event: { layer: L.Layer }) => {
      map.pm.disableDraw()
      watch(event.layer as L.Polygon)
    }
    map.on("pm:create", onCreate)
    if (initial) {
      const polygon = L.polygon(toLatLngs(initial), LOT_STYLE).addTo(map)
      watch(polygon)
      map.fitBounds(polygon.getBounds(), { padding: [60, 60], maxZoom: 19 })
    } else {
      onChange(null)
      map.pm.enableDraw("Polygon", { allowSelfIntersection: false, snappable: true, finishOn: null })
    }
    return () => {
      map.off("pm:create", onCreate)
      map.pm.disableDraw()
      layer?.pm.disable()
      layer?.remove()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, round])
  return null
}

/** Draw or adjust a property's lot outline over satellite imagery, see
 *  its measurements live, and save it. Property editors only. */
export function BoundaryEditor({ listing, onClose, onSaved }: { listing: Listing; onClose: () => void; onSaved: (listing: Listing) => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const saved = (listing.boundary as Boundary | null | undefined) ?? null
  const [start, setStart] = useState<Boundary | null>(saved)
  const [round, setRound] = useState(0)
  const [points, setPoints] = useState<number[][] | null>(null)
  const [basemap, setBasemap] = useState<Basemap>("satellite")
  const [useAsLotArea, setUseAsLotArea] = useState(listing.lot_area_sqm == null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [confirmRemove, setConfirmRemove] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && !confirmRemove && onClose()
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [busy, confirmRemove, onClose])

  const shape = points && points.length >= 3 ? fromCorners(points) : null
  const measured = useMemo(() => (shape ? measure(shape) : null), [shape])
  const invalid = points && points.length >= 3 && crossesItself(points) ? t("The boundary crosses itself; move the points so the sides don't cross.") : ""
  const pin = useMemo<[number, number] | null>(
    () => (listing.lat != null && listing.lng != null ? [Number(listing.lat), Number(listing.lng)] : null),
    [listing.lat, listing.lng],
  )
  const center: [number, number] = pin ?? PH_CENTER
  const pinOutside = Boolean(pin && points && points.length >= 3 && !contains(points, [pin[1], pin[0]]))

  const redraw = () => { setStart(null); setPoints(null); setError(""); setRound((n) => n + 1) }
  const save = async () => {
    if (!shape || invalid) return
    setBusy(true)
    setError("")
    try {
      const updated = await api<Listing>(`/property-listings/${listing.listing_id}/boundary`, {
        method: "PUT", body: JSON.stringify({ geometry: shape, use_as_lot_area: useAsLotArea }),
      })
      toast(t("Lot boundary saved."))
      onSaved(updated)
    } catch (saveError) {
      setError(t((saveError as Error).message))
      setBusy(false)
    }
  }
  const remove = async () => {
    setBusy(true)
    try {
      const updated = await api<Listing>(`/property-listings/${listing.listing_id}/boundary`, { method: "DELETE" })
      toast(t("Lot boundary removed."))
      onSaved(updated)
    } catch (removeError) {
      toast(t((removeError as Error).message), "error")
      setBusy(false)
      setConfirmRemove(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[80] flex flex-col bg-ab-bg" role="dialog" aria-modal="true" aria-label={t("Lot boundary")}>
      <header className="flex flex-wrap items-center gap-3 border-b border-ab-border bg-ab-sidebar px-4 py-3">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-lg font-extrabold">{t("Lot boundary")} · {listing.title}</h2>
          <p className="text-xs text-ab-muted">
            {points ? t("Drag the corners to adjust; drag a side's middle point to add a corner; right-click a corner to remove it.")
              : pin
                ? t("The white pin marks the property. Click each corner of its lot, then click the first corner again to close the outline.")
                : t("This property has no map pin yet, so find its lot on the map. Click each corner, then click the first corner again to close the outline.")}
          </p>
        </div>
        <button type="button" onClick={() => setBasemap((value) => (value === "satellite" ? "map" : "satellite"))}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-ab-border-strong px-3 text-sm font-semibold hover:bg-ab-hover">
          {basemap === "satellite" ? <MapIcon className="h-4 w-4" /> : <Satellite className="h-4 w-4" />}
          {basemap === "satellite" ? t("Street map") : t("Satellite")}
        </button>
        <button type="button" onClick={onClose} aria-label={t("Close")} className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><X className="h-5 w-5" /></button>
      </header>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div className="relative min-h-[320px] flex-1">
          <MapContainer center={center} zoom={18} maxZoom={20} className="h-full w-full" zoomControl>
            {basemap === "satellite"
              ? <TileLayer key="sat" url={SATELLITE_TILES} maxNativeZoom={SATELLITE_MAX_ZOOM} maxZoom={20} attribution={SATELLITE_ATTRIBUTION} />
              : <TileLayer key="osm" url={STREET_TILES} maxNativeZoom={19} maxZoom={20} attribution="&copy; OpenStreetMap contributors" />}
            {pin && <PropertyPin position={pin} />}
            <DrawingLayer initial={start} round={round} onChange={setPoints} />
          </MapContainer>
        </div>

        <aside className="w-full shrink-0 space-y-4 overflow-y-auto border-t border-ab-border bg-ab-card p-4 lg:w-80 lg:border-l lg:border-t-0">
          <section>
            <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("Measurements")}</p>
            {measured ? (
              <dl className="mt-2 space-y-1.5 text-sm">
                <div className="flex justify-between gap-3"><dt className="text-ab-muted">{t("Area")}</dt><dd className="text-right font-bold tabular-nums">{lotAreaLong(measured.area_sqm)}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-ab-muted">{t("Perimeter")}</dt><dd className="font-bold tabular-nums">{formatLength(measured.perimeter_m)}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-ab-muted">{t("Corners")}</dt><dd className="tabular-nums">{points!.length}</dd></div>
              </dl>
            ) : (
              <p className="mt-2 text-sm text-ab-muted">{t("The area and side lengths appear once the outline is closed.")}</p>
            )}
            {measured && (
              <ol className="mt-3 space-y-0.5 text-xs text-ab-muted">
                {measured.sides_m.map((side, index) => (
                  <li key={index} className="flex justify-between"><span>{t("Side {n}", { n: index + 1 })}</span><span className="tabular-nums">{formatLength(side)}</span></li>
                ))}
              </ol>
            )}
            <p className="mt-3 text-[11px] text-ab-faint">{t("Geodesic estimates from the outline you draw on the imagery; not an official survey.")}</p>
          </section>

          {listing.lot_area_sqm != null && measured && (
            <p className="rounded-xl bg-ab-card-2 p-2.5 text-xs text-ab-muted">
              {t("Stated lot area: {v}", { v: lotAreaLong(listing.lot_area_sqm) ?? "—" })}
            </p>
          )}
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={useAsLotArea} onChange={(e) => setUseAsLotArea(e.target.checked)} className="mt-0.5 h-4 w-4 accent-[var(--color-ab-accent)]" />
            <span>{t("Also set the property's lot area to the measured area")}</span>
          </label>

          {pinOutside && !invalid && (
            <p className="rounded-xl bg-ab-warning/15 p-2.5 text-sm text-ab-text">
              {t("The property's pin is outside this outline. Check that you traced the right lot (or that the pin is in the right place).")}
            </p>
          )}
          {(invalid || error) && <p role="alert" className="rounded-xl bg-ab-danger/10 p-2.5 text-sm text-ab-danger">{invalid || error}</p>}

          <div className="flex flex-wrap gap-2">
            <Button variant="primary" onClick={() => void save()} disabled={busy || !shape || Boolean(invalid)}>
              {busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Save boundary")}
            </Button>
            <Button onClick={redraw} disabled={busy}><RotateCcw className="h-4 w-4" /> {t("Start over")}</Button>
            {saved && <Button variant="danger" onClick={() => setConfirmRemove(true)} disabled={busy}><Trash2 className="h-4 w-4" /> {t("Remove")}</Button>}
          </div>
        </aside>
      </div>
      {confirmRemove && (
        // Above the map's own layers inside this full-screen editor.
        <div className="relative z-[2000]">
        <Confirm title={t("Remove the lot boundary?")} message={t("The outline is deleted from the map. The property's lot area value stays.")}
          confirmLabel={t("Remove boundary")} busy={busy} typeToConfirm="Delete" onConfirm={() => void remove()} onCancel={() => setConfirmRemove(false)} />
        </div>
      )}
    </div>
  )
}
