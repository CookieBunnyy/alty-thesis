import React, { useState } from 'react';
import { X, ChevronLeft, ChevronRight, Building } from 'lucide-react';

interface GalleryProps {
  photos: string[];
  title: string;
  /** Shows a close button over the photo; leave out when the dialog has its own. */
  onClose?: () => void;
}

/** Photos with arrows and thumbnails. On phones a fixed-height strip at the top;
 *  from md up it fills the left side of the dialog (whole photo, dark backdrop). */
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
    <div className="flex shrink-0 flex-col bg-ab-card-2 md:min-h-0 md:min-w-0 md:flex-1 md:bg-black">
      <div className="relative h-60 sm:h-72 md:h-auto md:min-h-0 md:flex-1 flex items-center justify-center shrink-0 overflow-hidden">
        {photos.length > 0 ? (
          <>
            <img
              src={photos[activePhotoIndex]}
              alt={`${title} photo ${activePhotoIndex + 1}`}
              className="w-full h-full object-cover md:object-contain transition-all duration-300"
            />

            {photos.length > 1 && (
              <>
                <button
                  type="button"
                  aria-label="Previous photo"
                  onClick={handlePrevPhoto}
                  className="absolute left-3 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-black/80 text-white p-2 rounded-full backdrop-blur-md transition shadow-md"
                >
                  <ChevronLeft className="h-5 w-5" />
                </button>
                <button
                  type="button"
                  aria-label="Next photo"
                  onClick={handleNextPhoto}
                  className="absolute right-3 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-black/80 text-white p-2 rounded-full backdrop-blur-md transition shadow-md"
                >
                  <ChevronRight className="h-5 w-5" />
                </button>

                <span className="absolute bottom-3 right-3 bg-black/75 text-white text-xs font-semibold px-2.5 py-1 rounded-full backdrop-blur-md">
                  {activePhotoIndex + 1} / {photos.length}
                </span>
              </>
            )}
          </>
        ) : (
          <div className="text-ab-faint flex flex-col items-center">
            <Building className="h-12 w-12 mb-1 opacity-50" />
            <span className="text-xs">No image preview available</span>
          </div>
        )}

        {onClose && (
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="absolute top-3 right-3 bg-black/60 hover:bg-black/80 text-white p-1.5 rounded-full backdrop-blur-md transition z-10"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {photos.length > 1 && (
        <div className="bg-ab-card-2 px-3 py-2.5 border-b border-ab-border shrink-0 md:border-0 md:bg-black">
          <div className="flex gap-2.5 overflow-x-auto no-scrollbar scroll-smooth md:justify-center">
            {photos.map((photo, idx) => (
              <button
                key={idx}
                type="button"
                aria-label={`Show photo ${idx + 1}`}
                aria-pressed={activePhotoIndex === idx}
                onClick={() => setActivePhotoIndex(idx)}
                className={`relative h-14 w-20 shrink-0 rounded-xl overflow-hidden border-2 transition-all ${
                  activePhotoIndex === idx
                    ? 'border-ab-accent ring-2 ring-ab-accent/30 scale-100 shadow-sm'
                    : 'border-transparent opacity-60 hover:opacity-100'
                }`}
              >
                <img src={photo} alt={`Thumbnail ${idx + 1}`} className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};