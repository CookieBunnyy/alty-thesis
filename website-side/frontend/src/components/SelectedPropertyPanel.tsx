import { Bath, Bed, Building, Info, MapPin, PhoneCall, X } from "lucide-react"
import { CommuteCard } from "./CommuteCard"
import { publicUrl } from "@/config"
import type { LocationPoint, Property, RouteSelection } from "@/types"
import type { CommuteState } from "@/hooks/useCommute"

type Props = {
  property: Property
  workplace: LocationPoint | null
  routeSelection: RouteSelection
  onRouteSelectionChange: (selection: RouteSelection) => void
  onSetWorkplaceClick: () => void
  onViewRoute?: () => void
  onOpenDetails: () => void
  onContactAgent: () => void
  onClose: () => void
  compact?: boolean
  commute?: CommuteState
}

const STATUS_STYLES: Record<string, string> = {
  AVAILABLE: "bg-ab-success/15 text-ab-success",
  RESERVED: "bg-ab-warning/15 text-ab-warning",
  SOLD: "bg-ab-info/15 text-ab-info",
}

/** Property → commute (DSS) → Contact Agent, for the selected pin.
 *  Reservations and purchases are recorded by agents from documents, so the
 *  website connects the client with an agent instead of transacting. */
export function SelectedPropertyPanel({
  property,
  workplace,
  routeSelection,
  onRouteSelectionChange,
  onSetWorkplaceClick,
  onViewRoute,
  onOpenDetails,
  onContactAgent,
  onClose,
  compact = false,
  commute,
}: Props) {
  const cover = property.photos?.[0] ?? (property.media?.[0] ? publicUrl(property.media[0]) : null)
  const status = property.status ?? "AVAILABLE"

  return (
    <article aria-label={`Selected property: ${property.title}`} className="space-y-4">
      <div className="relative overflow-hidden rounded-2xl border border-ab-border bg-ab-card-2">
        {cover ? (
          <img src={cover} alt="" className={`w-full object-cover ${compact ? "h-32" : "h-44"}`} />
        ) : (
          <div className={`flex w-full flex-col items-center justify-center text-ab-faint ${compact ? "h-24" : "h-36"}`}>
            <Building className="h-8 w-8 opacity-60" />
            <span className="mt-1 text-xs">No photo yet</span>
          </div>
        )}
        <button
          type="button"
          onClick={onClose}
          aria-label="Close property"
          className="absolute right-2 top-2 flex h-9 w-9 items-center justify-center rounded-full bg-ab-card/90 text-ab-text shadow backdrop-blur transition hover:bg-ab-card"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${STATUS_STYLES[status] ?? "bg-ab-card-2 text-ab-muted"}`}>
            {status}
          </span>
          {property.category && (
            <span className="rounded-full bg-ab-accent-soft px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ab-accent">
              {property.category}
            </span>
          )}
        </div>
        <h2 className="mt-2 text-lg font-bold leading-snug text-ab-text">{property.title}</h2>
        <p className="mt-1 flex items-center gap-1 text-sm text-ab-muted">
          <MapPin className="h-3.5 w-3.5 shrink-0 text-ab-faint" />
          {property.village_name}
        </p>
        <div className="mt-2 flex items-end justify-between gap-3">
          <p className="text-xl font-bold text-ab-accent">₱{Number(property.price_total).toLocaleString()}</p>
          <p className="flex items-center gap-3 text-sm text-ab-muted">
            <span className="inline-flex items-center gap-1">
              <Bed className="h-3.5 w-3.5 text-ab-faint" /> {property.num_bedrooms}
            </span>
            <span className="inline-flex items-center gap-1">
              <Bath className="h-3.5 w-3.5 text-ab-faint" /> {property.num_bathrooms}
            </span>
          </p>
        </div>
      </div>

      <CommuteCard
        property={property}
        workplace={workplace}
        onSetWorkplaceClick={onSetWorkplaceClick}
        routeSelection={routeSelection}
        onRouteSelectionChange={onRouteSelectionChange}
        onViewRoute={onViewRoute}
        commute={commute}
      />

      <div className="grid gap-2">
        <button
          type="button"
          onClick={onContactAgent}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-ab-accent px-3 text-sm font-semibold text-ab-ink transition hover:bg-ab-accent-hover"
        >
          <PhoneCall className="h-4 w-4" /> Contact Agent
        </button>
        <button
          type="button"
          onClick={onOpenDetails}
          className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl border border-ab-border bg-ab-card-2 px-3 text-sm font-medium text-ab-text transition hover:bg-ab-hover"
        >
          <Info className="h-4 w-4 text-ab-accent" /> Full details, photos & amenities
        </button>
      </div>
      <p className="text-center text-xs text-ab-faint">Agents near this property handle reservations and purchases.</p>
    </article>
  )
}
