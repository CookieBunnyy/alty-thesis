import { useRef, useState, type DragEvent, type FormEvent } from "react"
import { FileUp, LoaderCircle, UploadCloud, X } from "lucide-react"
import { ApiError } from "@/lib/auth"
import { fileSize } from "./format"
import { Button } from "./ui"
import { useStaffAuth } from "./staffContext"
import { indexFolders } from "./folders"

export type DocType = { code: string; label: string; processing: string }
export type Folder = { id: number; name: string; parent_id: number | null; is_archived: boolean }
export type DocumentRecord = {
  document_id: string; document_name: string; document_type: string; status: string; version: number
  folder_id: number | null; folder_name: string | null; folder_path?: string | null; processing_error: string | null; processing_stage: string | null
  [key: string]: unknown
}

// Same checks as the server (document_storage.detect_file_kind, MAX_UPLOAD_MB).
const ACCEPT = ".pdf,.docx,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp"
const MAX_MB = 25
const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"

/** Upload a new document, or (with ``versionOf``) a new version of one.
 *  Processing runs automatically on the server; the result comes back here. */
export function UploadDocument({ types, folders, defaultFolder, versionOf, onClose, onUploaded }: {
  types: DocType[]; folders: Folder[]; defaultFolder?: number | null; versionOf?: DocumentRecord
  onClose: () => void; onUploaded: (doc: DocumentRecord) => void
}) {
  const { api } = useStaffAuth()
  const input = useRef<HTMLInputElement | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState("")
  const [type, setType] = useState(versionOf?.document_type ?? "AUTO")
  const [folder, setFolder] = useState<string>(String(versionOf?.folder_id ?? defaultFolder ?? ""))
  const [description, setDescription] = useState("")
  const [error, setError] = useState("")
  const [duplicate, setDuplicate] = useState<DocumentRecord | null>(null)
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)

  const choose = (picked: File | undefined) => {
    setError("")
    setDuplicate(null)
    if (!picked) return
    const extension = picked.name.slice(picked.name.lastIndexOf(".")).toLowerCase()
    if (!ACCEPT.split(",").includes(extension)) return setError("Use a PDF, Word (.docx) or image file (PNG, JPG, TIFF, BMP, WEBP).")
    if (picked.size > MAX_MB * 1024 * 1024) return setError(`Files must be ${MAX_MB} MB or smaller.`)
    if (picked.size === 0) return setError("The selected file is empty.")
    setFile(picked)
  }

  const send = async (allowDuplicate: boolean) => {
    if (!file) return setError("Choose a file to upload.")
    setBusy(true)
    setError("")
    const body = new FormData()
    body.append("file", file)
    if (name.trim()) body.append("document_name", name.trim())
    if (type && type !== "AUTO") body.append("document_type", type)
    if (folder) body.append("folder_id", folder)
    if (description.trim()) body.append("description", description.trim())
    if (allowDuplicate) body.append("allow_duplicate", "true")
    try {
      const path = versionOf ? `/documents/${encodeURIComponent(versionOf.document_id)}/new-version` : "/documents/upload"
      onUploaded(await api<DocumentRecord>(path, { method: "POST", body }))
    } catch (uploadError) {
      const detail = uploadError instanceof ApiError ? (uploadError.detail as { existing_document?: DocumentRecord } | undefined) : undefined
      if (uploadError instanceof ApiError && uploadError.status === 409 && detail?.existing_document) setDuplicate(detail.existing_document)
      setError((uploadError as Error).message)
      setBusy(false)
    }
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void send(false)
  }
  const drop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    choose(event.dataTransfer.files[0])
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={versionOf ? "Upload new version" : "Upload document"}>
      <button type="button" aria-label="Cancel" className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={submit} className="ab-pop relative flex max-h-[94dvh] w-full max-w-xl flex-col rounded-t-2xl border border-ab-border bg-ab-card shadow-2xl sm:rounded-2xl">
        <header className="flex items-center justify-between border-b border-ab-border px-5 py-4">
          <h2 className="text-lg font-bold">{versionOf ? `New version of “${versionOf.document_name}”` : "Upload document"}</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><X className="h-4 w-4" /></button>
        </header>
        <div className="space-y-4 overflow-y-auto p-5">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={drop}
            className={`rounded-2xl border-2 border-dashed p-6 text-center transition ${dragging ? "border-ab-accent bg-ab-accent-soft" : "border-ab-border"}`}
          >
            <UploadCloud className="mx-auto h-8 w-8 text-ab-accent" />
            {file ? (
              <p className="mt-2 text-sm"><span className="font-semibold">{file.name}</span> <span className="text-ab-faint">· {fileSize(file.size)}</span></p>
            ) : (
              <p className="mt-2 text-sm text-ab-muted">Drag a file here, or</p>
            )}
            <button type="button" onClick={() => input.current?.click()} className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-ab-border-strong px-3 py-1.5 text-sm font-semibold hover:bg-ab-hover">
              <FileUp className="h-4 w-4" /> {file ? "Choose another file" : "Choose file"}
            </button>
            <input ref={input} type="file" accept={ACCEPT} className="sr-only" onChange={(e) => choose(e.target.files?.[0])} aria-label="Document file" />
            <p className="mt-2 text-xs text-ab-faint">PDF, Word (.docx) or image · up to {MAX_MB} MB</p>
          </div>
          {!versionOf && (
            <label className="block text-sm font-medium">Display name (optional)
              <input className={field} value={name} onChange={(e) => setName(e.target.value)} placeholder={file?.name ?? "Defaults to the file name"} />
            </label>
          )}
          <label className="block text-sm font-medium">Document type
            <select className={field} value={type} onChange={(e) => setType(e.target.value)}>
              {types.map((t) => <option key={t.code} value={t.code}>{t.label}</option>)}
            </select>
            <span className="mt-1 block text-xs font-normal text-ab-faint">{types.find((t) => t.code === type)?.processing}</span>
          </label>
          <label className="block text-sm font-medium">Folder
            <select className={field} value={folder} onChange={(e) => setFolder(e.target.value)}>
              <option value="">{versionOf ? "No folder" : "Automatic (by person / property)"}</option>
              {indexFolders(folders).options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            {!versionOf && (
              <span className="mt-1 block text-xs font-normal text-ab-faint">
                Processed documents are filed by who they are about: a buyer document for John Doe goes to Buyers / John Doe. A custom folder you pick is kept.
              </span>
            )}
          </label>
          <label className="block text-sm font-medium">Description (optional)
            <textarea className={`${field} min-h-16`} value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
          <p className="text-xs text-ab-faint">
            After upload, ALTY validates the file, extracts its text (OCR for scans), classifies it, matches the property, client, agent and
            transaction, checks for duplicates and records the result automatically. If something can't be processed, the document is marked
            <strong> Failed</strong> with the reason.
          </p>
        </div>
        {error && (
          <div role="alert" className="mx-5 mb-2 rounded-lg border border-ab-danger/40 bg-ab-danger/10 px-3 py-2 text-sm text-ab-danger">
            {error}
            {duplicate && (
              <p className="mt-1 text-ab-muted">
                Existing: <span className="font-semibold text-ab-text">{duplicate.document_name}</span> (v{duplicate.version}).{" "}
                <button type="button" onClick={() => void send(true)} className="font-semibold text-ab-accent underline">Upload anyway</button>
              </p>
            )}
          </div>
        )}
        <footer className="flex justify-end gap-2 border-t border-ab-border px-5 py-3">
          <Button onClick={onClose} disabled={busy}>Cancel</Button>
          <Button type="submit" variant="primary" disabled={busy || !file}>
            {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />} {busy ? "Uploading & processing…" : "Upload"}
          </Button>
        </footer>
      </form>
    </div>
  )
}
