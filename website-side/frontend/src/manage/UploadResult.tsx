import { useEffect } from "react"
import { AlertTriangle, ChevronRight, CircleCheck, FolderOpen, UploadCloud } from "lucide-react"
import { statusLabel } from "./format"
import { t } from "./i18n"
import { Button } from "./ui"
import type { DocumentRecord } from "./UploadDocument"

type Processing = { created_records?: string[]; updated_records?: string[]; error_reason?: string | null }

// A short word of encouragement after a successful upload, picked by the
// document's ID so it stays the same if the dialog re-renders.
const CHEERS = [
  "Nice work — one more record in order.",
  "Well done — this file is now easy to find.",
  "Great job keeping the repository organized.",
  "Filed and ready. Thanks for keeping things tidy.",
]
const cheerFor = (id: string) => CHEERS[[...id].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % CHEERS.length]

const recordKind = (ref: string) => statusLabel(ref.split(":")[0].replace("property_listings", "property").replace(/s$/, ""))

/** Shown after an upload: where the document was saved and what ALTY did. */
export function UploadResult({ doc, newFolder, isVersion, onView, onOpenFolder, onUploadAnother, onClose }: {
  doc: DocumentRecord; newFolder: boolean; isVersion?: boolean
  onView: () => void; onOpenFolder?: () => void; onUploadAnother?: () => void; onClose: () => void
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose()
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  const failed = doc.status === "FAILED"
  const processing = (doc.processing ?? {}) as Processing
  const path = doc.folder_path ?? doc.folder_name ?? null
  const created = processing.created_records ?? []
  const updated = processing.updated_records ?? []
  const title = failed
    ? t("Saved, but processing failed")
    : isVersion ? t("Version {n} saved", { n: doc.version }) : t("Document saved")

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="upload-result-title">
      <button type="button" aria-label={t("Close")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <div className="ab-pop relative w-full max-w-md rounded-2xl border border-ab-border bg-ab-card p-6 text-center shadow-2xl">
        <span className={`mx-auto flex h-14 w-14 items-center justify-center rounded-full ${failed ? "bg-ab-danger/15 text-ab-danger" : "bg-ab-success/15 text-ab-success"}`}>
          {failed ? <AlertTriangle className="h-7 w-7" /> : <CircleCheck className="h-7 w-7" />}
        </span>
        <h2 id="upload-result-title" className="mt-3 text-xl font-extrabold">{title}</h2>
        <p className="mt-1 break-words text-sm text-ab-muted">“{doc.document_name}”</p>

        <div className="mt-5 rounded-xl border border-ab-border bg-ab-card-2 p-4 text-left">
          <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-ab-faint">{t("Saved to")}</p>
          {path ? (
            <p className="mt-1.5 flex flex-wrap items-center gap-1 text-sm font-semibold text-ab-text">
              <FolderOpen className="mr-0.5 h-4 w-4 shrink-0 text-ab-accent" aria-hidden />
              {path.split(" / ").map((part, i, all) => (
                <span key={`${part}-${i}`} className="inline-flex items-center gap-1">
                  {part}
                  {i < all.length - 1 && <ChevronRight className="h-3.5 w-3.5 text-ab-faint" aria-hidden />}
                </span>
              ))}
            </p>
          ) : (
            <p className="mt-1.5 text-sm font-semibold text-ab-text">{t("All documents (no folder)")}</p>
          )}
          {newFolder && path && !failed && (
            <p className="mt-1 text-xs text-ab-success">{t("New folder created for “{name}”.", { name: path.split(" / ").pop() ?? path })}</p>
          )}
          {!failed && (created.length > 0 || updated.length > 0) && (
            <p className="mt-2 border-t border-ab-border pt-2 text-xs text-ab-muted">
              {created.length > 0 && <>{t("Created:")} {created.map(recordKind).join(", ")}</>}
              {created.length > 0 && updated.length > 0 && " · "}
              {updated.length > 0 && <>{t("Updated:")} {updated.map(recordKind).join(", ")}</>}
            </p>
          )}
          {failed && (
            <p className="mt-2 border-t border-ab-border pt-2 text-xs text-ab-muted">
              {doc.processing_stage && <span className="font-semibold text-ab-danger">{t("{stage} stage", { stage: statusLabel(doc.processing_stage) })} · </span>}
              {doc.processing_error ?? processing.error_reason ?? t("Not recorded")}
            </p>
          )}
        </div>

        <p className="mt-4 text-sm text-ab-muted">
          {failed
            ? t("The file is stored safely. Open it to see what went wrong, then reprocess it once it's fixed.")
            : t(cheerFor(doc.document_id))}
        </p>

        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {onUploadAnother && <Button onClick={onUploadAnother}><UploadCloud className="h-4 w-4" /> {t("Upload another")}</Button>}
          {onOpenFolder && doc.folder_id != null && <Button onClick={onOpenFolder}><FolderOpen className="h-4 w-4" /> {t("Open folder")}</Button>}
          <Button variant="primary" onClick={onView}>{failed ? t("View details") : t("View document")}</Button>
        </div>
      </div>
    </div>
  )
}
