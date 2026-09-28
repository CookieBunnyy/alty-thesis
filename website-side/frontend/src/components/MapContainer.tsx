import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import type { MapProps, NearbyEstablishmentsMap } from '../types';

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

const createCustomEmojiIcon = (emoji: string) => {
  return L.divIcon({
    className: 'custom-establishment-pin',
    html: `<div style="
      background-color: white;
      border: 2px solid #0f172a;
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
    background-color: #0f172a;
    color: white;
    border: 2px solid #0284c7;
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
          className="absolute top-3 right-3 z-[1000] flex items-center gap-1.5 bg-white/95 hover:bg-white text-slate-800 text-xs font-semibold px-3 py-1.5 rounded-lg shadow-md border border-slate-200 transition-all hover:text-red-600 hover:shadow-lg active:scale-95"
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
        <TileLayer
          attribution=""
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapResizer lat={activeCenter.lat} lng={activeCenter.lng} />

        {/* 1. Property Pins */}
        {validProperties.map((prop) => (
          <Marker
            key={prop.listing_id}
            position={[prop.lat!, prop.lng!]}
            eventHandlers={{
              click: () => onSelectProperty(prop),
            }}
          >
            <Popup>
              <div className="p-1 max-w-xs">
                <h4 className="font-bold text-sm">{prop.title}</h4>
                <p className="text-xs text-gray-600">{prop.village_name}</p>
                <p className="text-sm font-semibold text-emerald-600 mt-1">
                  ₱{prop.price_total.toLocaleString()}
                </p>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* 2. Workplace Pin */}
        {workplaceLocation && workplaceLocation.lat && workplaceLocation.lng && (
          <Marker
            position={[workplaceLocation.lat, workplaceLocation.lng]}
            icon={WorkplaceIcon}
          >
            <Popup>
              <div className="p-1">
                <p className="text-xs font-bold text-slate-900">🏢 Workplace Location</p>
                <p className="text-[11px] text-slate-600">{workplaceLocation.name}</p>
              </div>
            </Popup>
          </Marker>
        )}

        {/* 3. Point-to-Point Commute Line */}
        {polylineCoords.length === 2 && (
          <Polyline
            positions={polylineCoords}
            pathOptions={{
              color: '#0284c7',
              weight: 4,
              dashArray: '8, 8',
              opacity: 0.85,
            }}
          />
        )}

        {/* 4. Establishment Pins */}
        {selectedProperty?.lat &&
          selectedProperty?.lng &&
          Object.entries(selectedNearby).map(([category, items], catIdx) => {
            if (!Array.isArray(items)) return null;
            const emoji = EMOJI_META[category] || '📍';
            const categoryName = CATEGORY_LABELS[category] || category;
            const icon = createCustomEmojiIcon(emoji);

            return items.map((item, idx) => {
              let estLat = item.lat;
              let estLng = item.lng;

              if (estLat == null || estLng == null) {
                const angle = (catIdx * 60 + idx * 30) * (Math.PI / 180);
                const offset = (item.distance_km || 1) * 0.009;
                estLat = selectedProperty.lat! + Math.sin(angle) * offset;
                estLng = selectedProperty.lng! + Math.cos(angle) * offset;
              }

              return (
                <Marker
                  key={`establishment-${category}-${idx}`}
                  position={[estLat, estLng]}
                  icon={icon}
                >
                  <Popup>
                    <div className="p-1 min-w-[140px]">
                      <span className="inline-block px-2 py-0.5 mb-1 text-[10px] font-semibold text-slate-600 bg-slate-100 rounded-full border border-slate-200 uppercase tracking-wider">
                        {categoryName}
                      </span>
                      <p className="text-xs font-bold text-slate-800 leading-tight">
                        {emoji} {item.name}
                      </p>
                      <p className="text-[11px] text-slate-500 mt-1">
                        📍 <span className="font-medium text-slate-700">{item.distance_km} km</span> away from property
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