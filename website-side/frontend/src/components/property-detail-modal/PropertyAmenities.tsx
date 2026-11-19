import React from 'react';
import { CheckCircle2 } from 'lucide-react';

interface AmenitiesProps {
  /** A list of names, or (older records) an object of name -> included. */
  amenityList: string | string[] | Record<string, boolean> | undefined | null;
  /** Amenities outside the common list, typed in as text. */
  other?: string | null;
}

function names(amenityList: AmenitiesProps['amenityList']): string[] {
  let raw: unknown = amenityList;
  if (typeof amenityList === 'string') {
    try {
      raw = JSON.parse(amenityList);
    } catch {
      return amenityList.split(',').map((a) => a.trim()).filter(Boolean);
    }
  }
  if (Array.isArray(raw)) return raw.map(String).filter(Boolean);
  if (raw && typeof raw === 'object') {
    return Object.entries(raw as Record<string, unknown>).filter(([, included]) => Boolean(included)).map(([name]) => name.replace(/_/g, ' '));
  }
  return [];
}

export const PropertyAmenities: React.FC<AmenitiesProps> = ({ amenityList, other }) => {
  const extra = (other ?? '').split(/[,;]/).map((a) => a.trim()).filter(Boolean);
  const amenities = [...new Set([...names(amenityList), ...extra])];
  if (amenities.length === 0) return null;

  return (
    <div>
      <h3 className="text-xs font-semibold uppercase text-ab-faint mb-2">Amenities</h3>
      <div className="flex flex-wrap gap-2">
        {amenities.map((name) => (
          <span
            key={name}
            className="flex items-center text-xs bg-ab-card-2 text-ab-muted px-2.5 py-1 rounded-md font-medium"
          >
            <CheckCircle2 className="h-3 w-3 mr-1 text-ab-accent" />
            {name}
          </span>
        ))}
      </div>
    </div>
  );
};
