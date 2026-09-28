import React from 'react';
import { Bed, Bath, UtensilsCrossed, Sun, Trees, Car } from 'lucide-react';
import type { Property } from '@/types';

interface FeaturesProps {
  property: Property;
}

export const PropertyFeatures: React.FC<FeaturesProps> = ({ property }) => {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase text-slate-400 mb-2">Key Features & Layout</h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
        <div className="flex items-center space-x-2 bg-slate-50 p-2.5 rounded-xl border border-slate-100 text-slate-700 text-xs font-medium">
          <Bed className="h-4 w-4 text-emerald-600 shrink-0" />
          <span>{property.num_bedrooms} Bedrooms</span>
        </div>

        <div className="flex items-center space-x-2 bg-slate-50 p-2.5 rounded-xl border border-slate-100 text-slate-700 text-xs font-medium">
          <Bath className="h-4 w-4 text-emerald-600 shrink-0" />
          <span>{property.num_bathrooms} Bathrooms</span>
        </div>

        {(property.has_kitchen ?? true) && (
          <div className="flex items-center space-x-2 bg-slate-50 p-2.5 rounded-xl border border-slate-100 text-slate-700 text-xs font-medium">
            <UtensilsCrossed className="h-4 w-4 text-emerald-600 shrink-0" />
            <span>Kitchen</span>
          </div>
        )}

        {property.has_balcony && (
          <div className="flex items-center space-x-2 bg-slate-50 p-2.5 rounded-xl border border-slate-100 text-slate-700 text-xs font-medium">
            <Sun className="h-4 w-4 text-emerald-600 shrink-0" />
            <span>Balcony</span>
          </div>
        )}

        {property.has_backyard && (
          <div className="flex items-center space-x-2 bg-slate-50 p-2.5 rounded-xl border border-slate-100 text-slate-700 text-xs font-medium">
            <Trees className="h-4 w-4 text-emerald-600 shrink-0" />
            <span>Backyard</span>
          </div>
        )}

        {(property.has_garage || (property.garage_spaces ?? 0) > 0) && (
          <div className="flex items-center space-x-2 bg-slate-50 p-2.5 rounded-xl border border-slate-100 text-slate-700 text-xs font-medium">
            <Car className="h-4 w-4 text-emerald-600 shrink-0" />
            <span>
              {property.garage_spaces && property.garage_spaces > 0
                ? `${property.garage_spaces} Car Garage`
                : 'Garage Slot'}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};