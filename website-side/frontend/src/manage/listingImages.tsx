// A listing's images, in three groups like a developer's flyer: property
// photos, floor plans and amenities. Every upload is checked for quality
// (resolution, sharpness, brightness, contrast); only images that pass are
// shown on the website. Used when adding a property, in the property drawer
// and in a seller's own listings.
import { useCallback, useRef, useState } from "react"
import { CheckCircle2, ImagePlus, LoaderCircle, Pencil, ShieldAlert, Trash2, TriangleAlert } from "lucide-react"
import { ApiError } from "@/lib/auth"
import { statusLabel } from "./format"
import { Confirm } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData } from "./useApiData"
import { useBlobUrl } from "./useBlobUrl"
import { t } from "./i18n"

export type ListingImage = {
  id: number; listing_id: number; file_name: string; media_kind: string; caption: string | null
  width: number | null; height: number | null; quality_status: string; quality_issues: string[] | null
}
type Group = "PHOTO" | "FLOOR_PLAN" | "AMENITY"

const IMAGE_ACCEPT = ".png,.jpg,.jpeg,.webp,.tif,.tiff,.bmp"
const passes = (image: ListingImage) => image.quality_status === "GOOD" || image.quality_status === "ACCEPTABLE"
const GROUPS: { key: Group; title: string; hint: string; button: string }[] = [
  { key: "PHOTO", title: "Property photos", hint: "Photos of the unit, and the architect's perspectives from the developer.", button: "Add photos" },
  { key: "FLOOR_PLAN", title: "Floor plans", hint: "Floor plans from the developer (bare unit, turnover or suggested layout). Name each one.", button: "Add floor plans" },
  { key: "AMENITY", title: "Amenities", hint: "Pictures of the amenities from the developer's materials (pool, playground, clubhouse…). Name each one.", button: "Add amenity pictures" },
]

export function ListingImages({ listingId, editable }: { listingId: number; editable: boolean }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const load = useCallback(() => api<ListingImage[]>(`/media?listing_id=${listingId}`), [api, listingId])
  const { data, error, loading, reload } = useApiData(load)
  const [busy, setBusy] = useState<Group | null>(null)
  const [pending, setPending] = useState<{ group: Group; files: File[] } | null>(null)
  const [results, setResults] = useState<ListingImage[]>([])
  const [toDelete, setToDelete] = useState<ListingImage | null>(null)
  const images = data ?? []

  const upload = async (group: Group, files: File[], captions: string[] = []) => {
    setBusy(group)
    const done: ListingImage[] = []
    let failed = 0
    for (const [index, file] of files.entries()) {
      const body = new FormData()
      body.append("file", file)
      body.append("kind", group)
      if (captions[index]?.trim()) body.append("caption", captions[index].trim())
      try {
        done.push(await api<ListingImage>(`/media/properties/${listingId}`, { method: "POST", body }))
      } catch (uploadError) {
        failed += 1
        toast(`${file.name}: ${uploadError instanceof ApiError ? t(uploadError.message) : t("upload failed")}`, "error")
      }
    }
    setBusy(null)
    setPending(null)
    setResults(done)
    const poor = done.filter((image) => !passes(image)).length
    if (done.length) {
      toast(poor ? t("{n} uploaded · {poor} didn't pass the quality check and won't be shown", { n: done.length, poor })
        : t("{n} uploaded · all passed the quality check", { n: done.length }), poor || failed ? "error" : "success")
    }
    void reload()
  }

  const remove = async () => {
    if (!toDelete) return
    try {
      await api(`/media/${toDelete.id}`, { method: "DELETE" })
      setToDelete(null)
      void reload()
    } catch (deleteError) {
      toast(t((deleteError as Error).message), "error")
    }
  }

  return (
    <div className="space-y-5">
      {error && <p role="alert" className="text-sm text-ab-danger">{error}</p>}
      {loading && !data && <p className="text-sm text-ab-muted"><LoaderCircle className="mr-1 inline h-4 w-4 animate-spin" />{t("Loading images…")}</p>}
      {results.length > 0 && <QualityReport images={results} onClose={() => setResults([])} />}
      {GROUPS.map((group) => {
        const items = images.filter((image) => (group.key === "PHOTO" ? image.media_kind === "PHOTO" || image.media_kind === "PERSPECTIVE" : image.media_kind === group.key))
        return (
          <section key={group.key} aria-labelledby={`images-${group.key}`}>
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <h3 id={`images-${group.key}`} className="text-sm font-bold">{t(group.title)} <span className="font-normal text-ab-faint">· {items.length}</span></h3>
                <p className="text-xs text-ab-faint">{t(group.hint)}</p>
              </div>
              {editable && <PickButton label={group.button} busy={busy === group.key}
                onPick={(files) => (group.key === "PHOTO" ? void upload("PHOTO", files) : setPending({ group: group.key, files }))} />}
            </div>
            {items.length === 0 ? (
              <p className="mt-2 rounded-xl border border-dashed border-ab-border px-3 py-4 text-center text-xs text-ab-faint">{t("None yet.")}</p>
            ) : group.key === "AMENITY" ? (
              <ul className="mt-2 grid grid-cols-2 gap-1 overflow-hidden rounded-xl sm:grid-cols-3">
                {items.map((image) => <AmenityTile key={image.id} image={image} editable={editable} onDelete={() => setToDelete(image)} onChanged={reload} />)}
              </ul>
            ) : (
              <ul className={`mt-2 grid gap-2 ${group.key === "FLOOR_PLAN" ? "grid-cols-2 sm:grid-cols-3" : "grid-cols-2 sm:grid-cols-3"}`}>
                {items.map((image) => <ImageCard key={image.id} image={image} plan={group.key === "FLOOR_PLAN"} editable={editable} onDelete={() => setToDelete(image)} onChanged={reload} />)}
              </ul>
            )}
          </section>
        )
      })}
      {pending && <CaptionDialog group={pending.group} files={pending.files} busy={busy === pending.group}
        onCancel={() => setPending(null)} onUpload={(captions) => void upload(pending.group, pending.files, captions)} />}
      {toDelete && (
        <Confirm title="Remove image?" message={t("Remove “{name}”? It will no longer appear on the website.", { name: toDelete.caption || toDelete.file_name })}
          confirmLabel="Remove" onConfirm={() => void remove()} onCancel={() => setToDelete(null)} />
      )}
    </div>
  )
}

function PickButton({ label, busy, onPick }: { label: string; busy: boolean; onPick: (files: File[]) => void }) {
  const picker = useRef<HTMLInputElement | null>(null)
  return (
    <>
      <input ref={picker} type="file" accept={IMAGE_ACCEPT} multiple className="sr-only" aria-label={t(label)}
        onChange={(e) => { const files = [...(e.target.files ?? [])]; e.target.value = ""; if (files.length) onPick(files) }} />
      <button type="button" disabled={busy} onClick={() => picker.current?.click()}
        className="inline-flex min-h-9 items-center gap-1.5 rounded-xl border border-ab-border-strong px-3 text-xs font-semibold hover:bg-ab-hover disabled:opacity-60">
        {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <ImagePlus className="h-4 w-4" />} {t(label)}
      </button>
    </>
  )
}

/** The quality check of the images just uploaded. */
function QualityReport({ images, onClose }: { images: ListingImage[]; onClose: () => void }) {
  return (
    <div role="status" className="rounded-xl border border-ab-border bg-ab-card-2 p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <p className="font-semibold">{t("Image quality check")}</p>
        <button type="button" onClick={onClose} className="text-xs font-semibold text-ab-muted hover:underline">{t("Dismiss")}</button>
      </div>
      <ul className="mt-2 space-y-1.5">
        {images.map((image) => (
          <li key={image.id} className="flex items-start gap-2 text-xs">
            {passes(image) ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ab-success" /> : <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-ab-danger" />}
            <span className="min-w-0">
              <span className="font-semibold">{image.caption || image.file_name}</span> · {statusLabel(image.quality_status)} · {image.width}×{image.height}
              {image.quality_issues?.length ? <span className="block text-ab-warning">{image.quality_issues.map((issue) => t(issue)).join(" · ")}</span> : null}
              {!passes(image) && <span className="block font-semibold text-ab-danger">{t("Not shown on the website. Upload a sharper, larger image.")}</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function QualityBadge({ image }: { image: ListingImage }) {
  const ok = passes(image)
  const tone = image.quality_status === "GOOD" ? "bg-ab-success text-white" : ok ? "bg-ab-warning text-ab-ink" : "bg-ab-danger text-white"
  return (
    <span title={image.quality_issues?.map((issue) => t(issue)).join(" · ") || t("No quality issues")}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${tone}`}>
      {!ok && <TriangleAlert className="h-3 w-3" />}{statusLabel(image.quality_status)}
    </span>
  )
}

function useImage(id: number) {
  return useBlobUrl(`/media/${id}/file`).url
}

function ImageCard({ image, plan, editable, onDelete, onChanged }: { image: ListingImage; plan: boolean; editable: boolean; onDelete: () => void; onChanged: () => void }) {
  const url = useImage(image.id)
  return (
    <li className="overflow-hidden rounded-xl border border-ab-border bg-ab-card">
      <div className={`relative aspect-[4/3] ${plan ? "bg-white" : "bg-ab-card-2"}`}>
        {url ? <img src={url} alt={image.caption ?? image.file_name} className={`h-full w-full ${plan ? "object-contain p-1" : "object-cover"}`} />
          : <div className="flex h-full items-center justify-center"><LoaderCircle className="h-4 w-4 animate-spin text-ab-accent" /></div>}
        <span className="absolute left-1.5 top-1.5"><QualityBadge image={image} /></span>
        {image.media_kind === "PERSPECTIVE" && <span className="absolute right-1.5 top-1.5 rounded-full bg-black/60 px-2 py-0.5 text-[10px] font-semibold text-white">{t("Perspective")}</span>}
      </div>
      <div className="flex items-center justify-between gap-1 px-2 py-1.5">
        <CaptionText image={image} editable={editable && plan} onChanged={onChanged} fallback={plan ? t("Floor plan") : image.file_name} />
        {editable && <button type="button" onClick={onDelete} aria-label={t("Remove")} className="rounded-lg p-1 text-ab-danger hover:bg-ab-hover"><Trash2 className="h-3.5 w-3.5" /></button>}
      </div>
    </li>
  )
}

/** Flyer style: the picture with its name on it. */
function AmenityTile({ image, editable, onDelete, onChanged }: { image: ListingImage; editable: boolean; onDelete: () => void; onChanged: () => void }) {
  const url = useImage(image.id)
  return (
    <li className="relative aspect-[4/3] bg-ab-card-2">
      {url && <img src={url} alt={image.caption ?? ""} className="h-full w-full object-cover" />}
      <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/75 to-transparent px-2 pb-1.5 pt-6">
        <span className="block text-[11px] font-bold uppercase tracking-wide text-white">{image.caption}</span>
      </span>
      <span className="absolute left-1.5 top-1.5"><QualityBadge image={image} /></span>
      {editable && (
        <span className="absolute right-1 top-1 flex gap-0.5">
          <CaptionText image={image} editable onChanged={onChanged} fallback="" iconOnly />
          <button type="button" onClick={onDelete} aria-label={t("Remove")} className="rounded-lg bg-black/55 p-1 text-white hover:bg-black/75"><Trash2 className="h-3.5 w-3.5" /></button>
        </span>
      )}
    </li>
  )
}

function CaptionText({ image, editable, onChanged, fallback, iconOnly }: { image: ListingImage; editable: boolean; onChanged: () => void; fallback: string; iconOnly?: boolean }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const rename = async () => {
    const next = window.prompt(t("Name shown under the image"), image.caption ?? "")
    if (next === null) return
    try {
      await api(`/media/${image.id}`, { method: "PATCH", body: JSON.stringify({ caption: next }) })
      onChanged()
    } catch (renameError) {
      toast(t((renameError as Error).message), "error")
    }
  }
  if (iconOnly) {
    return <button type="button" onClick={() => void rename()} aria-label={t("Rename")} className="rounded-lg bg-black/55 p-1 text-white hover:bg-black/75"><Pencil className="h-3.5 w-3.5" /></button>
  }
  return (
    <span className="flex min-w-0 items-center gap-1">
      <span className="truncate text-[11px] font-semibold uppercase tracking-wide text-ab-muted">{image.caption || fallback}</span>
      {editable && <button type="button" onClick={() => void rename()} aria-label={t("Rename")} className="shrink-0 rounded p-0.5 text-ab-faint hover:text-ab-text"><Pencil className="h-3 w-3" /></button>}
    </span>
  )
}

const SUGGESTIONS: Record<string, string[]> = {
  FLOOR_PLAN: ["Floor plan (bare unit)", "Floor plan (suggested layout)", "Floor plan (turnover unit layout)"],
  AMENITY: ["Swimming pool", "Basketball court", "Outdoor playground & leisure park", "Clubhouse", "Guardhouse (main gate)", "Parking slots"],
}

function CaptionDialog({ group, files, busy, onCancel, onUpload }: { group: Group; files: File[]; busy: boolean; onCancel: () => void; onUpload: (captions: string[]) => void }) {
  const [captions, setCaptions] = useState(() => files.map(() => ""))
  const amenity = group === "AMENITY"
  const missing = amenity && captions.some((caption) => !caption.trim())
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={t(amenity ? "Name the amenities" : "Name the floor plans")}>
      <button type="button" aria-label={t("Cancel")} className="absolute inset-0 bg-black/55" onClick={onCancel} />
      <form onSubmit={(e) => { e.preventDefault(); if (!missing && !busy) onUpload(captions) }}
        className="ab-pop relative flex max-h-[90dvh] w-full max-w-lg flex-col rounded-2xl border border-ab-border bg-ab-card shadow-2xl">
        <h2 className="border-b border-ab-border px-5 py-4 text-lg font-bold">{t(amenity ? "Name the amenities" : "Name the floor plans")}</h2>
        <div className="space-y-3 overflow-y-auto p-5">
          <datalist id={`captions-${group}`}>{SUGGESTIONS[group].map((s) => <option key={s} value={s} />)}</datalist>
          {files.map((file, index) => (
            <label key={`${file.name}-${index}`} className="block text-sm font-medium">
              <span className="block truncate text-xs text-ab-faint">{file.name}</span>
              <input list={`captions-${group}`} value={captions[index]} required={amenity} maxLength={160} autoFocus={index === 0}
                placeholder={t(amenity ? "e.g. Swimming pool" : "e.g. Studio unit (22.92 sqm) - suggested layout")}
                onChange={(e) => setCaptions((all) => all.map((c, i) => (i === index ? e.target.value : c)))}
                className="mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none" />
            </label>
          ))}
        </div>
        <footer className="flex justify-end gap-2 border-t border-ab-border px-5 py-3">
          <button type="button" onClick={onCancel} className="rounded-xl border border-ab-border px-4 py-2 text-sm font-semibold hover:bg-ab-hover">{t("Cancel")}</button>
          <button type="submit" disabled={busy || missing} className="inline-flex items-center gap-2 rounded-xl bg-ab-accent px-4 py-2 text-sm font-semibold text-ab-ink disabled:opacity-60">
            {busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Upload and check quality")}
          </button>
        </footer>
      </form>
    </div>
  )
}
