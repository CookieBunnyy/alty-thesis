import { useState } from "react"
import { LandPlot } from "lucide-react"
import { lotAreaLong } from "@/lib/area"
import { formatLength, measure } from "@/lib/lotGeometry"
import type { Property } from "@/types"

/** What the mapped lot boundary measures; says plainly when there is none. */
export function LotMeasurements({ property, compact = false }: { property: Property; compact?: boolean }) {
  const [showSides, setShowSides] = useState(false)
  const boundary = property.boundary
  const stated = lotAreaLong(property.lot_area_sqm)
  if (!boundary) {
    return (
      <p className="flex items-center gap-1.5 text-xs text-ab-faint">
        <LandPlot className="h-3.5 w-3.5" />
        {stated ? `Lot area: ${stated} · boundary not mapped yet` : "Lot boundary not mapped yet"}
      </p>
    )
  }
  const measured = property.boundary_measurements ?? measure(boundary)
  const statedDiffers = property.lot_area_sqm != null && Math.abs(Number(property.lot_area_sqm) - measured.area_sqm) / measured.area_sqm > 0.02
  return (
    <div className={`rounded-xl border border-ab-border bg-ab-card ${compact ? "p-2.5" : "p-3"}`}>
      <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ab-faint">
        <LandPlot className="h-3.5 w-3.5 text-[#E0242B]" /> Lot boundary
      </p>
      <dl className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
        <dt className="text-ab-muted">Area</dt><dd className="text-right font-semibold tabular-nums">{lotAreaLong(measured.area_sqm)}</dd>
        <dt className="text-ab-muted">Perimeter</dt><dd className="text-right font-semibold tabular-nums">{formatLength(measured.perimeter_m)}</dd>
        {statedDiffers && <><dt className="text-ab-muted">Stated lot area</dt><dd className="text-right tabular-nums">{stated}</dd></>}
      </dl>
      <button type="button" onClick={() => setShowSides((value) => !value)} className="mt-1.5 text-xs font-semibold text-ab-accent hover:underline" aria-expanded={showSides}>
        {showSides ? "Hide side lengths" : `Side lengths (${measured.sides_m.length})`}
      </button>
      {showSides && (
        <ol className="mt-1 grid grid-cols-2 gap-x-3 text-xs text-ab-muted">
          {measured.sides_m.map((side, index) => (
            <li key={index} className="flex justify-between"><span>Side {index + 1}</span><span className="tabular-nums">{formatLength(side)}</span></li>
          ))}
        </ol>
      )}
      <p className="mt-1.5 text-[11px] text-ab-faint">Estimated from the outline mapped on satellite imagery; not an official survey.</p>
    </div>
  )
}
