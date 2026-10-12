import { Bath, BedDouble, Building, MapPin, LandPlot } from "lucide-react"
import { peso, propertyImage } from "@/lib/media"
import { categoryLabel } from "@/lib/categories"
import type { Property } from "@/types"
import { lotAreaShort } from "@/lib/area"

const STATUS_STYLES: Record<string, string> = {
  AVAILABLE: "bg-ab-success text-white",
  RESERVED: "bg-ab-warning text-white",
  SOLD: "bg-ab-info text-white",
}

type Props = {
  property: Property
  onOpen: (property: Property) => void
  onMap?: (property: Property) => void
  style?: React.CSSProperties
  className?: string
  eager?: boolean
}

/** Listing card with real data only: photo, price, place, rooms, status. */
export function PropertyCard({ property, onOpen, onMap, style, className = "", eager = false }: Props) {
  const image = propertyImage(property, 640)
  const status = property.status ?? "AVAILABLE"
  return (
    <article
      style={style}
      className={`group flex flex-col overflow-hidden rounded-2xl border border-ab-border bg-ab-card shadow-sm transition duration-300 hover:-translate-y-1 hover:border-ab-accent/50 hover:shadow-xl ${className}`}
    >
      <button type="button" onClick={() => onOpen(property)} className="relative block aspect-[4/3] overflow-hidden bg-ab-card-2 text-left" aria-label={`View ${property.title}`}>
        {image ? (
          <img
            src={image}
            alt=""
            loading={eager ? "eager" : "lazy"}
            decoding="async"
            width={640}
            height={480}
            className="h-full w-full object-cover transition duration-700 ease-out group-hover:scale-105"
          />
        ) : (
          <span className="flex h-full w-full flex-col items-center justify-center text-ab-faint">
            <Building className="h-10 w-10 opacity-60" />
            <span className="mt-1 text-xs">No photo yet</span>
          </span>
        )}
        <span className={`absolute left-3 top-3 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide shadow ${STATUS_STYLES[status] ?? "bg-ab-card text-ab-text"}`}>
          {status}
        </span>
        {property.category && (
          <span className="absolute right-3 top-3 rounded-full bg-black/55 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-white backdrop-blur">
            {categoryLabel(property.category)}
          </span>
        )}
      </button>
      <div className="flex flex-1 flex-col p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
          <p className="text-xl font-bold text-ab-accent">{peso(property.price_total)}</p>
          {property.monthly_rate ? (
            <p className="whitespace-nowrap text-xs font-medium text-ab-muted">
              <span className="font-semibold text-ab-text">{peso(property.monthly_rate)}</span>/mo
            </p>
          ) : null}
        </div>
        <h3 className="mt-1 line-clamp-2 text-base font-semibold leading-snug text-ab-text">{property.title}</h3>
        <p className="mt-1 flex items-center gap-1 text-sm text-ab-muted">
          <MapPin className="h-3.5 w-3.5 shrink-0 text-ab-faint" />
          <span className="truncate">{property.village_name || "Location to be confirmed"}</span>
        </p>
        <ul className="mt-3 flex gap-1.5 text-sm text-ab-muted">
          <li className="flex flex-auto items-center justify-center gap-1.5 whitespace-nowrap rounded-lg bg-ab-card-2 px-2 py-1.5" title="Bedrooms">
            <BedDouble className="h-4 w-4 shrink-0 text-ab-faint" />
            <span className="font-semibold text-ab-text">{property.num_bedrooms ?? "—"}</span> bd
          </li>
          <li className="flex flex-auto items-center justify-center gap-1.5 whitespace-nowrap rounded-lg bg-ab-card-2 px-2 py-1.5" title="Bathrooms">
            <Bath className="h-4 w-4 shrink-0 text-ab-faint" />
            <span className="font-semibold text-ab-text">{property.num_bathrooms ?? "—"}</span> ba
          </li>
          {lotAreaShort(property.lot_area_sqm) && (
            <li className="flex flex-auto items-center justify-center gap-1.5 whitespace-nowrap rounded-lg bg-ab-card-2 px-2 py-1.5" title="Lot area">
              <LandPlot className="h-4 w-4 shrink-0 text-ab-faint" />
              <span className="font-semibold text-ab-text">{lotAreaShort(property.lot_area_sqm)}</span>
            </li>
          )}
        </ul>
        <div className="mt-auto flex gap-2 pt-4">
          <button type="button" onClick={() => onOpen(property)} className="flex-1 rounded-xl bg-ab-accent px-3 py-2 text-sm font-semibold text-ab-ink transition hover:bg-ab-accent-hover">
            View Property
          </button>
          {onMap && property.lat != null && (
            <button type="button" onClick={() => onMap(property)} className="rounded-xl border border-ab-border-strong px-3 py-2 text-sm font-semibold text-ab-text transition hover:bg-ab-hover">
              Map
            </button>
          )}
        </div>
      </div>
    </article>
  )
}
