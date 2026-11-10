// Pin a place on the map: search an address (or just move the map), then
// click to drop the pin, or drag it. Used for a property's location and for
// where an agent is based (buyers see the agents nearest a property).
import { useEffect, useRef, useState, type FormEvent } from "react"
import { MapContainer, TileLayer, useMap, useMapEvents } from "react-leaflet"
import L from "leaflet"
import "leaflet/dist/leaflet.css"
import { Check, LoaderCircle, LocateFixed, Map as MapIcon, MapPin, Satellite, Search, X } from "lucide-react"
import { SATELLITE_ATTRIBUTION, SATELLITE_MAX_ZOOM, SATELLITE_TILES, STREET_TILES, type Basemap } from "@/lib/mapTiles"
import { Button } from "./ui"
import { useStaffAuth } from "./staffContext"
import { t } from "./i18n"

export type PickedLocation = { lat: number; lng: number; address: string | null }
type Place = { name: string; address: string; lat: number; lng: number }

const PH_CENTER: [number, number] = [14.5995, 120.9842]
const PIN = L.divIcon({
  className: "location-picker-pin",
  html: `<svg width="36" height="46" viewBox="0 0 36 46" aria-hidden="true">
    <path d="M18 44C16.8 42.4 4 28.6 4 18a14 14 0 0 1 28 0c0 10.6-12.8 24.4-14 26Z" fill="#dc2626" stroke="#fff" stroke-width="3" stroke-linejoin="round"/>
    <circle cx="18" cy="18" r="5" fill="#fff"/></svg>`,
  iconSize: [36, 46],
  iconAnchor: [18, 44],
})

/** The pin: dropped by clicking the map, moved by dragging. */
function PinLayer({ position, onMove }: { position: [number, number] | null; onMove: (lat: number, lng: number) => void }) {
  const map = useMap()
  const marker = useRef<L.Marker | null>(null)
  useMapEvents({ click: (event) => onMove(event.latlng.lat, event.latlng.lng) })
  useEffect(() => {
    if (!position) {
      marker.current?.remove()
      marker.current = null
      return
    }
    if (!marker.current) {
      marker.current = L.marker(position, { icon: PIN, draggable: true, keyboard: true, title: t("Property location") }).addTo(map)
      marker.current.on("dragend", () => {
        const at = marker.current!.getLatLng()
        onMove(at.lat, at.lng)
      })
    } else {
      marker.current.setLatLng(position)
    }
  }, [map, position, onMove])
  useEffect(() => () => { marker.current?.remove() }, [])
  return null
}

function FlyTo({ target }: { target: { at: [number, number]; zoom: number; n: number } | null }) {
  const map = useMap()
  useEffect(() => {
    if (target) map.flyTo(target.at, target.zoom, { duration: 0.8 })
  }, [map, target])
  return null
}

export function LocationPicker({ title, initial, initialQuery, onClose, onPick }: {
  title: string
  initial: { lat: number; lng: number } | null
  initialQuery?: string
  onClose: () => void
  onPick: (picked: PickedLocation) => void
}) {
  const { api } = useStaffAuth()
  const [pin, setPin] = useState<[number, number] | null>(initial ? [initial.lat, initial.lng] : null)
  const [query, setQuery] = useState(initialQuery ?? "")
  const [results, setResults] = useState<Place[]>([])
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState("")
  const [address, setAddress] = useState<string | null>(null)
  const [basemap, setBasemap] = useState<Basemap>("map")
  const [fly, setFly] = useState<{ at: [number, number]; zoom: number; n: number } | null>(null)
  const searched = useRef(false)
  const flyTo = (at: [number, number], zoom: number) => setFly((previous) => ({ at, zoom, n: (previous?.n ?? 0) + 1 }))

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose()
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  const search = async (event?: FormEvent) => {
    event?.preventDefault()
    if (query.trim().length < 2) return
    setSearching(true)
    setError("")
    try {
      const reply = await api<{ results: Place[] }>(`/map/geocode?q=${encodeURIComponent(query.trim())}`)
      setResults(reply.results)
      if (!reply.results.length) setError(t("No place found. Try a shorter address (barangay, city), or move the map and click the spot."))
      else flyTo([reply.results[0].lat, reply.results[0].lng], 16)
    } catch (searchError) {
      setError(t((searchError as Error).message))
    } finally {
      setSearching(false)
    }
  }

  // Open on the address already typed in the form, when there's no pin yet.
  useEffect(() => {
    if (!initial && initialQuery && initialQuery.trim().length >= 2 && !searched.current) {
      searched.current = true
      void search()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // The pin's address, so the form can fill the location field.
  useEffect(() => {
    if (!pin) return
    let alive = true
    const timer = window.setTimeout(async () => {
      try {
        const reply = await api<{ result: { address: string } | null }>(`/map/reverse-geocode?lat=${pin[0]}&lng=${pin[1]}`)
        if (alive) setAddress(reply.result?.address ?? null)
      } catch {
        if (alive) setAddress(null)
      }
    }, 500)
    return () => { alive = false; window.clearTimeout(timer) }
  }, [api, pin])

  const place = (lat: number, lng: number) => setPin([Number(lat.toFixed(6)), Number(lng.toFixed(6))])
  const choose = (result: Place) => {
    place(result.lat, result.lng)
    flyTo([result.lat, result.lng], 18)
    setResults([])
  }
  const here = () => {
    if (!navigator.geolocation) return setError(t("This device can't share its location."))
    navigator.geolocation.getCurrentPosition(
      (position) => { place(position.coords.latitude, position.coords.longitude); flyTo([position.coords.latitude, position.coords.longitude], 18) },
      () => setError(t("Couldn't get this device's location. Search the address instead.")),
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  return (
    <div className="fixed inset-0 z-[90] flex flex-col bg-ab-bg" role="dialog" aria-modal="true" aria-label={title}>
      <header className="flex flex-wrap items-center gap-2 border-b border-ab-border bg-ab-sidebar px-4 py-3">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-lg font-extrabold">{title}</h2>
          <p className="text-xs text-ab-muted">{t("Search the address or move the map, then click the exact spot to drop the red pin. Drag the pin to adjust.")}</p>
        </div>
        <button type="button" onClick={() => setBasemap((value) => (value === "satellite" ? "map" : "satellite"))}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-ab-border-strong px-3 text-sm font-semibold hover:bg-ab-hover">
          {basemap === "satellite" ? <MapIcon className="h-4 w-4" /> : <Satellite className="h-4 w-4" />}
          {basemap === "satellite" ? t("Street map") : t("Satellite")}
        </button>
        <button type="button" onClick={onClose} aria-label={t("Close")} className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><X className="h-5 w-5" /></button>
      </header>

      <form onSubmit={search} className="relative flex gap-2 border-b border-ab-border bg-ab-card px-4 py-2">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ab-faint" />
          <input aria-label={t("Address or place")} value={query} onChange={(e) => setQuery(e.target.value)} autoFocus
            placeholder={t("e.g. Brgy. Salitran, Dasmariñas, Cavite")}
            className="block min-h-10 w-full rounded-xl border border-ab-border bg-ab-input pl-9 pr-3 text-sm focus:border-ab-accent focus:outline-none" />
        </div>
        <Button type="submit" disabled={searching}>{searching ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />} {t("Search")}</Button>
        <Button onClick={here} title={t("Use this device's location")}><LocateFixed className="h-4 w-4" /><span className="hidden sm:inline"> {t("I'm here")}</span></Button>
        {results.length > 1 && (
          <ul className="absolute left-4 right-4 top-full z-[1000] mt-1 max-h-60 overflow-y-auto rounded-xl border border-ab-border bg-ab-card shadow-xl">
            {results.map((result) => (
              <li key={`${result.lat},${result.lng}`}>
                <button type="button" onClick={() => choose(result)} className="block w-full px-3 py-2 text-left text-sm hover:bg-ab-hover">
                  <span className="font-semibold">{result.name}</span>
                  <span className="block truncate text-xs text-ab-faint">{result.address}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </form>
      {error && <p role="alert" className="border-b border-ab-border bg-ab-warning/10 px-4 py-2 text-sm">{error}</p>}

      <div className="relative min-h-0 flex-1">
        <MapContainer center={pin ?? PH_CENTER} zoom={pin ? 18 : 11} maxZoom={20} className="h-full w-full" zoomControl>
          {basemap === "satellite"
            ? <TileLayer key="sat" url={SATELLITE_TILES} maxNativeZoom={SATELLITE_MAX_ZOOM} maxZoom={20} attribution={SATELLITE_ATTRIBUTION} />
            : <TileLayer key="osm" url={STREET_TILES} maxNativeZoom={19} maxZoom={20} attribution="&copy; OpenStreetMap contributors" />}
          <PinLayer position={pin} onMove={place} />
          <FlyTo target={fly} />
        </MapContainer>
      </div>

      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-ab-border bg-ab-card px-4 py-3">
        <p className="min-w-0 flex-1 text-sm">
          {pin ? (
            <>
              <MapPin className="mr-1 inline h-4 w-4 text-ab-danger" aria-hidden />
              <span className="font-semibold">{address ?? t("Pinned")}</span>
              <span className="block text-xs text-ab-faint tabular-nums">{pin[0].toFixed(6)}, {pin[1].toFixed(6)}</span>
            </>
          ) : <span className="text-ab-muted">{t("No pin yet: click the map where it is.")}</span>}
        </p>
        <span className="flex gap-2">
          <Button onClick={onClose}>{t("Cancel")}</Button>
          <Button variant="primary" disabled={!pin} onClick={() => pin && onPick({ lat: pin[0], lng: pin[1], address })}>
            <Check className="h-4 w-4" /> {t("Use this location")}
          </Button>
        </span>
      </footer>
    </div>
  )
}
