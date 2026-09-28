import React from 'react';
import type { Property } from '@/types';

interface PricingProps {
  property: Property;
}

export const PropertyPricingGrid: React.FC<PricingProps> = ({ property }) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 border-y border-slate-100 py-3.5 bg-slate-50/60 p-3.5 rounded-xl">
      <div>
        <p className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Total Price</p>
        <p className="text-lg font-bold text-emerald-600">
          ₱{Number(property.price_total || 0).toLocaleString()}
        </p>
      </div>

      {property.initial_dp != null && property.initial_dp > 0 && (
        <div className="border-t sm:border-t-0 sm:border-l border-slate-200 pt-2 sm:pt-0 sm:pl-3">
          <p className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Down Payment</p>
          <p className="text-sm font-semibold text-slate-800">
            ₱{Number(property.initial_dp).toLocaleString()}
          </p>
        </div>
      )}

      {property.monthly_rate != null && property.monthly_rate > 0 && (
        <div className="border-t sm:border-t-0 sm:border-l border-slate-200 pt-2 sm:pt-0 sm:pl-3">
          <p className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Est. Monthly</p>
          <p className="text-sm font-semibold text-slate-800">
            ₱{Number(property.monthly_rate).toLocaleString()}/mo
          </p>
        </div>
      )}
    </div>
  );
};