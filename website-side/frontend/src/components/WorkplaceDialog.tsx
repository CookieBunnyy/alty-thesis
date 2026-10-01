import React, { useEffect, useRef, useState } from "react"
import { Briefcase, Crosshair, LoaderCircle, LocateFixed, MapPin, Search, X } from "lucide-react"
import { requestCurrentPosition, reversePlace, searchPlaces } from "@/lib/mapApi"
import type { LocationPoint, PlaceResult } from "@/types"

type Props = {
  current: LocationPoint | null
  onSave: (place: LocationPoint) => void
  onPickOnMap: () => void
  onClose: () => void
  onClear?: () => void
}

/** Set Workplace: search for a place, use the device location, or pick a
 *  point on the map. The chosen place is the origin of every commute route. */
export function WorkplaceDialog({ current, onSave, onPickOnMap, onClose, onClear }: Props) {
  const [query, setQuery] = useState(current?.name ?? "")
  const [results, setResults] = useState<PlaceResult[] | null>(null)
  const [busy, setBusy] = useState<"search" | "locate" | null>(null)
  const [error, setError] = useState("")
  const inputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    inputRef.current?.focus()
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose()
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  const runSearch = async (event: React.FormEvent) => {
    event.preventDefault()
    if (query.trim().length < 2) return
    setBusy("search")
    setError("")
    try {
      const places = await searchPlaces(query)
      setResults(places)
      if (places.length === 0) setError("No places matched. Try a building, street or city name.")
    } catch (searchError) {
      setResults(null)
      setError((searchError as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const useMyLocation = async () => {
    setBusy("locate")
    setError("")
    try {
      const position = await requestCurrentPosition()
      const place = await reversePlace(position.lat, position.lng).catch(() => null)
      onSave({ ...position, name: place?.name ? `Near ${place.name}` : "My current location" })
    } catch (locateError) {
      setError((locateError as Error).message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="fixed inset-0 z-[2050] flex items-end justify-center bg-black/50 backdrop-blur-sm sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="workplace-title"
        onClick={(event) => event.stopPropagation()}
        className="flex max-h-[90vh] w-full max-w-md flex-col overflow-hidden rounded-t-[1.5rem] border border-ab-border bg-ab-card shadow-2xl sm:rounded-[1.5rem]"
      >
        <div className="flex items-start justify-between gap-3 p-5 pb-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ab-faint">Workplace</p>
            <h3 id="workplace-title" className="text-xl font-semibold text-ab-text">
              {current ? "Change your workplace" : "Set your workplace"}
            </h3>
            <p className="mt-1 text-xs text-ab-muted">Commute routes and travel times start here.</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ab-card-2 text-ab-text transition hover:bg-ab-hover"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={runSearch} className="px-5">
          <label htmlFor="workplace-search" className="sr-only">
            Workplace name or address
          </label>
          <div className="flex items-center gap-2 rounded-xl border border-ab-border bg-ab-input px-3 focus-within:border-ab-accent">
            <Search className="h-4 w-4 shrink-0 text-ab-faint" />
            <input
              ref={inputRef}
              id="workplace-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="e.g. Ayala Tower One, BGC Taguig, Ortigas"
              className="min-h-11 w-full bg-transparent text-sm text-ab-text placeholder:text-ab-faint focus:outline-none"
            />
            <button
              type="submit"
              disabled={busy !== null || query.trim().length < 2}
              className="shrink-0 rounded-lg bg-ab-accent px-3 py-1.5 text-xs font-semibold text-ab-ink transition hover:bg-ab-accent-hover disabled:opacity-50"
            >
              {busy === "search" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : "Search"}
            </button>
          </div>
        </form>

        <div className="grid grid-cols-2 gap-2 px-5 pt-3">
          <button
            type="button"
            onClick={useMyLocation}
            disabled={busy !== null}
            className="flex min-h-11 items-center justify-center gap-2 rounded-xl border border-ab-border bg-ab-card-2 px-3 text-sm font-medium text-ab-text transition hover:bg-ab-hover disabled:opacity-60"
          >
            {busy === "locate" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <LocateFixed className="h-4 w-4 text-ab-accent" />}
            Current location
          </button>
          <button
            type="button"
            onClick={onPickOnMap}
            className="flex min-h-11 items-center justify-center gap-2 rounded-xl border border-ab-border bg-ab-card-2 px-3 text-sm font-medium text-ab-text transition hover:bg-ab-hover"
          >
            <Crosshair className="h-4 w-4 text-ab-accent" />
            Pick on map
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-3">
          {error && (
            <p role="alert" className="mb-2 rounded-lg border border-ab-warning/40 bg-ab-warning/10 px-3 py-2 text-xs text-ab-warning">
              {error}
            </p>
          )}
          {results && results.length > 0 && (
            <ul className="space-y-1.5" aria-label="Matching places">
              {results.map((place) => (
                <li key={`${place.lat},${place.lng}`}>
                  <button
                    type="button"
                    onClick={() => onSave({ lat: place.lat, lng: place.lng, name: place.name })}
                    className="flex w-full items-start gap-2.5 rounded-xl border border-ab-border bg-ab-card-2 p-3 text-left transition hover:border-ab-accent hover:bg-ab-hover"
                  >
                    <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-ab-accent" />
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold text-ab-text">{place.name}</span>
                      <span className="line-clamp-2 text-xs text-ab-muted">{place.address}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {!results && !error && current && (
            <div className="flex items-center gap-2.5 rounded-xl border border-ab-border bg-ab-card-2 p-3 text-sm">
              <Briefcase className="h-4 w-4 shrink-0 text-ab-accent" />
              <span className="min-w-0 flex-1 truncate text-ab-text">{current.name}</span>
              {onClear && (
                <button type="button" onClick={onClear} className="shrink-0 text-xs font-semibold text-ab-danger hover:underline">
                  Remove
                </button>
              )}
            </div>
          )}
        </div>

        <p className="border-t border-ab-border px-5 py-2.5 text-[10px] text-ab-faint">
          Place search © OpenStreetMap contributors (Nominatim). Your location is only read when you tap “Current location”.
        </p>
      </div>
    </div>
  )
}
