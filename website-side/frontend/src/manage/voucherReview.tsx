// Commission vouchers: every "label: value" pair read from the document, the
// fields management configured, a person's corrections and verification, and
// the link to the commission record (/documents/{id}/extraction, /schemas).
import { useCallback, useState, type FormEvent } from "react"
import { BadgeCheck, LoaderCircle, Plus, Settings2, Trash2, X } from "lucide-react"
import { dateTime, peso } from "./format"
import { Button, LoadState, Section } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData } from "./useApiData"
import { t } from "./i18n"

type SchemaField = { key: string; label: string; aliases: string[]; type: string; required: boolean }
type Extraction = {
  document_id: string; document_type: string; schema: SchemaField[]
  detected_pairs: { label: string; value: string; line: number }[]
  mapped_fields: Record<string, string>; verified_fields: Record<string, string>
  links: { commission_id?: number; agent_id?: string; listing_id?: number; transaction_id?: string }
  verification_status: "NEEDS_REVIEW" | "VERIFIED" | null; verified_by: string | null; verified_at: string | null
  linked_commissions: number[]
}
type CommissionOption = { id: number; seller_name: string | null; property_title: string | null; property_description: string | null; amount: number; kind: string }

const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"

export function VoucherReview({ documentId, canEdit }: { documentId: string; canEdit: boolean }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const load = useCallback(() => Promise.all([
    api<Extraction>(`/documents/${encodeURIComponent(documentId)}/extraction`),
    api<CommissionOption[]>("/commissions"),
  ]), [api, documentId])
  const { data, error, loading, reload } = useApiData(load)
  const [extraction, commissionOptions] = data ?? [null, []]
  const [edits, setEdits] = useState<Record<string, string>>({})
  const [commission, setCommission] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const value = (key: string) => edits[key] ?? extraction?.verified_fields[key] ?? extraction?.mapped_fields[key] ?? ""
  const linked = commission ?? (extraction?.links.commission_id ? String(extraction.links.commission_id) : "")
  const save = async (verify: boolean, event?: FormEvent) => {
    event?.preventDefault()
    if (!extraction) return
    setBusy(true)
    try {
      await api(`/documents/${encodeURIComponent(documentId)}/extraction`, {
        method: "PUT",
        body: JSON.stringify({ fields: Object.fromEntries(extraction.schema.map((f) => [f.key, value(f.key) || null])), commission_id: linked ? Number(linked) : null, verify }),
      })
      toast(t(verify ? "Voucher verified." : "Saved."))
      setEdits({})
      await reload()
    } catch (saveError) {
      toast(t((saveError as Error).message), "error")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section title="Commission voucher review">
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {extraction && (
        <form className="space-y-4 text-sm" onSubmit={(e) => void save(true, e)}>
          <p className={`flex items-center gap-2 rounded-xl px-3 py-2 ${extraction.verification_status === "VERIFIED" ? "bg-ab-success/10 text-ab-success" : "bg-ab-warning/10 text-ab-warning"}`}>
            {extraction.verification_status === "VERIFIED" ? <BadgeCheck className="h-4 w-4" aria-hidden /> : null}
            {extraction.verification_status === "VERIFIED"
              ? t("Verified by {name}, {when}", { name: extraction.verified_by ?? "", when: dateTime(extraction.verified_at) })
              : t("Needs review: check what was read, correct it, and link the commission.")}
          </p>

          <div>
            <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("Everything read from the voucher")}</p>
            {extraction.detected_pairs.length === 0 ? <p className="mt-1 italic text-ab-faint">{t("No “label: value” lines were found. Open the file and enter the values below.")}</p> : (
              <dl className="mt-1 divide-y divide-ab-border rounded-xl border border-ab-border">
                {extraction.detected_pairs.map((p, i) => (
                  <div key={`${p.line}-${i}`} className="flex flex-wrap justify-between gap-x-3 px-3 py-1.5">
                    <dt className="text-ab-muted">{p.label}</dt><dd className="break-words font-medium">{p.value || "—"}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>

          <div>
            <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("Voucher fields")}</p>
            {extraction.schema.length === 0 ? (
              <p className="mt-1 text-ab-muted">{t("No voucher fields are set up yet. Once Abellar provides a real commission voucher, management sets its printed labels with Voucher fields (top of this page); until then the values above are kept as read.")}</p>
            ) : (
              <div className="mt-1 grid gap-2 sm:grid-cols-2">
                {extraction.schema.map((f) => (
                  <label key={f.key} className="text-sm font-medium">{f.label}{f.required ? " *" : ""}
                    <input className={field} value={value(f.key)} disabled={!canEdit} onChange={(e) => setEdits((all) => ({ ...all, [f.key]: e.target.value }))} />
                    {extraction.mapped_fields[f.key] && value(f.key) !== extraction.mapped_fields[f.key] && <span className="mt-0.5 block text-xs font-normal text-ab-faint">{t("Read as: {v}", { v: extraction.mapped_fields[f.key] })}</span>}
                  </label>
                ))}
              </div>
            )}
          </div>

          <label className="block text-sm font-medium">{t("Commission record this voucher supports")}
            <select className={field} value={linked} disabled={!canEdit} onChange={(e) => setCommission(e.target.value)}>
              <option value="">{t("Not linked yet")}</option>
              {commissionOptions.map((c) => <option key={c.id} value={c.id}>{[c.seller_name, c.property_title ?? c.property_description, peso(c.amount)].filter(Boolean).join(" · ")}</option>)}
            </select>
          </label>

          {canEdit && (
            <div className="flex flex-wrap justify-end gap-2">
              <Button disabled={busy} onClick={() => void save(false)}>{t("Save without verifying")}</Button>
              <Button type="submit" variant="primary" disabled={busy}>{busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <BadgeCheck className="h-4 w-4" />} {t("Verify")}</Button>
            </div>
          )}
          <p className="text-xs text-ab-faint">{t("The uploaded file itself is never changed; corrections are kept with the document's history.")}</p>
        </form>
      )}
    </Section>
  )
}

/** Management: the printed labels to look for on commission vouchers. */
export function VoucherFieldsDialog({ onClose }: { onClose: () => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const load = useCallback(() => api<{ document_type: string; fields: SchemaField[] }[]>("/documents/schemas"), [api])
  const { data, error, loading, reload } = useApiData(load)
  const current = data?.find((s) => s.document_type === "COMMISSION_VOUCHER")?.fields
  const [rows, setRows] = useState<SchemaField[] | null>(null)
  const fields = rows ?? current ?? []
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState("")
  const update = (index: number, patch: Partial<SchemaField>) => setRows(fields.map((f, i) => (i === index ? { ...f, ...patch } : f)))
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const cleaned = fields.map((f) => ({ ...f, key: f.key.trim() || f.label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, ""), aliases: f.aliases.map((a) => a.trim()).filter(Boolean) }))
    if (cleaned.some((f) => !f.label.trim() || !/^[a-z][a-z0-9_]*$/.test(f.key))) return setProblem(t("Each field needs a printed label (and a key of lowercase letters, numbers and _)."))
    setBusy(true)
    try {
      await api("/documents/schemas/COMMISSION_VOUCHER", { method: "PUT", body: JSON.stringify({ fields: cleaned }) })
      toast(t("Voucher fields saved."))
      onClose()
    } catch (saveError) {
      setProblem(t((saveError as Error).message))
      setBusy(false)
    }
  }
  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={t("Voucher fields")}>
      <button type="button" aria-label={t("Cancel")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={submit} noValidate className="ab-pop relative flex max-h-[94dvh] w-full max-w-3xl flex-col rounded-t-2xl border border-ab-border bg-ab-card shadow-2xl sm:rounded-2xl">
        <header className="flex items-center justify-between border-b border-ab-border px-5 py-4">
          <h2 className="flex items-center gap-2 text-lg font-bold"><Settings2 className="h-5 w-5" aria-hidden /> {t("Commission voucher fields")}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close")} className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><X className="h-4 w-4" /></button>
        </header>
        <div className="space-y-3 overflow-y-auto p-5 text-sm">
          <p className="text-ab-muted">{t("Enter the labels exactly as printed on Abellar's real commission voucher. ALTY fills each field from the line with that label (or one of its other spellings). Leave this empty until a real voucher is available.")}</p>
          <LoadState loading={loading && !data} error={error} onRetry={reload} />
          {fields.map((f, index) => (
            <div key={index} className="grid gap-2 rounded-xl border border-ab-border p-3 sm:grid-cols-[1fr_1fr_8rem_auto]">
              <label className="font-medium">{t("Printed label")}<input className={field} value={f.label} onChange={(e) => update(index, { label: e.target.value })} /></label>
              <label className="font-medium">{t("Other spellings (comma-separated)")}<input className={field} value={f.aliases.join(", ")} onChange={(e) => update(index, { aliases: e.target.value.split(",") })} /></label>
              <label className="font-medium">{t("Type")}
                <select className={field} value={f.type} onChange={(e) => update(index, { type: e.target.value })}>
                  {["text", "money", "date", "number"].map((type) => <option key={type} value={type}>{t(type === "text" ? "Text" : type === "money" ? "Amount" : type === "date" ? "Date" : "Number")}</option>)}
                </select>
              </label>
              <div className="flex items-end gap-2">
                <label className="flex min-h-10 items-center gap-1.5 font-medium"><input type="checkbox" checked={f.required} onChange={(e) => update(index, { required: e.target.checked })} className="h-4 w-4 accent-[var(--color-ab-accent)]" />{t("Required")}</label>
                <button type="button" aria-label={t("Remove field")} onClick={() => setRows(fields.filter((_, i) => i !== index))} className="mb-1 rounded-lg p-2 text-ab-danger hover:bg-ab-hover"><Trash2 className="h-4 w-4" /></button>
              </div>
            </div>
          ))}
          <Button onClick={() => setRows([...fields, { key: "", label: "", aliases: [], type: "text", required: false }])}><Plus className="h-4 w-4" /> {t("Add field")}</Button>
          {problem && <p role="alert" className="text-ab-danger">{problem}</p>}
        </div>
        <footer className="flex justify-end gap-2 border-t border-ab-border px-5 py-3">
          <Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button>
          <Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Save")}</Button>
        </footer>
      </form>
    </div>
  )
}
