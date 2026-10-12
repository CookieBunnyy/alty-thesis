// Base maps: OpenStreetMap streets, and Esri World Imagery for satellite
// views (lot boundaries). Esri's imagery requires this attribution.
export type Basemap = "map" | "satellite"

export const STREET_TILES = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
export const SATELLITE_TILES = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
export const SATELLITE_ATTRIBUTION = "Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community"
export const SATELLITE_MAX_ZOOM = 19
