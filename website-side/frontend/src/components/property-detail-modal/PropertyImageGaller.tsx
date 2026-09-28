import React, { useState } from 'react';
import { X, ChevronLeft, ChevronRight, Building } from 'lucide-react';

interface GalleryProps {
  photos: string[];
  title: string;
  onClose: () => void;
}

export const PropertyImageGallery: React.FC<GalleryProps> = ({ photos, title, onClose }) => {
  const [activePhotoIndex, setActivePhotoIndex] = useState(0);

  const handleNextPhoto = () => {
    if (photos.length > 0) {
      setActivePhotoIndex((prev) => (prev + 1) % photos.length);
    }
  };

  const handlePrevPhoto = () => {
    if (photos.length > 0) {
      setActivePhotoIndex((prev) => (prev - 1 + photos.length) % photos.length);
    }
  };

  return (
    <>
      <div className="relative h-60 bg-slate-900 flex items-center justify-center shrink-0 overflow-hidden">
        {photos.length > 0 ? (
          <>
            <img
              src={photos[activePhotoIndex]}
              alt={`${title} photo ${activePhotoIndex + 1}`}
              className="w-full h-full object-cover transition-all duration-300"
            />

            {photos.length > 1 && (
              <>
                <button
                  onClick={handlePrevPhoto}
                  className="absolute left-3 top-1/2 -translate-y-1/2 bg-slate-900/60 hover:bg-slate-900 text-white p-2 rounded-full backdrop-blur-md transition shadow-md"
                >
                  <ChevronLeft className="h-5 w-5" />
                </button>
                <button
                  onClick={handleNextPhoto}
                  className="absolute right-3 top-1/2 -translate-y-1/2 bg-slate-900/60 hover:bg-slate-900 text-white p-2 rounded-full backdrop-blur-md transition shadow-md"
                >
                  <ChevronRight className="h-5 w-5" />
                </button>

                <span className="absolute bottom-3 right-3 bg-slate-900/75 text-white text-xs font-semibold px-2.5 py-1 rounded-full backdrop-blur-md">
                  {activePhotoIndex + 1} / {photos.length}
                </span>
              </>
            )}
          </>
        ) : (
          <div className="text-slate-400 flex flex-col items-center">
            <Building className="h-12 w-12 mb-1 opacity-50" />
            <span className="text-xs">No image preview available</span>
          </div>
        )}

        <button
          onClick={onClose}
          className="absolute top-3 right-3 bg-slate-900/60 hover:bg-slate-900 text-white p-1.5 rounded-full backdrop-blur-md transition z-10"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {photos.length > 1 && (
        <div className="bg-slate-100 px-3 py-2.5 border-b border-slate-200 shrink-0">
          <div className="flex gap-2.5 overflow-x-auto no-scrollbar scroll-smooth">
            {photos.map((photo, idx) => (
              <button
                key={idx}
                onClick={() => setActivePhotoIndex(idx)}
                className={`relative h-14 w-20 shrink-0 rounded-xl overflow-hidden border-2 transition-all ${
                  activePhotoIndex === idx
                    ? 'border-emerald-600 ring-2 ring-emerald-600/30 scale-100 shadow-sm'
                    : 'border-white/80 opacity-60 hover:opacity-100'
                }`}
              >
                <img src={photo} alt={`Thumbnail ${idx + 1}`} className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  );
};