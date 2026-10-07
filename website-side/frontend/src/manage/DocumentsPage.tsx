import { useCallback, useMemo, useState, type FormEvent } from "react"
import { Archive, ArchiveRestore, Download, Eye, FilePlus2, FolderPlus, FolderX, LoaderCircle, RefreshCw, Trash2, UploadCloud, X } from "lucide-react"
import { Link } from "@/components/Link"
import { canFile, contains, date, dateTime, fileSize, statusLabel, text } from "./format"
import { UploadDocument, type DocType, type DocumentRecord, type Folder } from "./UploadDocument"
import { FolderTree } from "./FolderTree"
import { indexFolders, isStandardFolder } from "./folders"
import { Badge, Button, Confirm, DataTable, Drawer, Facts, LoadState, PageHeader, SearchBox, Section, Select, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData, useOpenRecord } from "./useApiData"
import { downloadBlob, useBlobUrl } from "./useBlobUrl"
import { UploadResult } from "./UploadResult"
import { t } from "./i18n"

type Doc = DocumentRecord & {
  description: string | null; mime_type: string; file_size: number; sync_status: string
  related_party_name: string | null; related_party_external_id: string | null
  property_listing_id: number | null; property_listing_title: string | null; transaction_reference: string | null
  uploaded_by_name: string | null; created_at: string; updated_at: string; archived_at: string | null
  extracted_fields: Record<string, unknown>
  processing: {
    status?: string; error_reason?: string | null; validation_result?: { valid?: boolean; errors?: ValidationError[]; warnings?: string[] }
    // Older results store plain IDs; newer ones {id, matched_by}.
    matched_entities?: Record<string, Matched | string | number | null>
    created_records?: string[]; updated_records?: string[]; processed_at?: string; filed_to?: string
  }
}
type Matched = { id: string | number; matched_by?: string }
// The server sends {field, message}; older results may hold plain text.
type ValidationError = string | { field?: string; message?: string }
const validationText = (e: ValidationError) =>
  typeof e === "string" ? e : [e.field ? statusLabel(e.field) : "", e.message ?? ""].filter(Boolean).join(": ")
type Summary = { total: number; success: number; failed: number; processing: number; archived: number; superseded: number }
type AuditEvent = { id: number; version: number; event_type: string; actor: string | null; created_at: string; details: Record<string, unknown> }

const STATUSES = ["SUCCESS", "FAILED", "PROCESSING", "ARCHIVED"]

export function DocumentsPage() {
  const { api, user } = useStaffAuth()
  const { id, open, close } = useOpenRecord()
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("")
  const [type, setType] = useState("")
  const [folder, setFolder] = useState<number | null>(null)
  const [uploading, setUploading] = useState(false)
  const [creatingFolder, setCreatingFolder] = useState(false)
  const [result, setResult] = useState<{ doc: DocumentRecord; newFolder: boolean } | null>(null)
  const [deletingFolder, setDeletingFolder] = useState(false)
  const [folderBusy, setFolderBusy] = useState(false)
  const toast = useToast()

  const load = useCallback(() => Promise.all([
    api<Doc[]>("/documents?limit=1000"),
    api<Summary>("/documents/summary"),
    api<Folder[]>("/documents/folders"),
    api<DocType[]>("/documents/types"),
  ]), [api])
  const { data, error, loading, reload } = useApiData(load, "documents")
  const [docs, summary, folders, types] = data ?? [[], null, [], []]
  const typeLabel = useMemo(() => Object.fromEntries(types.map((dt) => [dt.code, dt.label])), [types])
  const label = (code: string) => (typeLabel[code] ? t(typeLabel[code]) : statusLabel(code))

  const index = useMemo(() => indexFolders(folders), [folders])
  const inFolder = useMemo(() => (folder === null ? null : index.within(folder)), [index, folder])
  const shown = useMemo(() => docs.filter((d) =>
    (inFolder === null || (d.folder_id != null && inFolder.has(d.folder_id))) && (!status || d.status === status) && (!type || d.document_type === type) &&
    contains([d.document_name, d.document_type, d.document_id, d.related_party_name, d.property_listing_title, d.transaction_reference, d.folder_path, d.processing_error], search)),
  [docs, inFolder, status, type, search])
  const selected = id ? docs.find((d) => d.document_id === id) ?? null : null
  // Per folder, including everything filed in its sub-folders.
  const counts = useMemo(() => {
    const parentOf = new Map(folders.map((f) => [f.id, f.parent_id]))
    const out = new Map<number, number>()
    for (const d of docs) {
      const seen = new Set<number>()
      for (let fid = d.folder_id; fid != null && !seen.has(fid); fid = parentOf.get(fid) ?? null) {
        seen.add(fid)
        out.set(fid, (out.get(fid) ?? 0) + 1)
      }
    }
    return out
  }, [docs, folders])

  // Delete folder: only for a selected folder that isn't one of the standard ones.
  const selectedFolder = folder === null ? null : folders.find((f) => f.id === folder) ?? null
  const standard = selectedFolder ? isStandardFolder(selectedFolder, folders) : false
  const canDeleteFolder = Boolean(selectedFolder) && !standard && canFile(user?.role)
  const deleteFolderTitle = !selectedFolder ? t("Select a folder first")
    : standard ? t("“{name}” is a standard folder and can't be deleted", { name: selectedFolder.name })
    : !canFile(user?.role) ? t("Only filing and management roles can delete folders")
    : t("Delete “{name}”", { name: index.path.get(selectedFolder.id) ?? selectedFolder.name })
  const removeFolder = async () => {
    if (!selectedFolder) return
    setFolderBusy(true)
    try {
      const done = await api<{ deleted: string; moved_documents: number; moved_to: string | null }>(`/documents/folders/${selectedFolder.id}`, { method: "DELETE" })
      toast(done.moved_documents
        ? t("Deleted “{name}”. {n} document(s) moved to {dest}.", { name: done.deleted, n: done.moved_documents, dest: done.moved_to ?? t("All documents (no folder)") })
        : t("Deleted “{name}”.", { name: done.deleted }))
      setFolder(selectedFolder.parent_id)
      setDeletingFolder(false)
      void reload()
    } catch (deleteError) {
      toast((deleteError as Error).message, "error")
    } finally {
      setFolderBusy(false)
    }
  }

  const columns: Column<Doc>[] = [
    {
      key: "name", label: "Document", sort: (d) => d.document_name,
      render: (d) => (
        <span className="min-w-0">
          <span className="block truncate font-semibold">{d.document_name}</span>
          <span className="block truncate text-xs text-ab-faint">{label(d.document_type)} · v{d.version}</span>
        </span>
      ),
    },
    { key: "related", label: "Related to", sort: (d) => d.related_party_name ?? d.property_listing_title ?? "", render: (d) => <span className="line-clamp-2">{[d.related_party_name, d.property_listing_title].filter(Boolean).join(" · ") || "—"}</span> },
    { key: "folder", label: "Folder", sort: (d) => d.folder_path ?? "", render: (d) => <span className="line-clamp-2">{text(d.folder_path ?? d.folder_name)}</span>, hideOnPhone: true },
    { key: "uploaded", label: "Uploaded", sort: (d) => d.created_at, render: (d) => date(d.created_at) },
    {
      key: "status", label: "Status", sort: (d) => d.status,
      render: (d) => (
        <span className="flex flex-col items-start gap-0.5">
          <Badge value={d.status} />
          {d.status === "FAILED" && d.processing_error && <span className="line-clamp-1 max-w-56 text-[11px] text-ab-danger">{d.processing_error}</span>}
        </span>
      ),
    },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Document Repository"
        subtitle="Upload documents and ALTY processes them automatically: it reads, classifies and matches each one, then records the property, client, agent and transaction it describes. Failed documents show the stage and reason."
        actions={
          <>
            <Button onClick={() => setCreatingFolder(true)}><FolderPlus className="h-4 w-4" /> {t("New folder")}</Button>
            <Button variant="danger" onClick={() => setDeletingFolder(true)} disabled={!canDeleteFolder} title={deleteFolderTitle}>
              <FolderX className="h-4 w-4" /> {t("Delete folder")}
            </Button>
            <Button variant="primary" onClick={() => setUploading(true)} disabled={!data}><UploadCloud className="h-4 w-4" /> {t("Upload document")}</Button>
          </>
        }
      />
      {summary && (
        <Tiles items={[
          { label: "All documents", value: summary.total, onClick: () => setStatus(""), active: !status },
          { label: "Processed", value: summary.success, onClick: () => setStatus(status === "SUCCESS" ? "" : "SUCCESS"), active: status === "SUCCESS" },
          { label: "Failed", value: summary.failed, onClick: () => setStatus(status === "FAILED" ? "" : "FAILED"), active: status === "FAILED" },
          { label: "Processing", value: summary.processing, onClick: () => setStatus(status === "PROCESSING" ? "" : "PROCESSING"), active: status === "PROCESSING" },
          { label: "Archived", value: summary.archived, onClick: () => setStatus(status === "ARCHIVED" ? "" : "ARCHIVED"), active: status === "ARCHIVED" },
        ]} />
      )}
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <div className="grid gap-5 lg:grid-cols-[250px_1fr]">
          <nav aria-label={t("Folders")} className="hidden lg:block">
            <p className="px-2 pb-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-ab-faint">{t("Folders")}</p>
            <FolderTree index={index} counts={counts} total={docs.length} selected={folder} onSelect={setFolder} />
          </nav>
          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap gap-2 sm:flex-nowrap">
              <div className="w-full sm:w-auto sm:flex-1"><SearchBox value={search} onChange={setSearch} placeholder="Search name, client, property, reference or error" /></div>
              <div className="lg:hidden">
                <Select label="Folder" value={folder === null ? "" : String(folder)} onChange={(v) => setFolder(v ? Number(v) : null)}
                  options={[{ value: "", label: "All folders" }, ...index.options]} />
              </div>
              <Select label="Type" value={type} onChange={setType} options={[{ value: "", label: "All types" }, ...types.filter((dt) => dt.code !== "AUTO").map((dt) => ({ value: dt.code, label: dt.label }))]} />
              <Select label="Status" value={status} onChange={setStatus} options={[{ value: "", label: "All statuses" }, ...STATUSES.map((s) => ({ value: s, label: statusLabel(s) }))]} />
            </div>
            <p className="text-xs text-ab-faint">{t("{n} of {total} documents", { n: shown.length, total: docs.length })}</p>
            <DataTable rows={shown} columns={columns} rowKey={(d) => d.document_id} onOpen={(d) => open(d.document_id)}
              empty={docs.length ? "No documents match these filters." : "No documents yet. Upload one to get started."} initialSort={{ key: "uploaded", dir: "desc" }} />
          </div>
        </div>
      )}
      {selected && (
        <DocumentDrawer doc={selected} types={types} folders={folders} label={label} canEdit={canFile(user?.role)}
          onClose={close} onChanged={reload} onDeleted={() => { close(); void reload() }} />
      )}
      {uploading && (
        <UploadDocument
          types={types} folders={folders} defaultFolder={folder}
          onClose={() => setUploading(false)}
          onUploaded={(doc) => {
            setUploading(false)
            // A folder ALTY created while filing this document wasn't in the list before.
            setResult({ doc, newFolder: doc.folder_id != null && !folders.some((f) => f.id === doc.folder_id) })
            void reload()
          }}
        />
      )}
      {result && (
        <UploadResult
          doc={result.doc}
          newFolder={result.newFolder}
          onClose={() => setResult(null)}
          onView={() => { const docId = result.doc.document_id; setResult(null); open(docId) }}
          onOpenFolder={() => { setFolder(result.doc.folder_id); setStatus(""); setType(""); setSearch(""); setResult(null) }}
          onUploadAnother={() => { setResult(null); setUploading(true) }}
        />
      )}
      {deletingFolder && selectedFolder && (
        <Confirm
          typeToConfirm="Delete"
          title="Delete folder?"
          message={t("Delete the folder “{path}”{sub}? The {n} document(s) inside are kept and move to {dest}. This can't be undone.", {
            path: index.path.get(selectedFolder.id) ?? selectedFolder.name,
            sub: index.within(selectedFolder.id).size > 1 ? t(" and its {n} sub-folder(s)", { n: index.within(selectedFolder.id).size - 1 }) : "",
            n: counts.get(selectedFolder.id) ?? 0,
            dest: selectedFolder.parent_id != null ? index.path.get(selectedFolder.parent_id) ?? "" : t("All documents (no folder)"),
          })}
          confirmLabel="Delete"
          busy={folderBusy}
          onConfirm={() => void removeFolder()}
          onCancel={() => setDeletingFolder(false)}
        />
      )}
      {creatingFolder && <NewFolder folders={folders} onClose={() => setCreatingFolder(false)} onCreated={() => { setCreatingFolder(false); void reload() }} />}
    </div>
  )
}

function NewFolder({ folders, onClose, onCreated }: { folders: Folder[]; onClose: () => void; onCreated: () => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const [name, setName] = useState("")
  const [parent, setParent] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!name.trim()) return setError(t("Enter a folder name."))
    setBusy(true)
    try {
      await api("/documents/folders", { method: "POST", body: JSON.stringify({ name: name.trim(), parent_id: parent ? Number(parent) : null }) })
      toast(t("Folder “{name}” created.", { name: name.trim() }))
      onCreated()
    } catch (createError) {
      setError((createError as Error).message)
      setBusy(false)
    }
  }
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={t("New folder")}>
      <button type="button" aria-label={t("Cancel")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={submit} className="ab-pop relative w-full max-w-sm rounded-2xl border border-ab-border bg-ab-card p-5 shadow-2xl">
        <h2 className="text-lg font-bold">{t("New folder")}</h2>
        <label className="mt-4 block text-sm font-medium">{t("Name")}
          <input autoFocus className="mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none" value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="mt-3 block text-sm font-medium">{t("Inside")}
          <select className="mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm" value={parent} onChange={(e) => setParent(e.target.value)}>
            <option value="">{t("Top level")}</option>
            {indexFolders(folders).options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
        {error && <p role="alert" className="mt-3 text-sm text-ab-danger">{error}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button>
          <Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Create")}</Button>
        </div>
      </form>
    </div>
  )
}

const RECORD_LINKS: Record<string, string> = { clients: "/manage/clients", transactions: "/manage/transactions", property_listings: "/manage/properties", agents: "/manage/agents" }

function recordLink(ref: string) {
  const [table, idPart, field] = ref.split(":")
  const base = RECORD_LINKS[table]
  const textLabel = `${statusLabel(table.replace(/s$/, "").replace("property_listing", "property"))} ${idPart.length > 12 ? idPart.slice(0, 8) : idPart}${field ? ` (${statusLabel(field)})` : ""}`
  return base ? <Link key={ref} to={`${base}?id=${idPart}`} className="mr-2 inline-block hover:underline">{textLabel}</Link> : <span key={ref} className="mr-2">{textLabel}</span>
}

function DocumentDrawer({ doc, types, folders, label, canEdit, onClose, onChanged, onDeleted }: {
  doc: Doc; types: DocType[]; folders: Folder[]; label: (code: string) => string; canEdit: boolean
  onClose: () => void; onChanged: () => Promise<void>; onDeleted: () => void
}) {
  const { api, apiBlob } = useStaffAuth()
  const toast = useToast()
  const [busy, setBusy] = useState("")
  const [preview, setPreview] = useState(false)
  const [newVersion, setNewVersion] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [editing, setEditing] = useState(false)
  const [versionResult, setVersionResult] = useState<DocumentRecord | null>(null)
  const [meta, setMeta] = useState({ document_name: doc.document_name, folder_id: doc.folder_id ? String(doc.folder_id) : "", description: doc.description ?? "" })
  const [reprocessType, setReprocessType] = useState("")
  const loadExtra = useCallback(() => Promise.all([
    api<Doc[]>(`/documents/${encodeURIComponent(doc.document_id)}/versions`),
    api<AuditEvent[]>(`/documents/${encodeURIComponent(doc.document_id)}/audit`),
  ]), [api, doc.document_id])
  const extra = useApiData(loadExtra)
  const previewable = doc.mime_type === "application/pdf" || doc.mime_type.startsWith("image/")
  const matched = Object.fromEntries(Object.entries(doc.processing?.matched_entities ?? {}).map(([key, value]) => [
    key,
    value && typeof value === "object" ? { id: String(value.id), by: value.matched_by } : value != null ? { id: String(value), by: undefined } : null,
  ])) as Record<string, { id: string; by?: string } | null>
  const how = (entry: { by?: string } | null | undefined) => (entry?.by ? <span className="ml-1 text-xs font-normal text-ab-faint">({statusLabel(entry.by)})</span> : null)
  const fields = Object.entries(doc.extracted_fields ?? {}).filter(([, v]) => v !== null && v !== "")

  const act = async (name: string, run: () => Promise<unknown>, done: string) => {
    setBusy(name)
    try {
      await run()
      toast(t(done))
      await onChanged()
      extra.reload()
    } catch (error) {
      toast((error as Error).message, "error")
    } finally {
      setBusy("")
    }
  }
  const path = `/documents/${encodeURIComponent(doc.document_id)}`

  return (
    <Drawer
      title={doc.document_name}
      subtitle={<span className="flex flex-wrap items-center gap-2"><Badge value={doc.status} /> {label(doc.document_type)} · v{doc.version} · {fileSize(doc.file_size)}</span>}
      onClose={onClose}
      footer={
        <>
          {canEdit && <Button variant="danger" onClick={() => setConfirmDelete(true)}><Trash2 className="h-4 w-4" /> {t("Delete")}</Button>}
          {previewable && <Button onClick={() => setPreview(true)}><Eye className="h-4 w-4" /> {t("Preview")}</Button>}
          <Button variant="primary" disabled={busy === "download"}
            onClick={() => act("download", () => downloadBlob(apiBlob, `${path}/download`, doc.document_name), "Download started.")}>
            <Download className="h-4 w-4" /> {t("Download")}
          </Button>
        </>
      }
    >
      {doc.status === "FAILED" && (
        <div role="alert" className="rounded-2xl border border-ab-danger/50 bg-ab-danger/10 p-4">
          <p className="text-sm font-extrabold uppercase tracking-wide text-ab-danger">{t("Failed")}{doc.processing_stage ? ` · ${t("{stage} stage", { stage: statusLabel(doc.processing_stage) })}` : ""}</p>
          <p className="mt-1 text-sm"><span className="font-semibold">{t("Reason:")}</span> {doc.processing_error ?? doc.processing?.error_reason ?? t("Not recorded")}</p>
          {doc.processing?.validation_result?.errors?.length ? (
            <ul className="mt-2 list-disc pl-5 text-xs text-ab-muted">{doc.processing.validation_result.errors.map((e, i) => <li key={i}>{validationText(e)}</li>)}</ul>
          ) : null}
        </div>
      )}

      {canEdit && (
        <Section title="Actions">
          <div className="flex flex-wrap gap-2">
            {doc.status === "ARCHIVED" ? (
              <Button disabled={!!busy} onClick={() => act("restore", () => api(`${path}/restore`, { method: "POST" }), "Document restored.")}>
                <ArchiveRestore className="h-4 w-4" /> {t("Restore")}
              </Button>
            ) : (
              <Button disabled={!!busy} onClick={() => act("archive", () => api(`${path}/archive`, { method: "POST" }), "Document archived.")}>
                <Archive className="h-4 w-4" /> {t("Archive")}
              </Button>
            )}
            <Button disabled={!!busy} onClick={() => setNewVersion(true)}><FilePlus2 className="h-4 w-4" /> {t("New version")}</Button>
            <Button disabled={!!busy} onClick={() => setEditing((v) => !v)}>{t("Edit details")}</Button>
          </div>
          {doc.status !== "ARCHIVED" && doc.status !== "SUPERSEDED" && (
            <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-ab-border pt-3">
              <Select label="Reprocess as" value={reprocessType} onChange={setReprocessType}
                options={[{ value: "", label: "Reprocess (same type)" }, ...types.filter((dt) => dt.code !== "AUTO").map((dt) => ({ value: dt.code, label: t("Reprocess as {type}", { type: t(dt.label) }) }))]} />
              <Button disabled={!!busy} onClick={() => act("reprocess", () => api(`${path}/reprocess`, { method: "POST", body: JSON.stringify(reprocessType ? { document_type: reprocessType } : {}) }), "Document reprocessed.")}>
                {busy === "reprocess" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} {t("Reprocess")}
              </Button>
            </div>
          )}
          {editing && (
            <form
              className="mt-3 grid gap-3 border-t border-ab-border pt-3 sm:grid-cols-2"
              onSubmit={(e) => {
                e.preventDefault()
                const body: Record<string, unknown> = {}
                if (meta.document_name.trim() && meta.document_name.trim() !== doc.document_name) body.document_name = meta.document_name.trim()
                if ((meta.folder_id || null) !== (doc.folder_id ? String(doc.folder_id) : null)) body.folder_id = meta.folder_id ? Number(meta.folder_id) : null
                if (meta.description !== (doc.description ?? "")) body.description = meta.description || null
                if (!Object.keys(body).length) return setEditing(false)
                void act("edit", () => api(path, { method: "PUT", body: JSON.stringify(body) }), "Details saved.").then(() => setEditing(false))
              }}
            >
              <label className="text-sm font-medium sm:col-span-2">{t("Name")}
                <input className="mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm" value={meta.document_name} onChange={(e) => setMeta({ ...meta, document_name: e.target.value })} />
              </label>
              <label className="text-sm font-medium">{t("Folder")}
                <select className="mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm" value={meta.folder_id} onChange={(e) => setMeta({ ...meta, folder_id: e.target.value })}>
                  <option value="">{t("No folder")}</option>
                  {indexFolders(folders).options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </label>
              <label className="text-sm font-medium">{t("Description")}
                <input className="mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm" value={meta.description} onChange={(e) => setMeta({ ...meta, description: e.target.value })} />
              </label>
              <div className="flex justify-end gap-2 sm:col-span-2">
                <Button onClick={() => setEditing(false)}>{t("Cancel")}</Button>
                <Button type="submit" variant="primary" disabled={!!busy}>{t("Save")}</Button>
              </div>
            </form>
          )}
        </Section>
      )}

      <Section title="What ALTY recorded">
        <Facts items={[
          ["Property", matched.property ? <><Link to={`/manage/properties?id=${matched.property.id}`} className="hover:underline">{text(doc.property_listing_title)} (#{matched.property.id})</Link>{how(matched.property)}</> : doc.property_listing_title],
          ["Client", matched.client ? <><Link to={`/manage/clients?id=${matched.client.id}`} className="hover:underline">{text(doc.related_party_name)}</Link>{how(matched.client)}</> : doc.related_party_name],
          ["Agent", matched.agent ? <><Link to={`/manage/agents?id=${matched.agent.id}`} className="hover:underline">{matched.agent.id}</Link>{how(matched.agent)}</> : null],
          ["Transaction", matched.transaction ? <><Link to={`/manage/transactions?id=${matched.transaction.id}`} className="font-mono text-xs hover:underline">{matched.transaction.id.slice(0, 8)}</Link>{how(matched.transaction)}</> : doc.transaction_reference],
        ]} />
        {(doc.processing?.created_records?.length || doc.processing?.updated_records?.length) ? (
          <div className="mt-3 space-y-1 text-xs text-ab-muted">
            {doc.processing.created_records?.length ? <p><span className="font-semibold text-ab-text">{t("Created:")}</span> {doc.processing.created_records.map(recordLink)}</p> : null}
            {doc.processing.updated_records?.length ? <p><span className="font-semibold text-ab-text">{t("Updated:")}</span> {doc.processing.updated_records.map(recordLink)}</p> : null}
          </div>
        ) : null}
      </Section>

      {fields.length > 0 && (
        <Section title="Extracted information">
          <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-2">
            {fields.map(([key, value]) => (
              <div key={key} className="min-w-0">
                <dt className="text-xs text-ab-faint">{statusLabel(key)}</dt>
                <dd className="break-words font-medium">{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd>
              </div>
            ))}
          </dl>
        </Section>
      )}

      <Section title="File">
        <Facts items={[
          ["Folder", doc.folder_path ?? doc.folder_name],
          ["Description", doc.description],
          ["Uploaded by", doc.uploaded_by_name],
          ["Uploaded", dateTime(doc.created_at)],
          ["Processed", doc.processing?.processed_at ? dateTime(doc.processing.processed_at) : null],
          ["Sync status", statusLabel(doc.sync_status)],
          ["Document ID", <span className="break-all font-mono text-xs">{doc.document_id}</span>],
          ["Format", doc.mime_type],
        ]} />
      </Section>

      <Section title="Versions & audit trail">
        <LoadState loading={extra.loading} error={extra.error} onRetry={extra.reload} />
        {extra.data && (
          <>
            <ul className="space-y-1.5 text-sm">
              {extra.data[0].map((v) => (
                <li key={v.version} className="flex items-center justify-between gap-2">
                  <span>v{v.version} · {date(v.created_at)} · <Badge value={v.status} /></span>
                  <button type="button" className="text-xs font-semibold text-ab-accent hover:underline"
                    onClick={() => act("download", () => downloadBlob(apiBlob, `${path}/download?version=${v.version}`, v.document_name), "Download started.")}>
                    {t("Download")}
                  </button>
                </li>
              ))}
            </ul>
            <ol className="relative mt-4 space-y-2 border-l border-ab-border pl-4">
              {extra.data[1].map((e) => (
                <li key={e.id} className="text-xs">
                  <span className="absolute -left-[4px] mt-1 h-2 w-2 rounded-full bg-ab-border-strong" aria-hidden />
                  <span className="font-semibold text-ab-text">{statusLabel(e.event_type)}</span>
                  <span className="text-ab-faint"> · v{e.version} · {text(e.actor)} · {dateTime(e.created_at)}</span>
                </li>
              ))}
            </ol>
          </>
        )}
      </Section>

      {preview && <Preview path={`${path}/download`} name={doc.document_name} onClose={() => setPreview(false)} />}
      {newVersion && (
        <UploadDocument types={types} folders={folders} versionOf={doc}
          onClose={() => setNewVersion(false)}
          onUploaded={(next) => {
            setNewVersion(false)
            setVersionResult(next)
            void onChanged()
            extra.reload()
          }}
        />
      )}
      {versionResult && (
        <UploadResult doc={versionResult} newFolder={false} isVersion
          onClose={() => setVersionResult(null)} onView={() => setVersionResult(null)} />
      )}
      {confirmDelete && (
        <Confirm typeToConfirm="Delete"
          title="Delete document?"
          message={t("Deletes “{name}” and all its versions and files. The audit history is kept. Records it created (clients, transactions) are not removed. This can't be undone — consider Archive instead.", { name: doc.document_name })}
          confirmLabel="Delete"
          busy={busy === "delete"}
          onCancel={() => setConfirmDelete(false)}
          onConfirm={() => void (async () => {
            setBusy("delete")
            try {
              await api(path, { method: "DELETE" })
              toast(t("Document deleted."))
              onDeleted()
            } catch (error) {
              toast((error as Error).message, "error")
              setBusy("")
              setConfirmDelete(false)
            }
          })()}
        />
      )}
    </Drawer>
  )
}

function Preview({ path, name, onClose }: { path: string; name: string; onClose: () => void }) {
  const { url, error, type } = useBlobUrl(path)
  return (
    <div className="fixed inset-0 z-[75] flex flex-col bg-black/85 p-3 sm:p-6" role="dialog" aria-modal="true" aria-label={t("Preview of {name}", { name })}>
      <div className="mb-2 flex items-center justify-between text-white">
        <p className="truncate text-sm font-semibold">{name}</p>
        <button type="button" onClick={onClose} aria-label={t("Close preview")} className="rounded-lg p-2 hover:bg-white/10"><X className="h-5 w-5" /></button>
      </div>
      <div className="flex min-h-0 flex-1 items-center justify-center overflow-hidden rounded-xl bg-ab-card">
        {error ? <p className="text-sm text-ab-danger">{error}</p> : !url ? (
          <LoaderCircle className="h-6 w-6 animate-spin text-ab-accent" />
        ) : type.startsWith("image/") ? (
          <img src={url} alt={name} className="max-h-full max-w-full object-contain" />
        ) : (
          <iframe src={url} title={name} className="h-full w-full bg-white" />
        )}
      </div>
    </div>
  )
}
