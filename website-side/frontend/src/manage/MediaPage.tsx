import { useCallback, useMemo, useRef, useState } from "react"
import { ImagePlus, LoaderCircle, Trash2 } from "lucide-react"
import { Link } from "@/components/Link"
import { ApiError } from "@/lib/auth"
import { canFile, date, fileSize, statusLabel } from "./format"
import { Badge, Button, Confirm, LoadState, PageHeader, Select, Tiles } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData } from "./useApiData"
import { useBlobUrl } from "./useBlobUrl"
import { t } from "./i18n"

type Media = {
  id: number; listing_id: number; file_name: string; mime_type: string; file_size: number
  width: number | null; height: number | null; orientation: string | null
  blur_score: number | null; brightness: number | null; contrast: number | null
  quality_status: string; quality_issues: string[] | null; created_at: string
}
type Summary = { total: number; by_quality: Record<string, number>; listings_with_media: number }
type Thresholds = { min_resolution: string; blur_variance_poor_below: number; blur_variance_good_above: number; brightness_range: [number, number]; min_contrast_std: number; note: string }
type ListingOption = { listing_id: number; title: string | null; status: string }

// Same image types the server accepts for property media.
const IMAGE_ACCEPT = ".png,.jpg,.jpeg,.webp,.tif,.tiff,.bmp"

export function MediaPage() {
  const { api, user } = useStaffAuth()
  const toast = useToast()
  const picker = useRef<HTMLInputElement | null>(null)
  const [listing, setListing] = useState("")
  const [quality, setQuality] = useState("")
  const [uploading, setUploading] = useState("")
  const [toDelete, setToDelete] = useState<Media | null>(null)
  const [deleting, setDeleting] = useState(false)
  const editable = canFile(user?.role)

  const load = useCallback(() => Promise.all([
    api<Media[]>(`/media${listing ? `?listing_id=${listing}` : ""}`),
    api<Summary>("/media/summary"),
    api<Thresholds>("/media/thresholds"),
    api<ListingOption[]>("/property-listings?limit=5000"),
  ]), [api, listing])
  const { data, error, loading, reload } = useApiData(load, `media:${listing}`)
  const [media, summary, thresholds, listings] = data ?? [[], null, null, []]
  const titles = useMemo(() => Object.fromEntries(listings.map((l) => [l.listing_id, l.title ?? `#${l.listing_id}`])), [listings])
  const shown = media.filter((m) => !quality || m.quality_status === quality)

  const upload = async (files: FileList | null) => {
    if (!files?.length || !listing) return
    const results: string[] = []
    let failed = 0
    for (const [index, file] of [...files].entries()) {
      setUploading(t("Uploading {n} of {total}…", { n: index + 1, total: files.length }))
      const body = new FormData()
      body.append("file", file)
      try {
        const saved = await api<Media>(`/media/properties/${listing}`, { method: "POST", body })
        results.push(`${file.name}: ${statusLabel(saved.quality_status)}${saved.quality_issues?.length ? ` (${saved.quality_issues.map((issue) => t(issue)).join(", ")})` : ""}`)
      } catch (uploadError) {
        failed += 1
        results.push(`${file.name}: ${uploadError instanceof ApiError ? t(uploadError.message) : t("upload failed")}`)
      }
    }
    setUploading("")
    if (picker.current) picker.current.value = ""
    toast(results.join(" · "), failed ? "error" : "success")
    void reload()
  }

  const remove = async () => {
    if (!toDelete) return
    setDeleting(true)
    try {
      await api(`/media/${toDelete.id}`, { method: "DELETE" })
      toast(t("Removed {name}.", { name: toDelete.file_name }))
      setToDelete(null)
      void reload()
    } catch (deleteError) {
      toast((deleteError as Error).message, "error")
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Property photos and their quality checks"
        subtitle="Property photos uploaded to ALTY. Each image is checked for resolution, sharpness, brightness and contrast; only photos that pass are shown on the website."
        actions={editable && (
          <>
            <input ref={picker} type="file" accept={IMAGE_ACCEPT} multiple className="sr-only" aria-label={t("Property photos")} onChange={(e) => void upload(e.target.files)} />
            <Button variant="primary" disabled={!listing || !!uploading} onClick={() => picker.current?.click()}
              title={listing ? t("Upload photos to the selected property") : t("Choose a property first")}>
              {uploading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <ImagePlus className="h-4 w-4" />} {uploading || t("Upload photos")}
            </Button>
          </>
        )}
      />
      {summary && (
        <Tiles items={[
          { label: "Photos", value: summary.total, onClick: () => setQuality(""), active: !quality },
          ...["GOOD", "ACCEPTABLE", "POOR"].map((q) => ({
            label: statusLabel(q), value: summary.by_quality[q] ?? 0, onClick: () => setQuality(quality === q ? "" : q), active: quality === q,
          })),
          { label: "Properties with photos", value: summary.listings_with_media, detail: t("of {n}", { n: listings.length }) },
        ]} />
      )}
      <div className="flex flex-wrap gap-2">
        <Select label="Property" value={listing} onChange={setListing}
          options={[{ value: "", label: "All properties" }, ...listings.map((l) => ({ value: String(l.listing_id), label: `#${l.listing_id} · ${l.title ?? t("Untitled")}` }))]} />
        <Select label="Quality" value={quality} onChange={setQuality} options={[{ value: "", label: "Any quality" }, ...["GOOD", "ACCEPTABLE", "POOR"].map((q) => ({ value: q, label: statusLabel(q) }))]} />
      </div>
      {editable && !listing && <p className="text-xs text-ab-faint">{t("Choose a property to upload photos to it.")}</p>}
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (shown.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-ab-border px-4 py-14 text-center text-sm text-ab-muted">
          {t(media.length ? "No photos match this quality filter." : listing ? "No photos uploaded for this property yet." : "No property photos uploaded yet.")}
          <p className="mt-1 text-xs text-ab-faint">{t("Listings synced from Supabase keep their own photo links, which are edited on the Properties page.")}</p>
        </div>
      ) : (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((m) => <MediaCard key={m.id} media={m} title={titles[m.listing_id]} canDelete={editable} onDelete={() => setToDelete(m)} />)}
        </ul>
      ))}
      {thresholds && (
        <p className="text-xs text-ab-faint">
          {t("Checks: at least {res}; sharpness (blur variance) poor below {poor}, good above {good}; brightness {lo}–{hi}; contrast at least {contrast}.", {
            res: thresholds.min_resolution, poor: thresholds.blur_variance_poor_below, good: thresholds.blur_variance_good_above,
            lo: thresholds.brightness_range[0], hi: thresholds.brightness_range[1], contrast: thresholds.min_contrast_std,
          })} {t(thresholds.note)}
        </p>
      )}
      {toDelete && (
        <Confirm typeToConfirm="Delete" title="Delete photo?" message={t("Remove “{name}” from {property}? It will no longer appear on the website.", { name: toDelete.file_name, property: titles[toDelete.listing_id] ?? t("property #{id}", { id: toDelete.listing_id }) })}
          confirmLabel="Delete" busy={deleting} onConfirm={remove} onCancel={() => setToDelete(null)} />
      )}
    </div>
  )
}

function MediaCard({ media: m, title, canDelete, onDelete }: { media: Media; title?: string; canDelete: boolean; onDelete: () => void }) {
  const { url, error } = useBlobUrl(`/media/${m.id}/file`)
  return (
    <li className="overflow-hidden rounded-2xl border border-ab-border bg-ab-card">
      <div className="relative aspect-[4/3] bg-ab-card-2">
        {url ? <img src={url} alt={m.file_name} className="h-full w-full object-cover" /> : (
          <div className="flex h-full items-center justify-center text-xs text-ab-faint">{error || <LoaderCircle className="h-5 w-5 animate-spin text-ab-accent" />}</div>
        )}
        <span className="absolute left-2 top-2"><Badge value={m.quality_status} /></span>
      </div>
      <div className="space-y-1.5 p-3 text-xs">
        <p className="truncate text-sm font-semibold">{m.file_name}</p>
        <Link to={`/manage/properties?id=${m.listing_id}`} className="block truncate text-ab-muted hover:underline">{title ?? t("Property #{id}", { id: m.listing_id })}</Link>
        <p className="text-ab-faint">{m.width}×{m.height} · {fileSize(m.file_size)} · {date(m.created_at)}</p>
        <p className="text-ab-faint">{t("Sharpness")} {m.blur_score?.toFixed(0) ?? "—"} · {t("Brightness")} {m.brightness?.toFixed(0) ?? "—"} · {t("Contrast")} {m.contrast?.toFixed(0) ?? "—"}</p>
        {m.quality_issues?.length ? <p className="text-ab-warning">{m.quality_issues.map((issue) => t(issue)).join(" · ")}</p> : null}
        {canDelete && (
          <button type="button" onClick={onDelete} className="inline-flex items-center gap-1 font-semibold text-ab-danger hover:underline">
            <Trash2 className="h-3.5 w-3.5" /> {t("Remove")}
          </button>
        )}
      </div>
    </li>
  )
}
