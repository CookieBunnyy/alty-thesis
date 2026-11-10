// How buyers find and reach an agent. On the website, "Reserve / Purchase"
// lists the agents nearest the property (needs the map pin), and signed-in
// buyers call or text them (needs the mobile number).
import { useState, type FormEvent } from "react"
import { Check, LoaderCircle, MapPin, Pencil, Phone, TriangleAlert } from "lucide-react"
import { Button } from "./ui"
import { LocationPicker } from "./LocationPicker"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { t } from "./i18n"

type AgentPlace = {
  agent_id: string; full_name: string; phone_number: string | null
  agent_location: string | null; latitude: string | number | null; longitude: string | number | null
}

function PhoneRow({ agent, own, onSaved }: { agent: AgentPlace; own?: boolean; onSaved: () => void | Promise<void> }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(agent.phone_number ?? "")
  const [busy, setBusy] = useState(false)
  const has = Boolean(agent.phone_number)

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    try {
      await api(`/agents/${encodeURIComponent(agent.agent_id)}/phone`, { method: "PUT", body: JSON.stringify({ phone_number: value.trim() || null }) })
      toast(t(own ? "Buyers can now call or text you from the website." : "Mobile number saved."))
      setEditing(false)
      await onSaved()
    } catch (saveError) {
      toast(t((saveError as Error).message), "error")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3 ${has ? "border-ab-border" : "border-ab-warning/50 bg-ab-warning/5"}`}>
      {editing ? (
        <form onSubmit={save} className="flex w-full flex-wrap items-end gap-2">
          <label className="min-w-0 flex-1 text-sm font-medium">{t("Mobile number")}
            <input autoFocus inputMode="tel" value={value} onChange={(e) => setValue(e.target.value)} placeholder="0917 123 4567"
              className="mt-1 block min-h-10 w-full rounded-xl border border-ab-border bg-ab-input px-3 text-sm focus:border-ab-accent focus:outline-none" />
          </label>
          <Button onClick={() => { setEditing(false); setValue(agent.phone_number ?? "") }} disabled={busy}>{t("Cancel")}</Button>
          <Button type="submit" variant="primary" disabled={busy}>{busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} {t("Save")}</Button>
        </form>
      ) : (
        <>
          <p className="min-w-0 text-sm">
            <span className="flex items-center gap-1.5 font-semibold">
              {has ? <Phone className="h-4 w-4 text-ab-accent" aria-hidden /> : <TriangleAlert className="h-4 w-4 text-ab-warning" aria-hidden />}
              {has ? agent.phone_number : t(own ? "Your mobile number isn't set" : "No mobile number")}
            </span>
            <span className="block text-xs text-ab-muted">
              {t("Signed-in buyers call or text this number from “Reserve / Purchase” on the website.")}
            </span>
          </p>
          <Button variant={has ? "secondary" : "primary"} onClick={() => setEditing(true)}>
            {has ? <Pencil className="h-4 w-4" /> : <Phone className="h-4 w-4" />} {t(has ? "Change number" : "Add number")}
          </Button>
        </>
      )}
    </div>
  )
}

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
    <div className="grid gap-2 lg:grid-cols-2">
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
      <PhoneRow key={agent.phone_number ?? ""} agent={agent} own={own} onSaved={onSaved} />
    </div>
  )
}
