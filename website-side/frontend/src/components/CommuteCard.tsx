import React from 'react';
import { Navigation, Clock, ShieldCheck, MapPin } from 'lucide-react';
import type { LocationPoint, Property } from '../types';

interface CommuteCardProps {
  property: Property;
  workplace: LocationPoint | null;
  onSetWorkplaceClick: () => void;
}

// Fallback Haversine calculation if backend OSRM stats aren't pre-calculated
function calculateFallbackEstimate(lat1: number, lon1: number, lat2: number, lon2: number) {
  const R = 6371; // km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const distanceKm = R * c;
  const durationMins = Math.round((distanceKm / 25) * 60);

  let score: 'Excellent' | 'Good' | 'Moderate' | 'Far' = 'Moderate';
  if (durationMins <= 20) score = 'Excellent';
  else if (durationMins <= 35) score = 'Good';
  else if (durationMins > 50) score = 'Far';

  return { distanceKm: distanceKm.toFixed(1), durationMins, score };
}

function getBadgeColor(score: string) {
  switch (score) {
    case 'Excellent':
      return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    case 'Good':
      return 'bg-blue-100 text-blue-800 border-blue-200';
    case 'Far':
      return 'bg-red-100 text-red-800 border-red-200';
    default:
      return 'bg-amber-100 text-amber-800 border-amber-200';
  }
}

export const CommuteCard: React.FC<CommuteCardProps> = ({
  property,
  workplace,
  onSetWorkplaceClick,
}) => {
  if (!workplace) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-center shadow-sm">
        <Navigation className="mx-auto h-6 w-6 text-slate-400 mb-1" />
        <p className="text-xs font-semibold text-slate-700">Calculate Work Commute</p>
        <p className="text-[11px] text-slate-500 mb-2">
          Set your workplace location to see distance and estimated travel time.
        </p>
        <button
          onClick={onSetWorkplaceClick}
          className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-800"
        >
          + Set Workplace
        </button>
      </div>
    );
  }

  if (!property.lat || !property.lng) return null;

  // Use backend OSRM route data if available; otherwise calculate Haversine fallback
  const distance = property.commute_info
    ? property.commute_info.distance_km.toFixed(1)
    : calculateFallbackEstimate(property.lat, property.lng, workplace.lat, workplace.lng).distanceKm;

  const duration = property.commute_info
    ? property.commute_info.duration_mins
    : calculateFallbackEstimate(property.lat, property.lng, workplace.lat, workplace.lng).durationMins;

  const score = property.commute_info
    ? property.commute_info.convenience_score
    : calculateFallbackEstimate(property.lat, property.lng, workplace.lat, workplace.lng).score;

  const badgeColor = getBadgeColor(score);

  return (
    <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-4 shadow-sm">
      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
        <div className="flex items-center space-x-1.5">
          <ShieldCheck className="h-4 w-4 text-emerald-600" />
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
            Commute Value Score
          </h3>
        </div>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${badgeColor}`}
        >
          {score} Convenience
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3">
        {/* Distance */}
        <div className="rounded-lg bg-white p-2.5 border border-slate-100 shadow-2xs">
          <div className="flex items-center space-x-1 text-slate-400 mb-1">
            <MapPin className="h-3.5 w-3.5" />
            <span className="text-[11px] font-medium text-slate-500">Distance</span>
          </div>
          <p className="text-sm font-bold text-slate-900">{distance} km</p>
          <p className="text-[10px] text-slate-400">
            {property.commute_info ? "OSRM route" : "Point-to-point"}
          </p>
        </div>

        {/* Estimated Time */}
        <div className="rounded-lg bg-white p-2.5 border border-slate-100 shadow-2xs">
          <div className="flex items-center space-x-1 text-slate-400 mb-1">
            <Clock className="h-3.5 w-3.5" />
            <span className="text-[11px] font-medium text-slate-500">Est. Travel Time</span>
          </div>
          <p className="text-sm font-bold text-slate-900">~{duration} mins</p>
          <p className="text-[10px] text-slate-500">Best commute route</p>
        </div>
      </div>

      {/* Workplace details footer */}
      <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500 pt-2 border-t border-slate-100">
        <span className="truncate max-w-[200px]">
          Workplace: <strong>{workplace.name}</strong>
        </span>
        <button
          onClick={onSetWorkplaceClick}
          className="text-emerald-600 hover:underline font-medium shrink-0 ml-1"
        >
          Change
        </button>
      </div>
    </div>
  );
};