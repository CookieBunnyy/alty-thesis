// Amenity pictures and floor plans from the developer, laid out like the
// developer's flyer: amenity photos side by side with their names on them,
// floor plans on white with the label underneath.
import React, { useState } from 'react';
import { X } from 'lucide-react';
import { publicUrl } from '@/config';

type Labelled = { url: string; caption: string | null };

export const PropertyAmenityPhotos: React.FC<{ items?: Labelled[] }> = ({ items }) => {
  const [open, setOpen] = useState<Labelled | null>(null);
  if (!items?.length) return null;
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase text-ab-faint mb-2">Amenities</h3>
      <ul className="grid grid-cols-2 gap-1 overflow-hidden rounded-xl sm:grid-cols-3">
        {items.map((item) => (
          <li key={item.url} className="relative aspect-[4/3] bg-ab-card">
            <button type="button" onClick={() => setOpen(item)} className="block h-full w-full" aria-label={`View ${item.caption ?? 'amenity'}`}>
              <img src={publicUrl(item.url)} alt={item.caption ?? ''} loading="lazy" className="h-full w-full object-cover" />
              <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/75 to-transparent px-2 pb-1.5 pt-6 text-left">
                <span className="block text-[10px] font-bold uppercase tracking-wide text-white">{item.caption}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      {open && <Lightbox item={open} onClose={() => setOpen(null)} />}
    </div>
  );
};

export const PropertyFloorPlans: React.FC<{ items?: Labelled[] }> = ({ items }) => {
  const [open, setOpen] = useState<Labelled | null>(null);
  if (!items?.length) return null;
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase text-ab-faint mb-2">Floor plans</h3>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {items.map((item) => (
          <li key={item.url} className="text-center">
            <button type="button" onClick={() => setOpen(item)} className="block w-full overflow-hidden rounded-lg border border-ab-border bg-white p-1" aria-label={`View ${item.caption ?? 'floor plan'}`}>
              <img src={publicUrl(item.url)} alt={item.caption ?? 'Floor plan'} loading="lazy" className="aspect-[3/4] w-full object-contain" />
            </button>
            <span className="mt-1 block text-[10px] font-semibold uppercase leading-tight tracking-wide text-ab-muted">{item.caption ?? 'Floor plan'}</span>
          </li>
        ))}
      </ul>
      {open && <Lightbox item={open} onClose={() => setOpen(null)} white />}
    </div>
  );
};

function Lightbox({ item, onClose, white }: { item: Labelled; onClose: () => void; white?: boolean }) {
  return (
    <div className="fixed inset-0 z-[2100] flex items-center justify-center bg-black/80 p-4" role="dialog" aria-modal="true" aria-label={item.caption ?? 'Image'} onClick={onClose}>
      <button type="button" onClick={onClose} aria-label="Close" className="absolute right-4 top-4 rounded-full bg-black/60 p-2 text-white"><X className="h-5 w-5" /></button>
      <figure className="max-h-full max-w-4xl" onClick={(e) => e.stopPropagation()}>
        <img src={publicUrl(item.url)} alt={item.caption ?? ''} className={`max-h-[80vh] w-auto rounded-lg object-contain ${white ? 'bg-white p-2' : ''}`} />
        {item.caption && <figcaption className="mt-2 text-center text-sm font-semibold uppercase tracking-wide text-white">{item.caption}</figcaption>}
      </figure>
    </div>
  );
}
