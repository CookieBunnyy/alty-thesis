import { useState } from "react"
import { PropertyDetailModal } from "@/components/PropertyDetailModal"
import { ClientTransactionModal } from "@/components/ClientTransactionModal"
import { SignInPrompt } from "@/components/SignInPrompt"
import { useAuth } from "@/lib/auth"
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

const mapLink = (property: Property, action?: string) =>
  `/map?property=${encodeURIComponent(String(property.listing_id))}${action ? `&action=${action}` : ""}`

/** Property details from any page, using the existing detail modal and the
 *  same Reserve / Purchase rules as the map (sign in first). */
export function usePropertyViewer(onChanged?: () => void) {
  const { client } = useAuth()
  const [preview, setPreview] = useState<Property | null>(null)
  const [transaction, setTransaction] = useState<{ property: Property; type: "RESERVED" | "SOLD" } | null>(null)
  const [signInNext, setSignInNext] = useState<string | null>(null)

  const element = (
    <>
      <PropertyDetailModal
        property={preview}
        workplaceLocation={savedWorkplace()}
        onSetWorkplaceClick={() => preview && navigate(mapLink(preview))}
        onClose={() => setPreview(null)}
        onViewOnMap={(property) => property && navigate(mapLink(property))}
        onRequestTransaction={(property, type) => {
          if (client) setTransaction({ property, type })
          else setSignInNext(mapLink(property, type))
        }}
        onTransactionSubmitted={() => onChanged?.()}
      />
      {signInNext && <SignInPrompt next={signInNext} onClose={() => setSignInNext(null)} />}
      {transaction && (
        <ClientTransactionModal
          property={transaction.property}
          initialType={transaction.type}
          onClose={() => setTransaction(null)}
          onSubmitted={() => onChanged?.()}
        />
      )}
    </>
  )

  return {
    open: setPreview,
    showOnMap: (property: Property) => navigate(mapLink(property)),
    element,
  }
}
