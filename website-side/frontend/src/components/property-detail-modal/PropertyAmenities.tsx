import React from 'react';
import { CheckCircle2 } from 'lucide-react';

interface AmenitiesProps {
  amenityList: string | Record<string, boolean> | undefined;
}

export const PropertyAmenities: React.FC<AmenitiesProps> = ({ amenityList }) => {
  let amenities: Record<string, boolean> = {};

  if (typeof amenityList === 'string') {
    try {
      amenities = JSON.parse(amenityList);
    } catch {
      amenities = {};
    }
  } else if (amenityList) {
    amenities = amenityList;
  }

  const activeAmenities = Object.entries(amenities).filter(([, val]) => Boolean(val));

  if (activeAmenities.length === 0) return null;

  return (
    <div>
      <h3 className="text-xs font-semibold uppercase text-ab-faint mb-2">Amenities</h3>
      <div className="flex flex-wrap gap-2">
        {activeAmenities.map(([key]) => (
          <span
            key={key}
            className="flex items-center text-xs bg-ab-card-2 text-ab-muted px-2.5 py-1 rounded-md font-medium capitalize"
          >
            <CheckCircle2 className="h-3 w-3 mr-1 text-ab-accent" />
            {key.replace('_', ' ')}
          </span>
        ))}
      </div>
    </div>
  );
};