import React, { useEffect, useMemo, useRef, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { Layers, LocateFixed, MapPinOff, Minus, Plus } from 'lucide-react';
import type { MapProps, NearbyEstablishmentsMap, RouteOption, TrafficLevel } from '../types';
import { publicUrl } from '../config';
import { formatKm, formatMinutes, trafficTileUrl } from '@/lib/mapApi';

import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

// Leaflet finishes a zoom animation on a timer; if the map was removed in
// the meantime (navigating away mid-zoom) its pane is gone and Leaflet
// throws "_leaflet_pos". Skip that callback on a removed map.
type ZoomEndPatch = { _onZoomTransitionEnd: () => void; _mapPane?: HTMLElement };
const mapProto = L.Map.prototype as unknown as ZoomEndPatch;
const onZoomTransitionEnd = mapProto._onZoomTransitionEnd;
mapProto._onZoomTransitionEnd = function (this: ZoomEndPatch) {
  if (this._mapPane) onZoomTransitionEnd.call(this);
};

const EMOJI_META: Record<string, string> = {
  hospitals: '🏥',
  malls: '🛍️',
  markets: '🛒',
  parks: '🌳',
  schools: '🎓',
  transit: '🚆',
};

const CATEGORY_LABELS: Record<string, string> = {
  hospitals: 'Hospital / Medical',
  malls: 'Shopping Mall',
  markets: 'Supermarket / Market',
  parks: 'Park / Recreation',
  schools: 'School / University',
  transit: 'Transit Station',
};

const HOUSE_SVG =
  '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 3 2 11h3v9h5v-6h4v6h5v-9h3z"/></svg>';

const DEFAULT_CENTER: [number, number] = [14.5995, 120.9842]; // Metro Manila

// Temporary UI setting: hide map provider attribution during development.
// Set to true before public/production deployment to restore the required credits.
const SHOW_MAP_ATTRIBUTION = false;

// Congested stretches reported by the live-traffic provider, drawn over the route.
const TRAFFIC_COLORS: Record<TrafficLevel, string> = {
  slow: '#F5A623',
  moderate: '#F07C1B',
  heavy: '#D0021B',
  closed: '#7A0B0B',
};
const TRAFFIC_LABELS: Record<TrafficLevel, string> = {
  slow: 'Slow traffic',
  moderate: 'Moderate traffic',
  heavy: 'Heavy traffic',
  closed: 'Road closed / stopped',
};

const shortPrice = (value: number | null | undefined) => {
  const amount = Number(value);
  if (!Number.isFinite(amount) || amount <= 0) return '—';
  if (amount >= 1_000_000) return `₱${(amount / 1_000_000).toFixed(amount >= 10_000_000 ? 0 : 1).replace(/\.0$/, '')}M`;
  if (amount >= 1_000) return `₱${Math.round(amount / 1_000)}K`;
  return `₱${amount.toLocaleString()}`;
};

// Property pin: a price chip, highlighted when selected (styles in index.css).
// Reserved / sold listings stay on the map, muted and labelled with their status.
const propertyPin = (price: number, selected: boolean, status?: string) => {
  const state = String(status ?? 'AVAILABLE').toUpperCase();
  const tag = state === 'AVAILABLE' ? '' : `<em class="ab-pin-status">${state === 'SOLD' ? 'Sold' : 'Reserved'}</em>`;
  return L.divIcon({
    className: 'ab-pin ab-pin-wrap',
    html: `<div class="ab-price-pin${selected ? ' is-selected' : ''}${tag ? ' is-unavailable' : ''}">${HOUSE_SVG}<span>${shortPrice(price)}</span>${tag}</div>`,
    iconSize: [0, 0],
    iconAnchor: [0, 0],
    popupAnchor: [0, -30],
  });
};

const placePin = (emoji: string) =>
  L.divIcon({
    className: 'ab-pin',
    html: `<div class="ab-place-pin"><span>${emoji}</span></div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 40],
    popupAnchor: [0, -38],
  });
const WorkplaceIcon = placePin('🏢');
const MeIcon = L.divIcon({ className: '', html: '<div class="ab-me-dot"></div>', iconSize: [18, 18], iconAnchor: [9, 9] });

const propertyCover = (property: { photos?: string[]; media?: string[] }) =>
  property.photos?.[0] ?? (property.media?.[0] ? publicUrl(property.media[0]) : null);

const createCustomEmojiIcon = (emoji: string) =>
  L.divIcon({
    className: 'custom-establishment-pin',
    html: `<div style="
      background-color: var(--color-ab-card-2);
      border: 2px solid var(--color-ab-border-strong);
      border-radius: 50%;
      width: 30px;
      height: 30px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    ">${emoji}</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });

const cssVar = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** Keep Leaflet's size in sync with its container (panels open/close). */
const MapResizer: React.FC = () => {
  const map = useMap();
  useEffect(() => {
    map.attributionControl?.setPosition('topleft');
    map.attributionControl?.setPrefix(false);
    const container = map.getContainer();
    let frame = 0;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => map.invalidateSize());
    });
    observer.observe(container);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
      // Leaving the page mid-animation would otherwise make Leaflet touch
      // removed panes ("_leaflet_pos" errors). The map may already be
      // removed by react-leaflet at this point; then there's nothing to stop.
      try {
        map.stop();
      } catch {
        /* already removed */
      }
    };
  }, [map]);
  return null;
};

/** Camera: fit the selected route, else fly to the focused point / property. */
const CameraController: React.FC<{
  route: RouteOption | null;
  target: { lat: number; lng: number; zoom?: number } | null;
  bottomInset: number;
}> = ({ route, target, bottomInset }) => {
  const map = useMap();
  const routeKey = route ? `${route.id}:${route.geometry.length}:${route.distance_m}` : null;
  useEffect(() => {
    if (!route || route.geometry.length < 2) return;
    map.fitBounds(L.latLngBounds(route.geometry), {
      paddingTopLeft: [40, 90],
      paddingBottomRight: [40, 40 + bottomInset],
      maxZoom: 16,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, routeKey]);
  const targetKey = target ? `${target.lat},${target.lng},${target.zoom ?? ''}` : null;
  useEffect(() => {
    if (!target || route) return;
    map.flyTo([target.lat, target.lng], Math.max(map.getZoom(), target.zoom ?? 14), { duration: 0.6 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, targetKey]);
  return null;
};

/** Frame every listed property whenever the result set changes (initial load,
 *  filters, assistant recommendations), unless a property is selected. */
const FitToProperties: React.FC<{ points: [number, number][]; paused: boolean; topInset: number; bottomInset: number }> = ({
  points,
  paused,
  topInset,
  bottomInset,
}) => {
  const map = useMap();
  const key = points.map(([lat, lng]) => `${lat.toFixed(5)},${lng.toFixed(5)}`).sort().join('|');
  useEffect(() => {
    if (paused || points.length === 0) return;
    if (points.length === 1) {
      map.setView(points[0], 15);
      return;
    }
    map.fitBounds(L.latLngBounds(points), {
      paddingTopLeft: [30, topInset],
      paddingBottomRight: [70, 30 + bottomInset],
      maxZoom: 15,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, key]);
  return null;
};

const PickHandler: React.FC<{ active: boolean; onPick?: (point: { lat: number; lng: number }) => void }> = ({
  active,
  onPick,
}) => {
  const map = useMap();
  useEffect(() => {
    map.getContainer().style.cursor = active ? 'crosshair' : '';
  }, [map, active]);
  useMapEvents({
    click: (event) => {
      if (active && onPick) onPick({ lat: event.latlng.lat, lng: event.latlng.lng });
    },
  });
  return null;
};

const controlButton =
  'flex h-11 w-11 items-center justify-center rounded-xl border shadow-md transition active:scale-95 focus-visible:outline-2 focus-visible:outline-ab-accent';
// On: filled lime with dark ink (like the selected chips); off: plain card.
const controlState = (active: boolean) =>
  active
    ? 'border-ab-accent bg-ab-accent text-ab-ink shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-ab-accent)_30%,transparent)] hover:bg-ab-accent-hover'
    : 'border-ab-border bg-ab-card text-ab-text hover:bg-ab-hover';
const zoomButton =
  'flex h-11 w-11 items-center justify-center text-ab-text transition hover:bg-ab-hover active:bg-ab-accent active:text-ab-ink';

/** Floating controls rendered inside the map (clicks don't reach the map). */
const MapControls: React.FC<{
  onLocate?: () => void;
  onToggleTraffic?: () => void;
  showTraffic: boolean;
  trafficAvailable: boolean;
  onClearNearby?: () => void;
  hasSelection: boolean;
  located: boolean;
  top: number;
  legend?: React.ReactNode;
}> = ({ onLocate, onToggleTraffic, showTraffic, trafficAvailable, onClearNearby, hasSelection, located, top, legend }) => {
  const map = useMap();
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    L.DomEvent.disableClickPropagation(ref.current);
    L.DomEvent.disableScrollPropagation(ref.current);
  }, []);
  return (
    <div ref={ref} style={{ top }} className="absolute right-3 z-[1000] flex flex-col items-end gap-2">
      <div className="flex flex-col overflow-hidden rounded-xl border border-ab-border bg-ab-card shadow-md">
        <button type="button" onClick={() => map.zoomIn()} className={zoomButton} aria-label="Zoom in">
          <Plus className="h-5 w-5" />
        </button>
        <span className="h-px bg-ab-border" />
        <button type="button" onClick={() => map.zoomOut()} className={zoomButton} aria-label="Zoom out">
          <Minus className="h-5 w-5" />
        </button>
      </div>
      {onLocate && (
        <button
          type="button"
          onClick={onLocate}
          aria-pressed={located}
          className={`${controlButton} ${controlState(located)}`}
          aria-label="Show my location"
          title={located ? 'Showing your location — click to re-center' : 'Show my location'}
        >
          <LocateFixed className="h-5 w-5" />
        </button>
      )}
      {onToggleTraffic && (
        <button
          type="button"
          onClick={onToggleTraffic}
          aria-pressed={showTraffic}
          aria-label="Traffic layer"
          title={trafficAvailable ? 'Show live traffic' : 'Live traffic data is not available'}
          className={`${controlButton} ${controlState(showTraffic)}`}
        >
          <Layers className="h-5 w-5" />
        </button>
      )}
      {hasSelection && onClearNearby && (
        <button
          type="button"
          onClick={onClearNearby}
          aria-label="Clear selection"
          title="Deselect the property: hides its nearby places and commute route"
          className="flex min-h-11 min-w-11 items-center justify-center gap-1.5 rounded-xl border border-ab-border bg-ab-card px-3 text-xs font-semibold text-ab-text shadow-md transition hover:bg-ab-hover hover:text-ab-danger active:scale-95"
        >
          <MapPinOff className="h-4 w-4" /> <span className="hidden sm:inline">Clear selection</span>
        </button>
      )}
      {legend}
    </div>
  );
};

export const PropertyMap: React.FC<MapProps> = ({
  properties,
  selectedProperty,
  workplaceLocation,
  onSelectProperty,
  onClearNearby,
  theme,
  commute,
  routeSelection,
  onSelectRoute,
  showTraffic = false,
  trafficAvailable = false,
  trafficLegend = [],
  onToggleTraffic,
  currentPosition,
  onLocate,
  isPickingLocation = false,
  onPickLocation,
  focusPoint,
  bottomInset = 0,
  controlsTop = 12,
  showClearInControls = true,
  legendInControls = false,
}) => {
  const validProperties = properties.filter((p) => p.lat !== null && p.lng !== null);
  const [initialCenter] = useState<[number, number]>(() =>
    validProperties[0]?.lat != null && validProperties[0]?.lng != null
      ? [validProperties[0].lat, validProperties[0].lng]
      : DEFAULT_CENTER,
  );

  let selectedNearby: NearbyEstablishmentsMap = {};
  if (selectedProperty?.nearby_establishments) {
    const raw = selectedProperty.nearby_establishments;
    if (typeof raw === 'string') {
      try {
        selectedNearby = JSON.parse(raw);
      } catch {
        selectedNearby = {};
      }
    } else if (typeof raw === 'object') {
      selectedNearby = raw;
    }
  }

  // Road-following routes from the routing provider (never a straight line).
  const modeResult = routeSelection && commute ? commute.modes[routeSelection.mode] : null;
  const routes = modeResult?.status === 'ok' ? modeResult.routes : [];
  const activeRoute = routes.find((route) => route.id === routeSelection?.routeId) ?? routes[0] ?? null;
  const isWalking = routeSelection?.mode === 'walking';

  // Route colours follow the theme; read after the theme attribute changes.
  const colors = useMemo(
    () => ({
      route: cssVar('--color-ab-route') || '#C7F000',
      casing: cssVar('--color-ab-route-casing') || '#0B0F10',
      alt: cssVar('--color-ab-route-alt') || '#6E7872',
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [theme],
  );

  const focusTarget =
    focusPoint ??
    (selectedProperty?.lat != null && selectedProperty?.lng != null
      ? { lat: selectedProperty.lat, lng: selectedProperty.lng, zoom: 15 }
      : null);

  // Live-traffic key: beside the map controls on desktop, bottom-left on phones.
  const trafficLegendCard =
    showTraffic && trafficAvailable && trafficLegend.length ? (
      <div className="rounded-xl border border-ab-border bg-ab-card px-3 py-2 text-[11px] text-ab-muted shadow-md">
        <p className="mb-1 font-semibold text-ab-text">Live traffic</p>
        {trafficLegend.map((item) => (
          <p key={item.level} className="flex items-center gap-1.5">
            <span className="h-1.5 w-5 rounded-full" style={{ background: item.color }} /> {item.label}
          </p>
        ))}
      </div>
    ) : null;

  return (
    <div className="relative h-full min-h-[300px] w-full">
      {!legendInControls && trafficLegendCard ? (
        <div className="absolute bottom-9 left-3 z-[1000]">{trafficLegendCard}</div>
      ) : null}
      {isPickingLocation && (
        <div className="pointer-events-none absolute inset-x-0 top-20 z-[1000] flex justify-center px-4">
          <p className="rounded-full bg-ab-text px-4 py-2 text-sm font-semibold text-ab-bg shadow-lg">
            Tap the map to place your workplace
          </p>
        </div>
      )}

      <MapContainer center={initialCenter} zoom={13} zoomControl={false} attributionControl={SHOW_MAP_ATTRIBUTION} className="z-0 h-full w-full rounded-xl">
        {/* OpenStreetMap tiles; darkened in CSS (.ab-dark-tiles) for the dark
            theme, shown as-is for the light theme. Keyed so the class swaps. */}
        <TileLayer
          key={theme}
          attribution={SHOW_MAP_ATTRIBUTION ? '&copy; <a href="https://www.openstreetmap.org/copyright">' : ''}
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          className={theme === 'dark' ? 'ab-dark-tiles' : ''}
        />
        {showTraffic && trafficAvailable && (
          <TileLayer
            key={`traffic-${theme}`}
            url={trafficTileUrl(theme)}
            opacity={0.9}
            zIndex={5}
            attribution={SHOW_MAP_ATTRIBUTION ? 'Traffic &copy; TomTom' : ''}
          />
        )}

        <MapResizer />
        <MapControls
          onLocate={onLocate}
          onToggleTraffic={onToggleTraffic}
          showTraffic={showTraffic}
          trafficAvailable={trafficAvailable}
          onClearNearby={onClearNearby}
          hasSelection={showClearInControls && Boolean(selectedProperty)}
          legend={legendInControls ? trafficLegendCard : null}
          located={Boolean(currentPosition)}
          top={controlsTop}
        />
        <CameraController route={activeRoute} target={focusTarget} bottomInset={bottomInset} />
        <FitToProperties
          points={validProperties.map((p) => [p.lat!, p.lng!] as [number, number])}
          paused={Boolean(selectedProperty)}
          topInset={80}
          bottomInset={bottomInset}
        />
        <PickHandler active={isPickingLocation} onPick={onPickLocation} />

        {/* 1. Alternative routes (click to select), then the active route */}
        {routes
          .filter((route) => route !== activeRoute)
          .map((route) => (
            <Polyline
              key={`alt-${routeSelection?.mode}-${route.id}`}
              positions={route.geometry}
              pathOptions={{ color: colors.alt, weight: 6, opacity: 0.75, lineCap: 'round', lineJoin: 'round' }}
              eventHandlers={{ click: () => onSelectRoute?.(route.id) }}
            >
              <Popup>
                <p className="text-xs font-semibold text-ab-text">
                  Route {route.id}: {formatKm(route.distance_m)} · {formatMinutes(route.duration_s)}
                </p>
              </Popup>
            </Polyline>
          ))}
        {activeRoute && (
          <>
            <Polyline
              key={`casing-${routeSelection?.mode}-${activeRoute.id}-${theme}`}
              positions={activeRoute.geometry}
              pathOptions={{ color: colors.casing, weight: 10, opacity: 0.9, lineCap: 'round', lineJoin: 'round' }}
              interactive={false}
            />
            <Polyline
              key={`route-${routeSelection?.mode}-${activeRoute.id}-${theme}`}
              positions={activeRoute.geometry}
              pathOptions={{
                color: colors.route,
                weight: 6,
                opacity: 1,
                lineCap: 'round',
                lineJoin: 'round',
                dashArray: isWalking ? '1 10' : undefined,
              }}
            >
              <Popup>
                <p className="text-xs font-semibold text-ab-text">
                  {modeResult?.label}: {formatKm(activeRoute.distance_m)} · {formatMinutes(activeRoute.duration_s)}
                </p>
                <p className="text-[11px] text-ab-muted">Road route from your workplace</p>
              </Popup>
            </Polyline>
          </>
        )}

        {/* Live congestion along the active route (provider data only) */}
        {activeRoute?.traffic?.segments.map((segment) => (
          <Polyline
            key={`jam-${routeSelection?.mode}-${activeRoute.id}-${segment.start}-${segment.end}`}
            positions={activeRoute.geometry.slice(segment.start, segment.end + 1)}
            pathOptions={{ color: TRAFFIC_COLORS[segment.level], weight: 6, opacity: 1, lineCap: 'round', lineJoin: 'round' }}
          >
            <Popup>
              <p className="text-xs font-semibold text-ab-text">{TRAFFIC_LABELS[segment.level]}</p>
              <p className="text-[11px] text-ab-muted">
                {segment.delay_s >= 60 ? `+${formatMinutes(segment.delay_s)} delay` : 'Under a minute of delay'}
                {segment.speed_kmh != null ? ` · ~${Math.round(segment.speed_kmh)} km/h` : ''}
              </p>
            </Popup>
          </Polyline>
        ))}

        {/* 2. Property pins */}
        {validProperties.map((prop) => {
          const cover = propertyCover(prop);
          const isSelected = selectedProperty?.listing_id === prop.listing_id;
          return (
            <Marker
              key={`${prop.listing_id}-${isSelected}`}
              position={[prop.lat!, prop.lng!]}
              icon={propertyPin(prop.price_total, isSelected, prop.status)}
              zIndexOffset={isSelected ? 1000 : 0}
              title={prop.title}
              eventHandlers={{ click: () => onSelectProperty(prop) }}
            >
              <Popup minWidth={230}>
                <div className="w-[230px] space-y-2">
                  {cover && <img src={cover} alt="" className="h-24 w-full rounded-lg object-cover" />}
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-base font-bold text-ab-accent">₱{Number(prop.price_total).toLocaleString()}</p>
                    <span className="rounded-full bg-ab-accent-soft px-2 py-0.5 text-[10px] font-bold uppercase text-ab-accent">
                      {prop.status ?? 'Available'}
                    </span>
                  </div>
                  <h4 className="text-sm font-semibold leading-snug text-ab-text">{prop.title}</h4>
                  <p className="text-xs text-ab-muted">{prop.village_name}</p>
                  <p className="text-[11px] text-ab-faint">
                    {prop.num_bedrooms ?? 0} beds · {prop.num_bathrooms ?? 0} baths
                    {prop.category ? ` · ${prop.category}` : ''}
                  </p>
                </div>
              </Popup>
            </Marker>
          );
        })}

        {/* 3. Workplace (route start) */}
        {workplaceLocation && (
          <Marker position={[workplaceLocation.lat, workplaceLocation.lng]} icon={WorkplaceIcon} zIndexOffset={900}>
            <Popup>
              <div className="p-1">
                <p className="text-xs font-bold text-ab-text">🏢 Workplace</p>
                <p className="text-[11px] text-ab-muted">{workplaceLocation.name}</p>
              </div>
            </Popup>
          </Marker>
        )}

        {/* 4. Current position (only after the user asks for it) */}
        {currentPosition && (
          <Marker position={[currentPosition.lat, currentPosition.lng]} icon={MeIcon} zIndexOffset={800}>
            <Popup>
              <p className="text-xs font-semibold text-ab-text">You are here</p>
            </Popup>
          </Marker>
        )}

        {/* 5. Establishment pins */}
        {selectedProperty?.lat &&
          selectedProperty?.lng &&
          Object.entries(selectedNearby).map(([category, items]) => {
            if (!Array.isArray(items)) return null;
            const emoji = EMOJI_META[category] || '📍';
            const categoryName = CATEGORY_LABELS[category] || category;
            const icon = createCustomEmojiIcon(emoji);

            return items.map((item, idx) => {
              // Only plot establishments with real coordinates; entries that
              // only have a distance stay in the property's Nearby list.
              if (item.lat == null || item.lng == null) return null;
              return (
                <Marker key={`establishment-${category}-${idx}`} position={[item.lat, item.lng]} icon={icon}>
                  <Popup>
                    <div className="min-w-[140px] p-1">
                      <span className="mb-1 inline-block rounded-full border border-ab-border bg-ab-card-2 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ab-muted">
                        {categoryName}
                      </span>
                      <p className="text-xs font-bold leading-tight text-ab-text">
                        {emoji} {item.name}
                      </p>
                      <p className="mt-1 text-[11px] text-ab-muted">
                        📍 <span className="font-medium text-ab-muted">{item.distance_km} km</span> away from property
                      </p>
                    </div>
                  </Popup>
                </Marker>
              );
            });
          })}
      </MapContainer>
    </div>
  );
};
