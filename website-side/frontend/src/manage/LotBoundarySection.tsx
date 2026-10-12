import { lazy, Suspense, useState } from "react"
import { MapContainer, Polygon, TileLayer } from "react-leaflet"
import L from "leaflet"
import { LandPlot, LoaderCircle, PencilRuler } from "lucide-react"
import { lotAreaLong } from "@/lib/area"
import { LOT_STYLE, formatLength, measure, toLatLngs, type Boundary } from "@/lib/lotGeometry"
import { SATELLITE_MAX_ZOOM, SATELLITE_TILES } from "@/lib/mapTiles"
import { Button, Section } from "./ui"
import { dateTime } from "./format"
import { t } from "./i18n"
import type { Listing } from "./PropertyEditForm"

// The drawing tool (and its map library) loads only when it is opened.
const BoundaryEditor = lazy(() => import("./BoundaryEditor").then((m) => ({ default: m.BoundaryEditor })))

/** Property drawer: the mapped lot outline, its measurements, and the tool to draw it. */
export function LotBoundarySection({ listing, canEdit, onSaved }: { listing: Listing; canEdit: boolean; onSaved: (listing: Listing) => void }) {
  const [editing, setEditing] = useState(false)
  const boundary = (listing.boundary as Boundary | null | undefined) ?? null
  const measured = boundary ? (listing.boundary_measurements as ReturnType<typeof measure> | null | undefined) ?? measure(boundary) : null

  return (
    <Section title="Lot boundary"
      action={canEdit && (
        <Button onClick={() => setEditing(true)}><PencilRuler className="h-4 w-4" /> {boundary ? t("Edit boundary") : t("Draw boundary")}</Button>
      )}>
      {boundary && measured ? (
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,14rem)]">
          <div className="h-48 overflow-hidden rounded-xl border border-ab-border">
            <MapContainer bounds={L.latLngBounds(toLatLngs(boundary)).pad(0.25)} maxZoom={20} className="h-full w-full"
              dragging={false} scrollWheelZoom={false} doubleClickZoom={false} touchZoom={false} keyboard={false} zoomControl={false} attributionControl={false}>
              <TileLayer url={SATELLITE_TILES} maxNativeZoom={SATELLITE_MAX_ZOOM} maxZoom={20} />
              <Polygon positions={toLatLngs(boundary)} pathOptions={LOT_STYLE} />
            </MapContainer>
          </div>
          <dl className="space-y-1.5 text-sm">
            <div className="flex justify-between gap-2"><dt className="text-ab-muted">{t("Area")}</dt><dd className="text-right font-bold tabular-nums">{lotAreaLong(measured.area_sqm)}</dd></div>
            <div className="flex justify-between gap-2"><dt className="text-ab-muted">{t("Perimeter")}</dt><dd className="font-bold tabular-nums">{formatLength(measured.perimeter_m)}</dd></div>
            <div className="flex justify-between gap-2"><dt className="text-ab-muted">{t("Sides")}</dt><dd className="text-right text-xs tabular-nums">{measured.sides_m.map((s) => formatLength(s)).join(" · ")}</dd></div>
            {listing.boundary_updated_by && (
              <p className="pt-1 text-[11px] text-ab-faint">{t("Mapped by {name}, {when}", { name: listing.boundary_updated_by, when: listing.boundary_updated_at ? dateTime(listing.boundary_updated_at) : "—" })}</p>
            )}
            <p className="text-[11px] text-ab-faint">{t("Geodesic estimates from the mapped outline; not an official survey.")}</p>
          </dl>
        </div>
      ) : (
        <p className="flex items-center gap-2 rounded-xl border border-dashed border-ab-border p-3 text-sm text-ab-muted">
          <LandPlot className="h-4 w-4 text-ab-faint" />
          {t("No lot boundary mapped yet. Nothing is drawn on the map until someone traces the real outline.")}
        </p>
      )}
      {editing && (
        <Suspense fallback={<div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40"><LoaderCircle className="h-6 w-6 animate-spin text-white" /></div>}>
          <BoundaryEditor listing={listing} onClose={() => setEditing(false)} onSaved={(updated) => { setEditing(false); onSaved(updated) }} />
        </Suspense>
      )}
    </Section>
  )
}
