// Lot boundaries drawn on the map: GeoJSON Polygons of [lng, lat] points.
// Measurements use Turf (geodesic, on the mean earth radius): the API's
// services/lot_geometry.py uses the same formulas, so both always agree.
// They are estimates from the mapped outline, not an official survey.
import turfArea from "@turf/area"
import turfDistance from "@turf/distance"

export type Boundary = { type: "Polygon"; coordinates: number[][][] }
export type BoundaryMeasurements = { area_sqm: number; perimeter_m: number; sides_m: number[] }

/** The outline's points without the repeated closing point. */
export const corners = (boundary: Boundary): number[][] => {
  const ring = boundary.coordinates[0] ?? []
  const last = ring.length - 1
  return last > 0 && ring[0][0] === ring[last][0] && ring[0][1] === ring[last][1] ? ring.slice(0, last) : ring
}

/** A closed polygon from corner points ([lng, lat]). */
export const fromCorners = (points: number[][]): Boundary => ({ type: "Polygon", coordinates: [[...points, points[0]]] })

export function measure(boundary: Boundary): BoundaryMeasurements {
  const points = corners(boundary)
  if (points.length < 3) return { area_sqm: 0, perimeter_m: 0, sides_m: [] }
  const sides = points.map((point, i) => turfDistance(point, points[(i + 1) % points.length], { units: "meters" }))
  return {
    area_sqm: turfArea({ type: "Feature", geometry: fromCorners(points), properties: {} }),
    perimeter_m: sides.reduce((total, side) => total + side, 0),
    sides_m: sides,
  }
}

/** True when two non-neighbouring sides cross (an invalid outline). */
export function crossesItself(points: number[][]): boolean {
  const orient = (p: number[], q: number[], r: number[]) => {
    const value = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return Math.abs(value) < 1e-18 ? 0 : value > 0 ? 1 : -1
  }
  const onSegment = (p: number[], q: number[], r: number[]) =>
    Math.min(p[0], r[0]) <= q[0] && q[0] <= Math.max(p[0], r[0]) && Math.min(p[1], r[1]) <= q[1] && q[1] <= Math.max(p[1], r[1])
  const cross = (a: number[], b: number[], c: number[], d: number[]) => {
    const [o1, o2, o3, o4] = [orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)]
    if (o1 !== o2 && o3 !== o4) return true
    return (o1 === 0 && onSegment(a, c, b)) || (o2 === 0 && onSegment(a, d, b)) || (o3 === 0 && onSegment(c, a, d)) || (o4 === 0 && onSegment(c, b, d))
  }
  const n = points.length
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (j === i + 1 || (i === 0 && j === n - 1)) continue
      if (cross(points[i], points[(i + 1) % n], points[j], points[(j + 1) % n])) return true
    }
  }
  return false
}

/** "97.6 m" or "1.24 km". */
export const formatLength = (metres: number) =>
  metres >= 1000 ? `${(metres / 1000).toLocaleString("en-PH", { maximumFractionDigits: 2 })} km` : `${metres.toLocaleString("en-PH", { maximumFractionDigits: 1 })} m`

/** Leaflet [lat, lng] pairs for drawing. */
export const toLatLngs = (boundary: Boundary): [number, number][] => corners(boundary).map(([lng, lat]) => [lat, lng])

/** The lot's red outline (bright, rounded, with a see-through fill). */
export const LOT_STYLE = { color: "#E0242B", weight: 3, lineJoin: "round" as const, lineCap: "round" as const, fillColor: "#E0242B", fillOpacity: 0.1 }
