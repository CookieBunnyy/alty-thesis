// The recruitment form an applicant filled in, as photos or scans (one per
// page). The Filing Manager uploads them; everyone with Recruitment sees them.
import { useRef, useState } from "react"
import { Camera, ExternalLink, FileText, LoaderCircle, Trash2, Upload, X } from "lucide-react"
import { Button, Confirm, Section } from "./ui"
import { dateTime } from "./format"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useBlobUrl } from "./useBlobUrl"
import { t } from "./i18n"
import { FORM_ACCEPT, uploadForms, type ApplicantFormFile } from "./recruitmentFormsApi"

const apiPath = (url: string) => url.replace(/^\/api\/v1/, "")

function FormThumb({ form, onOpen, onDelete }: { form: ApplicantFormFile; onOpen: () => void; onDelete: () => void }) {
  const isImage = form.mime_type.startsWith("image/")
  const { url } = useBlobUrl(isImage ? apiPath(form.url) : null)
  return (
    <li className="group relative overflow-hidden rounded-xl border border-ab-border bg-ab-card-2">
      <button type="button" onClick={onOpen} className="block w-full text-left" aria-label={t("Open {file}", { file: form.file_name })}>
        {isImage
          ? (url ? <img src={url} alt="" className="h-36 w-full bg-white object-contain" /> : <span className="block h-36 animate-pulse bg-ab-card" />)
          : <span className="flex h-36 flex-col items-center justify-center gap-1 text-ab-muted"><FileText className="h-8 w-8" /> PDF</span>}
        <span className="block truncate px-2 pt-1.5 text-xs font-semibold">{form.file_name}</span>
        <span className="block truncate px-2 pb-1.5 text-[11px] text-ab-faint">{dateTime(form.uploaded_at)}{form.uploaded_by ? ` · ${form.uploaded_by}` : ""}</span>
      </button>
      <button type="button" onClick={onDelete} aria-label={t("Remove {file}", { file: form.file_name })}
        className="absolute right-1.5 top-1.5 rounded-lg bg-black/60 p-1.5 text-white opacity-90 hover:bg-ab-danger">
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </li>
  )
}

/** Full-size view of one page (images), or the PDF in the browser's viewer. */
function FormViewer({ form, onClose }: { form: ApplicantFormFile; onClose: () => void }) {
  const { url, error } = useBlobUrl(apiPath(form.url))
  return (
    <div className="fixed inset-0 z-[90] flex flex-col bg-black/90" role="dialog" aria-modal="true" aria-label={form.file_name}>
      <header className="flex items-center gap-2 px-4 py-3 text-white">
        <p className="min-w-0 flex-1 truncate text-sm font-semibold">{form.file_name}</p>
        {url && <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm hover:bg-white/10"><ExternalLink className="h-4 w-4" /> {t("Open in new tab")}</a>}
        <button type="button" onClick={onClose} aria-label={t("Close")} className="rounded-lg p-2 hover:bg-white/10"><X className="h-5 w-5" /></button>
      </header>
      <div className="flex min-h-0 flex-1 items-center justify-center p-3">
        {error && <p className="text-sm text-white">{t(error)}</p>}
        {!url && !error && <LoaderCircle className="h-8 w-8 animate-spin text-white" />}
        {url && (form.mime_type.startsWith("image/")
          ? <img src={url} alt={form.file_name} className="max-h-full max-w-full bg-white object-contain" />
          : <iframe src={url} title={form.file_name} className="h-full w-full rounded-lg bg-white" />)}
      </div>
    </div>
  )
}

export function RecruitmentForms({ applicantId, forms, onChanged }: { applicantId: number; forms: ApplicantFormFile[]; onChanged: () => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const picker = useRef<HTMLInputElement>(null)
  const camera = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [viewing, setViewing] = useState<ApplicantFormFile | null>(null)
  const [removing, setRemoving] = useState<ApplicantFormFile | null>(null)

  const upload = async (files: FileList | null) => {
    if (!files?.length) return
    setBusy(true)
    const failed = await uploadForms(api, applicantId, [...files])
    setBusy(false)
    if (failed.length) toast(t("These pages didn't upload (use a photo or a PDF up to the size limit): {files}", { files: failed.join(", ") }), "error")
    else toast(t("Recruitment form uploaded."))
    onChanged()
  }
  const remove = async () => {
    if (!removing) return
    setBusy(true)
    try {
      await api(`/recruitment/applicants/${applicantId}/forms/${removing.id}`, { method: "DELETE" })
      toast(t("Removed {file}.", { file: removing.file_name }))
      onChanged()
    } catch (removeError) {
      toast(t((removeError as Error).message), "error")
    } finally {
      setBusy(false)
      setRemoving(null)
    }
  }

  return (
    <Section title={t("Recruitment form")}>
      <p className="mb-2 text-xs text-ab-muted">{t("Photos or scans of the recruitment form the applicant filled in, one per page.")}</p>
      {forms.length > 0 && (
        <ul className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
          {forms.map((form) => <FormThumb key={form.id} form={form} onOpen={() => setViewing(form)} onDelete={() => setRemoving(form)} />)}
        </ul>
      )}
      {forms.length === 0 && <p className="mb-3 rounded-xl border border-dashed border-ab-warning/60 bg-ab-warning/5 p-3 text-sm">{t("No recruitment form uploaded yet.")}</p>}
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => picker.current?.click()} disabled={busy}>
          {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />} {t(forms.length ? "Add pages" : "Upload recruitment form")}
        </Button>
        <Button onClick={() => camera.current?.click()} disabled={busy}><Camera className="h-4 w-4" /> {t("Take a photo")}</Button>
      </div>
      <input ref={picker} type="file" accept={FORM_ACCEPT} multiple className="sr-only" aria-label={t("Recruitment form pages")}
        onChange={(e) => { void upload(e.target.files); e.target.value = "" }} />
      <input ref={camera} type="file" accept="image/*" capture="environment" className="sr-only" aria-label={t("Take a photo")}
        onChange={(e) => { void upload(e.target.files); e.target.value = "" }} />
      {viewing && <FormViewer form={viewing} onClose={() => setViewing(null)} />}
      {removing && (
        <Confirm title={t("Remove this page?")} confirmLabel={t("Remove")} busy={busy} onConfirm={() => void remove()} onCancel={() => setRemoving(null)}
          message={t("Remove {file} from the applicant's recruitment form?", { file: removing.file_name })} />
      )}
    </Section>
  )
}

/** Pick the form pages while recording a new applicant (uploaded after saving). */
export function FormFilePicker({ files, onChange }: { files: File[]; onChange: (files: File[]) => void }) {
  const picker = useRef<HTMLInputElement>(null)
  return (
    <div className="rounded-xl border border-dashed border-ab-border-strong p-3 sm:col-span-2">
      <p className="text-sm font-semibold">{t("Recruitment form (photo or scan)")}</p>
      <p className="text-xs text-ab-muted">{t("Upload the form the applicant filled in, one picture per page. You can add more later.")}</p>
      {files.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`} className="inline-flex items-center gap-1 rounded-full bg-ab-card-2 px-2.5 py-1 text-xs">
              {file.name}
              <button type="button" aria-label={t("Remove {file}", { file: file.name })} onClick={() => onChange(files.filter((_, i) => i !== index))} className="text-ab-muted hover:text-ab-danger"><X className="h-3 w-3" /></button>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2"><Button onClick={() => picker.current?.click()}><Upload className="h-4 w-4" /> {t(files.length ? "Add pages" : "Choose files")}</Button></div>
      <input ref={picker} type="file" accept={FORM_ACCEPT} multiple className="sr-only" aria-label={t("Recruitment form pages")}
        onChange={(e) => { onChange([...files, ...(e.target.files ? [...e.target.files] : [])]); e.target.value = "" }} />
    </div>
  )
}
