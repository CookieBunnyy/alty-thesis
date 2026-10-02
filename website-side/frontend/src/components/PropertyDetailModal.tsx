import React, { useState } from 'react';
import { MapPin, Map as MapIcon, Home, PhoneCall } from 'lucide-react';
import type { PropertyDetailModalProps, NearbyEstablishmentsMap, LocationPoint } from '../types';

import { PropertyImageGallery } from '@/components/property-detail-modal/PropertyImageGaller';
import { PropertyPricingGrid } from '@/components/property-detail-modal/PropertyPricingGrid';
import { PropertyFeatures } from '@/components/property-detail-modal/PropertyFeatures';
import { PropertyAmenities } from '@/components/property-detail-modal/PropertyAmenities';
import { PropertyNearby } from '@/components/property-detail-modal/PropertyNearby';
import { CommuteCard } from '@/components/CommuteCard';
import { ContactAgentsModal } from '@/components/ContactAgentsModal';
import { publicUrl } from '@/config';

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
      <div className="bg-ab-card-2 rounded-2xl max-w-lg w-full overflow-hidden shadow-2xl border border-ab-border flex flex-col max-h-[90vh]">
        
        {/* Photo Gallery Header */}
        <PropertyImageGallery photos={photos} title={property.title} onClose={onClose} />

        {/* Body Content */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              {property.category && (
                <span className="inline-block px-2.5 py-1 bg-ab-accent-soft text-ab-accent text-xs font-semibold rounded-full uppercase tracking-wider">
                  {property.category}
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
            onClick={onClose}
            className="px-4 py-2 bg-ab-card-2 border border-ab-border text-ab-muted rounded-xl text-sm font-medium hover:bg-ab-card-2 transition shadow-sm"
          >
            Close
          </button>

          <button
            onClick={() => setIsContactOpen(true)}
            title="Call or text an agent near this property"
            className="flex items-center gap-1.5 px-5 py-2 bg-ab-accent text-ab-ink rounded-xl text-sm font-medium hover:bg-ab-accent-hover transition shadow-sm"
          >
            <PhoneCall className="h-4 w-4" />
            <span>Contact Agent</span>
          </button>
        </div>
      </div>
      {isContactOpen && <ContactAgentsModal property={property} onClose={() => setIsContactOpen(false)} />}
    </div>
  );
};