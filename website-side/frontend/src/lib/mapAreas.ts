// Province boundaries are derived from geoBoundaries PHL ADM2 (CC BY 3.0 IGO),
// sourced from NAMRIA, PSA, and OCHA Philippines.
import type { Feature, MultiPolygon, Polygon, Position } from "geojson"
import type { Property } from "@/types"
import provinceBoundaries from "./philippinesAdmin2.json"

type BoundaryProperties = { shapeName: string; shapeID: string }
type ProvinceBoundary = Feature<Polygon | MultiPolygon, BoundaryProperties>

export type MapArea = {
  id: string
  name: string
  center: { lat: number; lng: number }
  bounds: [[number, number], [number, number]]
  boundary: ProvinceBoundary
  properties: Property[]
}

/** Tight bounds for the Philippines map, excluding most surrounding countries. */
export const PHILIPPINES_BOUNDS: [[number, number], [number, number]] = [[4.4, 116.7], [21.3, 126.8]]

export function groupIntoAreas(properties: Property[]): MapArea[] {
  const located = properties.filter((p) => p.lat != null && p.lng != null)
  const features = provinceBoundaries.features as ProvinceBoundary[]
  const grouped = new Map<string, { boundary: ProvinceBoundary; properties: Property[] }>()

  for (const property of located) {
    const boundary = features.find((feature) => containsPoint(feature, property.lng!, property.lat!))
    if (!boundary) continue
    const group = grouped.get(boundary.properties.shapeID) ?? { boundary, properties: [] }
    group.properties.push(property)
    grouped.set(boundary.properties.shapeID, group)
  }

  return [...grouped.values()]
    .map(({ boundary, properties: members }) => {
      const bounds = boundaryBounds(boundary)
      return {
        id: `province-${boundary.properties.shapeID}`,
        name: boundary.properties.shapeName,
        center: {
          lat: members.reduce((sum, p) => sum + p.lat!, 0) / members.length,
          lng: members.reduce((sum, p) => sum + p.lng!, 0) / members.length,
        },
        bounds,
        boundary,
        properties: members,
      }
    })
    .sort((a, b) => b.properties.length - a.properties.length || a.name.localeCompare(b.name))
}

function containsPoint(feature: ProvinceBoundary, longitude: number, latitude: number) {
  const polygons = feature.geometry.type === "Polygon" ? [feature.geometry.coordinates] : feature.geometry.coordinates
  return polygons.some((rings) => {
    if (!containsPointInRing(longitude, latitude, rings[0])) return false
    return !rings.slice(1).some((ring) => containsPointInRing(longitude, latitude, ring))
  })
}

function containsPointInRing(longitude: number, latitude: number, ring: Position[]) {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    if ((yi > latitude) !== (yj > latitude) && longitude < ((xj - xi) * (latitude - yi)) / (yj - yi) + xi) {
      inside = !inside
    }
  }
  return inside
}

function boundaryBounds(feature: ProvinceBoundary): [[number, number], [number, number]] {
  const polygons = feature.geometry.type === "Polygon" ? [feature.geometry.coordinates] : feature.geometry.coordinates
  let south = Infinity
  let west = Infinity
  let north = -Infinity
  let east = -Infinity
  for (const polygon of polygons) {
    for (const ring of polygon) {
      for (const [longitude, latitude] of ring) {
        south = Math.min(south, latitude)
        west = Math.min(west, longitude)
        north = Math.max(north, latitude)
        east = Math.max(east, longitude)
      }
    }
  }
  return [[south, west], [north, east]]
}

/** Corners of a circle's bounding box, to frame it on the map. */
export function circleBounds(center: { lat: number; lng: number }, radiusM: number): [number, number][] {
  const dLat = radiusM / 111_320
  const dLng = radiusM / (111_320 * Math.cos((center.lat * Math.PI) / 180))
  return [[center.lat + dLat, center.lng - dLng], [center.lat - dLat, center.lng + dLng]]
}
