import { useState } from "react"
import { PropertyDetailModal } from "@/components/PropertyDetailModal"
import { navigate } from "@/lib/router"
import { loadWorkplace } from "@/lib/workplace"
import type { Property } from "@/types"

const mapLink = (property: Property) => `/map?property=${encodeURIComponent(String(property.listing_id))}`

/** Property details from any page, using the existing detail modal
 *  (with Contact Agent for agents near the property). */
export function usePropertyViewer() {
  const [preview, setPreview] = useState<Property | null>(null)

  const element = (
    <PropertyDetailModal
      property={preview}
      workplaceLocation={loadWorkplace()}
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
