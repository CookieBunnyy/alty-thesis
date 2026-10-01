import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import type { MapProps, NearbyEstablishmentsMap } from '../types';
import { publicUrl } from '../config';

import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

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
  '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 3 2 11h3v9h5v-6h4v6h5v-9h3z"/></svg>';

// Property pin: white rounded tile with a house (lime when selected).
const propertyPin = (selected: boolean) =>
  L.divIcon({
    className: 'ab-pin',
    html: `<div style="
      width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;
      background:${selected ? '#C7F000' : '#F2F5F0'};color:#0B0F10;
      border:2px solid ${selected ? '#0B0F10' : 'rgba(11,15,16,0.25)'};
      box-shadow:0 6px 16px rgba(0,0,0,0.45);">${HOUSE_SVG}</div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
    popupAnchor: [0, -18],
  });

const propertyCover = (property: { photos?: string[]; media?: string[] }) =>
  property.photos?.[0] ?? (property.media?.[0] ? publicUrl(property.media[0]) : null);

const createCustomEmojiIcon = (emoji: string) => {
  return L.divIcon({
    className: 'custom-establishment-pin',
    html: `<div style="
      background-color: #151B1D;
      border: 2px solid #2F393C;
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
};

// Custom workplace icon
const WorkplaceIcon = L.divIcon({
  className: 'custom-workplace-pin',
  html: `<div style="
    background-color: #0B0F10;
    color: white;
    border: 2px solid #C7F000;
    border-radius: 50%;
    width: 34px;
    height: 34px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.4);
  ">🏢</div>`,
  iconSize: [34, 34],
  iconAnchor: [17, 17],
});

const MapResizer: React.FC<{ lat: number; lng: number }> = ({ lat, lng }) => {
  const map = useMap();

  useEffect(() => {
    const container = map.getContainer();
    if (!container) return;

    const resizeObserver = new ResizeObserver(() => {
      requestAnimationFrame(() => {
        map.invalidateSize();
        map.setView([lat, lng], map.getZoom(), { animate: false });
      });
    });

    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
    };
  }, [map, lat, lng]);

  return null;
};

export const PropertyMap: React.FC<MapProps> = ({
  properties,
  selectedProperty,
  workplaceLocation,
  onSelectProperty,
  onClearNearby,
}) => {
  const validProperties = properties.filter((p) => p.lat !== null && p.lng !== null);
  const defaultCenter: [number, number] =
    validProperties.length > 0 && validProperties[0].lat && validProperties[0].lng
      ? [validProperties[0].lat, validProperties[0].lng]
      : [14.5995, 120.9842];

  const activeCenter =
    selectedProperty?.lat && selectedProperty?.lng
      ? { lat: selectedProperty.lat, lng: selectedProperty.lng }
      : validProperties.length > 0 && validProperties[0].lat && validProperties[0].lng
      ? { lat: validProperties[0].lat, lng: validProperties[0].lng }
      : { lat: defaultCenter[0], lng: defaultCenter[1] };

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

  // Point-to-point coordinates array between selected property and workplace
  const polylineCoords: [number, number][] =
    selectedProperty?.lat && selectedProperty?.lng && workplaceLocation?.lat && workplaceLocation?.lng
      ? [
          [selectedProperty.lat, selectedProperty.lng],
          [workplaceLocation.lat, workplaceLocation.lng],
        ]
      : [];

  return (
    <div className="h-full w-full relative min-h-[300px]">
      {/* Floating Control Button to Clear Establishment Pins */}
      {selectedProperty && onClearNearby && (
        <button
          onClick={onClearNearby}
          className="absolute top-3 right-3 z-[1000] flex items-center gap-1.5 bg-white/95 hover:bg-ab-card-2 text-ab-text text-xs font-semibold px-3 py-1.5 rounded-lg shadow-md border border-ab-border transition-all hover:text-ab-danger hover:shadow-lg active:scale-95"
        >
          <span>📍</span> Hide Nearby Places
        </button>
      )}

      <MapContainer
        center={defaultCenter}
        zoom={13}
        attributionControl={false}
        className="h-full w-full rounded-xl z-0"
      >
        {/* OpenStreetMap tiles, darkened in CSS (.ab-dark-tiles) to match the
            Abellar theme without needing a paid/keyed dark tile provider. */}
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          className="ab-dark-tiles"
        />

        <MapResizer lat={activeCenter.lat} lng={activeCenter.lng} />

        {/* 1. Property Pins */}
        {validProperties.map((prop) => {
          const cover = propertyCover(prop);
          return (
            <Marker
              key={prop.listing_id}
              position={[prop.lat!, prop.lng!]}
              icon={propertyPin(selectedProperty?.listing_id === prop.listing_id)}
              eventHandlers={{
                click: () => onSelectProperty(prop),
              }}
            >
              <Popup minWidth={230}>
                <div className="w-[230px] space-y-2">
                  {cover && (
                    <img src={cover} alt="" className="h-24 w-full rounded-lg object-cover" />
                  )}
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

        {/* 2. Workplace Pin */}
        {workplaceLocation && workplaceLocation.lat && workplaceLocation.lng && (
          <Marker
            position={[workplaceLocation.lat, workplaceLocation.lng]}
            icon={WorkplaceIcon}
          >
            <Popup>
              <div className="p-1">
                <p className="text-xs font-bold text-ab-text">🏢 Workplace Location</p>
                <p className="text-[11px] text-ab-muted">{workplaceLocation.name}</p>
              </div>
            </Popup>
          </Marker>
        )}

        {/* 3. Point-to-Point Commute Line */}
        {polylineCoords.length === 2 && (
          <Polyline
            positions={polylineCoords}
            pathOptions={{
              color: '#C7F000',
              weight: 4,
              dashArray: '8, 8',
              opacity: 0.85,
            }}
          />
        )}

        {/* 4. Establishment Pins */}
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
              const estLat = item.lat;
              const estLng = item.lng;

              return (
                <Marker
                  key={`establishment-${category}-${idx}`}
                  position={[estLat, estLng]}
                  icon={icon}
                >
                  <Popup>
                    <div className="p-1 min-w-[140px]">
                      <span className="inline-block px-2 py-0.5 mb-1 text-[10px] font-semibold text-ab-muted bg-ab-card-2 rounded-full border border-ab-border uppercase tracking-wider">
                        {categoryName}
                      </span>
                      <p className="text-xs font-bold text-ab-text leading-tight">
                        {emoji} {item.name}
                      </p>
                      <p className="text-[11px] text-ab-muted mt-1">
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