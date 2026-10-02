import { useState } from "react"
import { PropertyDetailModal } from "@/components/PropertyDetailModal"
import { navigate } from "@/lib/router"
import type { LocationPoint, Property } from "@/types"

const savedWorkplace = (): LocationPoint | null => {
  try {
    const saved = JSON.parse(window.localStorage.getItem("alty-workplace") ?? "null")
    return saved && Number.isFinite(saved.lat) && Number.isFinite(saved.lng) && saved.name ? saved : null
  } catch {
    return null
  }
}

const mapLink = (property: Property) => `/map?property=${encodeURIComponent(String(property.listing_id))}`

/** Property details from any page, using the existing detail modal
 *  (with Contact Agent for agents near the property). */
export function usePropertyViewer() {
  const [preview, setPreview] = useState<Property | null>(null)

  const element = (
    <PropertyDetailModal
      property={preview}
      workplaceLocation={savedWorkplace()}
      onSetWorkplaceClick={() => preview && navigate(mapLink(preview))}
      onClose={() => setPreview(null)}
      onViewOnMap={(property) => property && navigate(mapLink(property))}
    />
  )

  return {
    open: setPreview,
    showOnMap: (property: Property) => navigate(mapLink(property)),
    element,
  }
}
