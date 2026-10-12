import React, { useState } from 'react';
import { MapPin, Map as MapIcon, Home, PhoneCall, X } from 'lucide-react';
import type { PropertyDetailModalProps, NearbyEstablishmentsMap, LocationPoint } from '../types';

import { PropertyImageGallery } from '@/components/property-detail-modal/PropertyImageGaller';
import { PropertyPricingGrid } from '@/components/property-detail-modal/PropertyPricingGrid';
import { PropertyFeatures } from '@/components/property-detail-modal/PropertyFeatures';
import { PropertyAmenities } from '@/components/property-detail-modal/PropertyAmenities';
import { PropertyNearby } from '@/components/property-detail-modal/PropertyNearby';
import { CommuteCard } from '@/components/CommuteCard';
import { ContactAgentsModal } from '@/components/ContactAgentsModal';
import { publicUrl } from '@/config';
import { categoryLabel } from '@/lib/categories';

interface ModalProps extends PropertyDetailModalProps {
  workplaceLocation?: LocationPoint | null;
  onViewOnMap?: (property: PropertyDetailModalProps['property']) => void;
}

export const PropertyDetailModal: React.FC<ModalProps> = ({
  property,
  workplaceLocation = null,
  onClose,
  onViewOnMap,
  onSetWorkplaceClick,
}) => {
  const [isContactOpen, setIsContactOpen] = useState(false);
  if (!property) return null;

  const handleViewOnMap = () => {
    if (onViewOnMap) {
      onViewOnMap(property);
    }
    onClose();
  };

  const photos = [
    ...(Array.isArray(property.photos) ? property.photos : []),
    ...(Array.isArray(property.media) ? property.media.map(publicUrl) : []),
  ];

  const rawNearby: NearbyEstablishmentsMap | undefined =
    property.nearby_establishments ??
    (property as { nearby_establishment?: NearbyEstablishmentsMap }).nearby_establishment;

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm animate-fade-in">
      {/* Phones: photos on top, details below. From md up: landscape, like a social
          media post — photos fill the left, details scroll on the right. */}
      <div className="relative bg-ab-card-2 rounded-2xl w-full max-w-lg md:max-w-6xl overflow-hidden shadow-2xl border border-ab-border flex flex-col md:flex-row max-h-[90vh] md:h-[min(88vh,760px)]">

        <PropertyImageGallery photos={photos} title={property.title} />

        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute top-3 right-3 z-20 bg-black/60 hover:bg-black/80 text-white p-1.5 rounded-full backdrop-blur-md transition"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Details panel */}
        <div className="flex min-h-0 flex-1 flex-col md:w-[380px] md:flex-none lg:w-[440px] md:border-l md:border-ab-border">
          <div className="p-6 overflow-y-auto space-y-5 flex-1">
            <div className="md:pr-10">
              <div className="flex flex-wrap items-center gap-2">
                {property.category && (
                  <span className="inline-block px-2.5 py-1 bg-ab-accent-soft text-ab-accent text-xs font-semibold rounded-full uppercase tracking-wider">
                    {categoryLabel(property.category)}
                  </span>
                )}
                {property.layout_type && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-ab-card-2 text-ab-muted text-xs font-semibold rounded-full">
                    <Home className="h-3 w-3" />
                    {property.layout_type}
                  </span>
                )}
              </div>
              <h2 className="text-xl font-bold text-ab-text mt-2">{property.title}</h2>
              <p className="text-ab-muted text-sm flex items-center mt-1">
                <MapPin className="h-4 w-4 mr-1 text-ab-faint shrink-0" />
                {property.village_name}
              </p>
            </div>

            <PropertyPricingGrid property={property} />

            {/* Commute & Route Convenience Score Container */}
            <CommuteCard
              property={property}
              workplace={workplaceLocation}
              onSetWorkplaceClick={onSetWorkplaceClick || (() => {})}
            />

            <PropertyFeatures property={property} />

            {property.details && (
              <div>
                <h3 className="text-xs font-semibold uppercase text-ab-faint mb-1">Description</h3>
                <p className="text-sm text-ab-muted leading-relaxed">{property.details}</p>
              </div>
            )}

            <PropertyAmenities amenityList={property.amenity_list} />

            <PropertyNearby nearbyData={rawNearby} />
          </div>

          {/* Footer Actions */}
          <div className="p-4 border-t bg-ab-card flex items-center justify-end gap-2.5 shrink-0">
            <button
              onClick={handleViewOnMap}
              className="flex items-center gap-1.5 px-4 py-2 bg-ab-card-2 border border-ab-border text-ab-muted rounded-xl text-sm font-medium hover:bg-ab-card-2 hover:text-ab-text transition shadow-sm"
            >
              <MapIcon className="h-4 w-4 text-ab-accent" />
              <span>View Map</span>
            </button>

            <button
              onClick={() => setIsContactOpen(true)}
              title="Reserve or buy through an agent near this property"
              className="flex items-center gap-1.5 px-5 py-2 bg-ab-accent text-ab-ink rounded-xl text-sm font-medium hover:bg-ab-accent-hover transition shadow-sm"
            >
              <PhoneCall className="h-4 w-4" />
              <span>Reserve / Purchase</span>
            </button>
          </div>
        </div>
      </div>
      {isContactOpen && <ContactAgentsModal property={property} onClose={() => setIsContactOpen(false)} />}
    </div>
  );
};