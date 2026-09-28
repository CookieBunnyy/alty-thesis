import React from 'react';
import { Navigation } from 'lucide-react';
import type { NearbyEstablishmentsMap } from "@/types"

const CATEGORY_META: Record<string, { label: string; icon: string }> = {
  hospitals: { label: 'Hospitals', icon: '🏥' },
  malls: { label: 'Malls', icon: '🛍️' },
  markets: { label: 'Markets', icon: '🛒' },
  parks: { label: 'Parks', icon: '🌳' },
  schools: { label: 'Schools', icon: '🎓' },
  transit: { label: 'Transit', icon: '🚆' },
};

interface NearbyProps {
  nearbyData: string | NearbyEstablishmentsMap | undefined;
}

export const PropertyNearby: React.FC<NearbyProps> = ({ nearbyData }) => {
  let nearby: NearbyEstablishmentsMap = {};

  if (typeof nearbyData === 'string') {
    try {
      nearby = JSON.parse(nearbyData);
    } catch {
      nearby = {};
    }
  } else if (nearbyData && typeof nearbyData === 'object') {
    nearby = nearbyData as NearbyEstablishmentsMap;
  }

  const hasNearbyData =
    nearby &&
    typeof nearby === 'object' &&
    Object.values(nearby).some((arr) => Array.isArray(arr) && arr.length > 0);

  if (!hasNearbyData) return null;

  return (
    <div className="pt-2 border-t border-slate-100">
      <h3 className="text-xs font-semibold uppercase text-slate-400 mb-2.5 flex items-center">
        <Navigation className="h-3.5 w-3.5 mr-1 text-slate-400" />
        Nearby Establishments
      </h3>
      <div className="flex flex-wrap gap-2">
        {Object.entries(nearby).map(([category, places]) => {
          if (!Array.isArray(places) || places.length === 0) return null;
          const meta = CATEGORY_META[category] || { label: category, icon: '📍' };

          return places.map((place, idx) => (
            <span
              key={`${category}-${idx}`}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200/60"
            >
              <span>{meta.icon}</span>
              <span className="font-semibold">{place.name}</span>
              <span className="text-slate-400 text-[11px]">({place.distance_km} km)</span>
            </span>
          ));
        })}
      </div>
    </div>
  );
};