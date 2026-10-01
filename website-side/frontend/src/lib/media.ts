import { publicUrl } from "@/config"
import type { Property } from "@/types"

/** Ask image CDNs that support it for a smaller rendition (cards don't need
 *  1200px originals). Other URLs are returned unchanged. */
export function sizedImage(url: string, width: number): string {
  try {
    const parsed = new URL(url, window.location.origin)
    if (parsed.hostname === "images.unsplash.com") {
      parsed.searchParams.set("w", String(width))
      parsed.searchParams.set("q", "70")
      parsed.searchParams.set("auto", "format")
      return parsed.toString()
    }
  } catch {
    /* not a URL: leave as is */
  }
  return url
}

export function propertyImage(property: Pick<Property, "photos" | "media">, width = 640): string | null {
  const photo = property.photos?.[0]
  if (photo) return sizedImage(photo, width)
  return property.media?.[0] ? publicUrl(property.media[0]) : null
}

export const peso = (value: number | null | undefined) =>
  value == null ? "Price on request" : `₱${Number(value).toLocaleString("en-PH", { maximumFractionDigits: 0 })}`
