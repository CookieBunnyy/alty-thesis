// Where an agent is based. Buyers who press "Reserve / Purchase" on the
// website see the agents nearest the property, which needs this pin.
import { useState } from "react"
import { MapPin, TriangleAlert } from "lucide-react"
import { Button } from "./ui"
import { LocationPicker } from "./LocationPicker"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { t } from "./i18n"

type AgentPlace = { agent_id: string; full_name: string; agent_location: string | null; latitude: string | number | null; longitude: string | number | null }

export function AgentLocation({ agent, own, onSaved }: { agent: AgentPlace; own?: boolean; onSaved: () => void | Promise<void> }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const [picking, setPicking] = useState(false)
  const pinned = agent.latitude != null && agent.longitude != null

  const save = async (lat: number, lng: number, address: string | null) => {
    try {
      await api(`/agents/${encodeURIComponent(agent.agent_id)}/location`, {
        method: "PUT",
        body: JSON.stringify({ agent_location: agent.agent_location || (address ?? "").split(",").slice(0, 3).join(",").trim() || null, latitude: lat, longitude: lng }),
      })
      toast(t(own ? "Your location is set. Buyers near your area will see you." : "Location saved."))
      setPicking(false)
      await onSaved()
    } catch (saveError) {
      toast(t((saveError as Error).message), "error")
    }
  }

  return (
    <div className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3 ${pinned ? "border-ab-border" : "border-ab-warning/50 bg-ab-warning/5"}`}>
      <p className="min-w-0 text-sm">
        <span className="flex items-center gap-1.5 font-semibold">
          {pinned ? <MapPin className="h-4 w-4 text-ab-danger" aria-hidden /> : <TriangleAlert className="h-4 w-4 text-ab-warning" aria-hidden />}
          {pinned ? agent.agent_location || t("Pinned on the map") : t(own ? "Your location isn't on the map yet" : "Not on the map yet")}
        </span>
        <span className="block text-xs text-ab-muted">
          {pinned ? `${Number(agent.latitude).toFixed(5)}, ${Number(agent.longitude).toFixed(5)}`
            : t("Buyers see the agents nearest each property. Without a pin, this agent is listed as “Location not on the map”.")}
        </span>
      </p>
      <Button variant={pinned ? "secondary" : "primary"} onClick={() => setPicking(true)}><MapPin className="h-4 w-4" /> {t(pinned ? "Move pin" : "Set on map")}</Button>
      {picking && (
        <LocationPicker title={t(own ? "Where are you based?" : "Where is {name} based?", { name: agent.full_name })}
          initial={pinned ? { lat: Number(agent.latitude), lng: Number(agent.longitude) } : null}
          initialQuery={agent.agent_location ?? ""} onClose={() => setPicking(false)}
          onPick={(picked) => void save(picked.lat, picked.lng, picked.address)} />
      )}
    </div>
  )
}
