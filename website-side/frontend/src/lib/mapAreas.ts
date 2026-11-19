// The map's "unlocked areas": the places where Abellar has listed properties.
// Properties within a few kilometres of each other form one area (a town or a
// cluster of subdivisions); everything else in the Philippines stays shaded.
import type { Property } from "@/types"

export type MapArea = {
  id: string
  name: string
  center: { lat: number; lng: number }
  /** Circle that holds every property of the area, with a margin (metres). */
  radiusM: number
  properties: Property[]
}

/** What the visitor can pan to: the Philippines and its waters. */
export const PHILIPPINES_BOUNDS: [[number, number], [number, number]] = [[4.2, 115.8], [21.4, 127.2]]

const JOIN_KM = 6 // properties closer than this share an area
const MARGIN_KM = 1.2
const MIN_RADIUS_KM = 1.5

export function distanceKm(a: { lat: number; lng: number }, b: { lat: number; lng: number }) {
  const rad = Math.PI / 180
  const dLat = (b.lat - a.lat) * rad
  const dLng = (b.lng - a.lng) * rad
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2
  return 12742 * Math.asin(Math.min(1, Math.sqrt(h)))
}

/** "Brgy. Sahud Ulan, Tanza, Cavite" -> "Tanza"; "Talon Dos, Las Piñas City" -> "Las Piñas City". */
function placeName(address: string | null | undefined) {
  const parts = String(address ?? "").split(",").map((part) => part.trim()).filter(Boolean)
  if (parts.length === 0) return ""
  return parts.length >= 3 ? parts[parts.length - 2] : parts[parts.length - 1]
}

export function groupIntoAreas(properties: Property[]): MapArea[] {
  const located = properties.filter((p) => p.lat != null && p.lng != null)
  const point = (p: Property) => ({ lat: p.lat!, lng: p.lng! })

  // Join properties that are near each other (union-find).
  const parent = located.map((_, i) => i)
  const find = (i: number): number => (parent[i] === i ? i : (parent[i] = find(parent[i])))
  for (let i = 0; i < located.length; i++) {
    for (let j = i + 1; j < located.length; j++) {
      if (distanceKm(point(located[i]), point(located[j])) < JOIN_KM) parent[find(i)] = find(j)
    }
  }
  const groups = new Map<number, Property[]>()
  located.forEach((p, i) => {
    const root = find(i)
    groups.set(root, [...(groups.get(root) ?? []), p])
  })

  // Areas whose circles would overlap become one area (so the shade has clean holes).
  let areas = [...groups.values()].map(describeArea)
  for (let merged = true; merged; ) {
    merged = false
    outer: for (let i = 0; i < areas.length; i++) {
      for (let j = i + 1; j < areas.length; j++) {
        if (distanceKm(areas[i].center, areas[j].center) * 1000 < areas[i].radiusM + areas[j].radiusM) {
          const joined = describeArea([...areas[i].properties, ...areas[j].properties])
          areas = [...areas.filter((_, k) => k !== i && k !== j), joined]
          merged = true
          break outer
        }
      }
    }
  }
  return areas.sort((a, b) => b.properties.length - a.properties.length || a.name.localeCompare(b.name))
}

function describeArea(members: Property[]): MapArea {
  const center = {
    lat: members.reduce((sum, p) => sum + p.lat!, 0) / members.length,
    lng: members.reduce((sum, p) => sum + p.lng!, 0) / members.length,
  }
  const farthest = Math.max(0, ...members.map((p) => distanceKm(center, { lat: p.lat!, lng: p.lng! })))
  const names = new Map<string, number>()
  for (const p of members) {
    const name = placeName(p.village_name)
    if (name) names.set(name, (names.get(name) ?? 0) + 1)
  }
  const name = [...names.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "Abellar area"
  const ids = members.map((p) => Number(p.listing_id)).sort((a, b) => a - b)
  return {
    id: `area-${ids[0]}`,
    name,
    center,
    radiusM: Math.max(MIN_RADIUS_KM, farthest + MARGIN_KM) * 1000,
    properties: members,
  }
}

/** A circle as a polygon ring (for the holes in the shade layer). */
export function circleRing(center: { lat: number; lng: number }, radiusM: number, steps = 64): [number, number][] {
  const dLat = radiusM / 111_320
  const dLng = radiusM / (111_320 * Math.cos((center.lat * Math.PI) / 180))
  return Array.from({ length: steps }, (_, i) => {
    const angle = (i / steps) * 2 * Math.PI
    return [center.lat + dLat * Math.sin(angle), center.lng + dLng * Math.cos(angle)] as [number, number]
  })
}

/** Corners of a circle's bounding box, to frame it on the map. */
export function circleBounds(center: { lat: number; lng: number }, radiusM: number): [number, number][] {
  const dLat = radiusM / 111_320
  const dLng = radiusM / (111_320 * Math.cos((center.lat * Math.PI) / 180))
  return [[center.lat + dLat, center.lng - dLng], [center.lat - dLat, center.lng + dLng]]
}
