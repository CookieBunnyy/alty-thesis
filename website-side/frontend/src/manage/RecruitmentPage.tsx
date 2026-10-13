import { useCallback, useMemo, useState, type FormEvent } from "react"
import { ArrowRight, BadgeCheck, LoaderCircle, Mail, Pencil, Phone, Plus, Trash2, UserPlus, X } from "lucide-react"
import { Link } from "@/components/Link"
import { contains, date, dateTime, statusLabel, text } from "./format"
import { Badge, Button, Confirm, DataTable, Drawer, Facts, LoadState, PageHeader, SearchBox, Section, Select, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData, useOpenRecord } from "./useApiData"
import { t } from "./i18n"
import { useBranchOptions } from "./branches"

type Applicant = {
  id: number; full_name: string; email: string | null; phone_number: string | null; address: string | null
  branch_id: number | null; branch_name: string | null; desired_designation: string | null; source: string | null
  experience_years: number | null; has_license: boolean; license_number: string | null; screening_score: number | null
  interview_on: string | null; status: string; notes: string | null
  history: { status: string; at: string; by: string; note: string | null }[]
  agent_id: string | null; created_by: string | null; created_at: string; updated_at: string
}
type Summary = {
  by_status: Record<string, number>; total: number; open: number; acceptance_rate: number | null
  stages: string[]; closed: string[]; sources: string[]; designations: string[]
}

const NEXT: Record<string, string> = { APPLIED: "SCREENING", SCREENING: "INTERVIEW", INTERVIEW: "APPROVED" }
const STEP_HELP: Record<string, string> = {
  APPLIED: "Check the application and requirements, then move to screening.",
  SCREENING: "Review documents and the screening score, then schedule an interview.",
  INTERVIEW: "After the interview, approve or reject the applicant.",
  APPROVED: "Onboard to create the agent record and assign a branch.",
}

/** Agent recruitment: applicants from application to onboarding (management roles). */
export function RecruitmentPage() {
  const { api } = useStaffAuth()
  const { id, open, close } = useOpenRecord()
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("")
  const [editing, setEditing] = useState<Applicant | "new" | null>(null)
  const load = useCallback(() => Promise.all([api<Applicant[]>("/recruitment/applicants"), api<Summary>("/recruitment/summary")]), [api])
  const { data, error, loading, reload } = useApiData(load, "recruitment")
  const [applicants, summary] = data ?? [null, null]
  const rows = useMemo(() => applicants ?? [], [applicants])
  const shown = rows.filter((a) => (!status || (status === "OPEN" ? NEXT[a.status] || a.status === "APPROVED" : a.status === status)) &&
    contains([a.full_name, a.email, a.phone_number, a.branch_name, a.desired_designation], search))
  const selected = id ? rows.find((a) => String(a.id) === id) ?? null : null

  const columns: Column<Applicant>[] = [
    {
      key: "name", label: "Applicant", sort: (a) => a.full_name.toLowerCase(),
      render: (a) => (
        <span className="min-w-0">
          <span className="block truncate font-semibold">{a.full_name}</span>
          <span className="block truncate text-xs text-ab-faint">{text(a.phone_number ?? a.email)}</span>
        </span>
      ),
    },
    { key: "position", label: "Applying as", sort: (a) => a.desired_designation ?? "", render: (a) => t(a.desired_designation ?? "Not set"), hideOnPhone: true },
    { key: "branch", label: "Branch", sort: (a) => a.branch_name ?? "", render: (a) => text(a.branch_name) },
    { key: "score", label: "Screening score", align: "right", sort: (a) => a.screening_score ?? -1, render: (a) => (a.screening_score != null ? `${a.screening_score}/100` : "—"), hideOnPhone: true },
    { key: "license", label: "License", sort: (a) => (a.has_license ? 1 : 0), render: (a) => (a.has_license ? t("Licensed") : t("None")), hideOnPhone: true },
    { key: "applied", label: "Applied", sort: (a) => a.created_at, render: (a) => date(a.created_at), hideOnPhone: true },
    { key: "status", label: "Stage", sort: (a) => a.status, render: (a) => <Badge value={a.status} /> },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Agent recruitment, from application to onboarding"
        subtitle="Record applicants, move them through screening and interviews, and onboard approved ones: onboarding creates their agent record with a branch and designation."
        actions={<Button variant="primary" onClick={() => setEditing("new")}><Plus className="h-4 w-4" /> {t("New applicant")}</Button>}
      />
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {summary && (
        <>
          <Tiles items={[
            { label: "Open applications", value: summary.open, onClick: () => setStatus(status === "OPEN" ? "" : "OPEN"), active: status === "OPEN" },
            ...summary.stages.map((s) => ({ label: statusLabel(s), value: summary.by_status[s] ?? 0, onClick: () => setStatus(status === s ? "" : s), active: status === s })),
            { label: "Acceptance rate", value: summary.acceptance_rate != null ? `${summary.acceptance_rate}%` : "—", detail: "Approved ÷ decided" },
          ]} />
          <Pipeline summary={summary} />
          <div className="flex flex-wrap gap-2 sm:flex-nowrap">
            <div className="w-full sm:w-auto sm:flex-1"><SearchBox value={search} onChange={setSearch} placeholder="Search name, contact, branch or position" /></div>
            <Select label="Stage" value={status} onChange={setStatus} options={[{ value: "", label: "All stages" }, { value: "OPEN", label: "Open applications" },
              ...[...summary.stages, ...summary.closed].map((s) => ({ value: s, label: statusLabel(s) }))]} />
          </div>
          <DataTable exportTitle="Agent applicants" rows={shown} columns={columns} rowKey={(a) => String(a.id)} onOpen={(a) => open(String(a.id))}
            empty={rows.length ? "No applicants match these filters." : "No applicants yet. Add one with New applicant."} initialSort={{ key: "applied", dir: "desc" }} />
        </>
      )}
      {selected && summary && (
        <ApplicantDrawer applicant={selected} summary={summary} onClose={close} onEdit={() => setEditing(selected)}
          onChanged={() => void reload()} onDeleted={() => { close(); void reload() }} />
      )}
      {editing && summary && (
        <ApplicantForm applicant={editing === "new" ? null : editing} summary={summary} onClose={() => setEditing(null)}
          onSaved={(a) => { setEditing(null); void reload().then(() => open(String(a.id))) }} />
      )}
    </div>
  )
}

/** Applicants at each stage, left to right. */
function Pipeline({ summary }: { summary: Summary }) {
  const most = Math.max(1, ...summary.stages.map((s) => summary.by_status[s] ?? 0))
  return (
    <Section title={t("Recruitment pipeline")}>
      <ol className="grid gap-2 sm:grid-cols-5">
        {summary.stages.map((stage, index) => (
          <li key={stage} className="min-w-0 rounded-xl border border-ab-border bg-ab-card-2 p-3">
            <p className="flex items-center gap-1 text-xs font-semibold text-ab-muted">{index + 1}. {statusLabel(stage)}</p>
            <p className="mt-1 text-2xl font-extrabold tabular-nums">{summary.by_status[stage] ?? 0}</p>
            <span className="mt-2 block h-1.5 overflow-hidden rounded-full bg-ab-card"><span className="block h-full rounded-full bg-ab-accent" style={{ width: `${((summary.by_status[stage] ?? 0) / most) * 100}%` }} /></span>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-xs text-ab-faint">{t("Closed: {r} rejected, {w} withdrawn.", { r: summary.by_status.REJECTED ?? 0, w: summary.by_status.WITHDRAWN ?? 0 })}</p>
    </Section>
  )
}

function ApplicantDrawer({ applicant, summary, onClose, onEdit, onChanged, onDeleted }: {
  applicant: Applicant; summary: Summary; onClose: () => void; onEdit: () => void; onChanged: () => void; onDeleted: () => void
}) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const [closing, setClosing] = useState<"REJECTED" | "WITHDRAWN" | null>(null)
  const [onboarding, setOnboarding] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)
  const next = NEXT[applicant.status]
  const isOpen = Boolean(next) || applicant.status === "APPROVED"
  const move = async (status: string, note?: string) => {
    setBusy(true)
    try {
      await api(`/recruitment/applicants/${applicant.id}/stage`, { method: "POST", body: JSON.stringify({ status, note: note || null }) })
      toast(t("{name} moved to {stage}.", { name: applicant.full_name, stage: statusLabel(status) }))
      setClosing(null)
      onChanged()
    } catch (moveError) {
      toast(t((moveError as Error).message), "error")
    } finally {
      setBusy(false)
    }
  }
  const remove = async () => {
    setBusy(true)
    try {
      await api(`/recruitment/applicants/${applicant.id}`, { method: "DELETE" })
      toast(t("Deleted {name}.", { name: applicant.full_name }))
      onDeleted()
    } catch (deleteError) {
      toast(t((deleteError as Error).message), "error")
      setBusy(false)
      setConfirmDelete(false)
    }
  }
  return (
    <Drawer
      title={applicant.full_name}
      subtitle={<span className="flex flex-wrap items-center gap-2"><Badge value={applicant.status} /> {t(applicant.desired_designation ?? "Position not set")}{applicant.branch_name ? ` · ${applicant.branch_name}` : ""}</span>}
      onClose={onClose}
      footer={(
        <>
          {applicant.status !== "ONBOARDED" && <Button variant="danger" onClick={() => setConfirmDelete(true)}><Trash2 className="h-4 w-4" /> {t("Delete")}</Button>}
          <Button onClick={onEdit}><Pencil className="h-4 w-4" /> {t("Edit")}</Button>
          {next && <Button variant="primary" disabled={busy} onClick={() => void move(next)}><ArrowRight className="h-4 w-4" /> {t("Move to {stage}", { stage: statusLabel(next) })}</Button>}
          {applicant.status === "APPROVED" && <Button variant="primary" onClick={() => setOnboarding(true)}><UserPlus className="h-4 w-4" /> {t("Onboard as agent")}</Button>}
        </>
      )}
    >
      <Stepper status={applicant.status} stages={summary.stages} />
      {isOpen && (
        <div className="rounded-xl bg-ab-card-2 p-3 text-sm text-ab-muted">
          <p>{t(STEP_HELP[applicant.status] ?? "")}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <button type="button" onClick={() => setClosing("REJECTED")} className="text-xs font-semibold text-ab-danger hover:underline">{t("Reject applicant")}</button>
            <button type="button" onClick={() => setClosing("WITHDRAWN")} className="text-xs font-semibold text-ab-muted hover:underline">{t("Mark as withdrawn")}</button>
          </div>
        </div>
      )}
      {applicant.agent_id && (
        <p className="flex items-center gap-2 rounded-xl border border-ab-success/40 bg-ab-success/10 p-3 text-sm">
          <BadgeCheck className="h-4 w-4 text-ab-success" aria-hidden />
          {t("Onboarded as agent")} <Link to={`/manage/agents?id=${applicant.agent_id}`} className="font-semibold hover:underline">{applicant.agent_id}</Link>
        </p>
      )}
      <div className="flex flex-wrap gap-2 text-sm">
        {applicant.phone_number && <a href={`tel:${applicant.phone_number.replace(/[^\d+]/g, "")}`} className="inline-flex items-center gap-1.5 rounded-full border border-ab-border bg-ab-card px-3 py-1 hover:border-ab-accent"><Phone className="h-3.5 w-3.5 text-ab-accent" />{applicant.phone_number}</a>}
        {applicant.email && <a href={`mailto:${applicant.email}`} className="inline-flex items-center gap-1.5 rounded-full border border-ab-border bg-ab-card px-3 py-1 hover:border-ab-accent"><Mail className="h-3.5 w-3.5 text-ab-accent" />{applicant.email}</a>}
      </div>
      <Section title="Application">
        <Facts items={[
          ["Applying as", applicant.desired_designation ? t(applicant.desired_designation) : null],
          ["Branch", applicant.branch_name],
          ["Source", applicant.source ? statusLabel(applicant.source) : null],
          ["Experience", applicant.experience_years != null ? t("{n} year(s)", { n: applicant.experience_years }) : null],
          ["Real estate license", applicant.has_license ? `${t("Yes")}${applicant.license_number ? ` · ${applicant.license_number}` : ""}` : t("No")],
          ["Screening score", applicant.screening_score != null ? `${applicant.screening_score}/100` : null],
          ["Interview date", applicant.interview_on ? date(applicant.interview_on) : null],
          ["Address", applicant.address],
          ["Notes", applicant.notes],
          ["Recorded by", applicant.created_by],
        ]} />
      </Section>
      <Section title="History">
        <ol className="space-y-2">
          {[...applicant.history].reverse().map((h, index) => (
            <li key={`${h.at}-${index}`} className="rounded-xl border border-ab-border p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2"><Badge value={h.status} /><span className="text-xs text-ab-faint">{dateTime(h.at)} · {h.by}</span></div>
              {h.note && <p className="mt-1 break-words text-ab-muted">{h.note}</p>}
            </li>
          ))}
        </ol>
      </Section>
      {closing && <CloseDialog kind={closing} busy={busy} onCancel={() => setClosing(null)} onConfirm={(note) => void move(closing, note)} />}
      {onboarding && <OnboardDialog applicant={applicant} summary={summary} onClose={() => setOnboarding(false)} onDone={() => { setOnboarding(false); onChanged() }} />}
      {confirmDelete && (
        <Confirm typeToConfirm="Delete" title="Delete applicant?" confirmLabel="Delete" busy={busy} onConfirm={remove} onCancel={() => setConfirmDelete(false)}
          message={t("Delete {name}'s application? This can't be undone.", { name: applicant.full_name })} />
      )}
    </Drawer>
  )
}

function Stepper({ status, stages }: { status: string; stages: string[] }) {
  const reached = stages.indexOf(status)
  const closed = reached < 0
  return (
    <ol className="flex flex-wrap items-center gap-1.5 text-xs" aria-label={t("Recruitment stage")}>
      {stages.map((stage, index) => (
        <li key={stage} className="flex items-center gap-1.5">
          <span className={`rounded-full px-2.5 py-1 font-semibold ${!closed && index <= reached ? "bg-ab-accent text-ab-ink" : "bg-ab-card-2 text-ab-muted"}`}>{statusLabel(stage)}</span>
          {index < stages.length - 1 && <span className="text-ab-faint" aria-hidden>›</span>}
        </li>
      ))}
      {closed && <li><Badge value={status} /></li>}
    </ol>
  )
}

const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"

function Dialog({ title, onClose, children, footer, onSubmit }: { title: string; onClose: () => void; children: React.ReactNode; footer: React.ReactNode; onSubmit: (e: FormEvent) => void }) {
  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" aria-label={t("Cancel")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={onSubmit} noValidate className="ab-pop relative flex max-h-[94dvh] w-full max-w-2xl flex-col rounded-t-2xl border border-ab-border bg-ab-card shadow-2xl sm:rounded-2xl">
        <header className="flex items-center justify-between border-b border-ab-border px-5 py-4">
          <h2 className="text-lg font-bold">{title}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close")} className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><X className="h-4 w-4" /></button>
        </header>
        {children}
        <footer className="flex justify-end gap-2 border-t border-ab-border px-5 py-3">{footer}</footer>
      </form>
    </div>
  )
}

function CloseDialog({ kind, busy, onCancel, onConfirm }: { kind: "REJECTED" | "WITHDRAWN"; busy: boolean; onCancel: () => void; onConfirm: (note: string) => void }) {
  const [note, setNote] = useState("")
  const [error, setError] = useState("")
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (kind === "REJECTED" && !note.trim()) return setError(t("Give a reason for rejecting the applicant."))
    onConfirm(note.trim())
  }
  return (
    <Dialog title={kind === "REJECTED" ? t("Reject applicant") : t("Mark as withdrawn")} onClose={onCancel} onSubmit={submit}
      footer={<><Button onClick={onCancel} disabled={busy}>{t("Cancel")}</Button><Button type="submit" variant={kind === "REJECTED" ? "danger" : "primary"} disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Confirm")}</Button></>}>
      <div className="p-5">
        <label className="text-sm font-medium">{kind === "REJECTED" ? t("Reason *") : t("Note")}
          <textarea className={`${field} min-h-24`} value={note} onChange={(e) => setNote(e.target.value)} placeholder={kind === "REJECTED" ? t("e.g. Didn't meet the license requirement") : ""} />
        </label>
        {error && <p role="alert" className="mt-2 text-sm text-ab-danger">{error}</p>}
      </div>
    </Dialog>
  )
}

function OnboardDialog({ applicant, summary, onClose, onDone }: { applicant: Applicant; summary: Summary; onClose: () => void; onDone: () => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const branches = useBranchOptions()
  const [form, setForm] = useState({ designation: applicant.desired_designation ?? "Trainee Agent", branch_id: applicant.branch_id ? String(applicant.branch_id) : "", work_area: "", hired_on: new Date().toISOString().slice(0, 10) })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError("")
    try {
      const saved = await api<{ agent: { agent_id: string } }>(`/recruitment/applicants/${applicant.id}/onboard`, {
        method: "POST", body: JSON.stringify({ ...form, branch_id: form.branch_id ? Number(form.branch_id) : null, work_area: form.work_area || null }),
      })
      toast(t("{name} is now agent {id}.", { name: applicant.full_name, id: saved.agent.agent_id }))
      onDone()
    } catch (saveError) {
      setError(t((saveError as Error).message))
      setBusy(false)
    }
  }
  return (
    <Dialog title={t("Onboard {name}", { name: applicant.full_name })} onClose={onClose} onSubmit={submit}
      footer={<><Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button><Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Create agent record")}</Button></>}>
      <div className="grid gap-3 overflow-y-auto p-5 sm:grid-cols-2">
        <p className="text-sm text-ab-muted sm:col-span-2">{t("This creates the agent record (with the next agent ID) and sends it to the central agent list.")}</p>
        <label className="text-sm font-medium">{t("Designation")}
          <select className={field} value={form.designation} onChange={(e) => setForm((f) => ({ ...f, designation: e.target.value }))}>
            {summary.designations.map((d) => <option key={d} value={d}>{t(d)}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">{t("Branch")}
          <select className={field} value={form.branch_id} onChange={(e) => setForm((f) => ({ ...f, branch_id: e.target.value }))}>
            <option value="">{t("No branch")}</option>
            {branches.filter((b) => b.is_active).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">{t("Work area")}<input className={field} value={form.work_area} onChange={(e) => setForm((f) => ({ ...f, work_area: e.target.value }))} placeholder={t("e.g. Imus, Bacoor")} /></label>
        <label className="text-sm font-medium">{t("Start date")}<input type="date" className={field} value={form.hired_on} onChange={(e) => setForm((f) => ({ ...f, hired_on: e.target.value }))} /></label>
        {error && <p role="alert" className="text-sm text-ab-danger sm:col-span-2">{error}</p>}
      </div>
    </Dialog>
  )
}

function ApplicantForm({ applicant, summary, onClose, onSaved }: { applicant: Applicant | null; summary: Summary; onClose: () => void; onSaved: (a: Applicant) => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const branches = useBranchOptions()
  const [form, setForm] = useState({
    full_name: applicant?.full_name ?? "", email: applicant?.email ?? "", phone_number: applicant?.phone_number ?? "", address: applicant?.address ?? "",
    branch_id: applicant?.branch_id ? String(applicant.branch_id) : "", desired_designation: applicant?.desired_designation ?? "",
    source: applicant?.source ?? "", experience_years: applicant?.experience_years != null ? String(applicant.experience_years) : "",
    has_license: applicant?.has_license ?? false, license_number: applicant?.license_number ?? "",
    screening_score: applicant?.screening_score != null ? String(applicant.screening_score) : "", interview_on: applicant?.interview_on ?? "", notes: applicant?.notes ?? "",
  })
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value }))
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!form.full_name.trim()) return setError(t("Enter the applicant's name."))
    setBusy(true)
    setError("")
    try {
      const body = JSON.stringify({
        ...form,
        branch_id: form.branch_id ? Number(form.branch_id) : null,
        desired_designation: form.desired_designation || null,
        source: form.source || null,
        experience_years: form.experience_years === "" ? null : Number(form.experience_years),
        screening_score: form.screening_score === "" ? null : Number(form.screening_score),
        interview_on: form.interview_on || null,
      })
      const saved = applicant
        ? await api<Applicant>(`/recruitment/applicants/${applicant.id}`, { method: "PUT", body })
        : await api<Applicant>("/recruitment/applicants", { method: "POST", body })
      toast(t(applicant ? "Saved {name}." : "Added {name}.", { name: saved.full_name }))
      onSaved(saved)
    } catch (saveError) {
      setError(t((saveError as Error).message))
      setBusy(false)
    }
  }
  return (
    <Dialog title={applicant ? t("Edit {name}", { name: applicant.full_name }) : t("New applicant")} onClose={onClose} onSubmit={submit}
      footer={<><Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button><Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {applicant ? t("Save") : t("Add applicant")}</Button></>}>
      <div className="grid gap-3 overflow-y-auto p-5 sm:grid-cols-2">
        <label className="text-sm font-medium sm:col-span-2">{t("Full name *")}<input className={field} value={form.full_name} onChange={set("full_name")} /></label>
        <label className="text-sm font-medium">{t("Phone")}<input className={field} value={form.phone_number} onChange={set("phone_number")} /></label>
        <label className="text-sm font-medium">{t("Email")}<input type="email" className={field} value={form.email} onChange={set("email")} /></label>
        <label className="text-sm font-medium sm:col-span-2">{t("Address")}<input className={field} value={form.address} onChange={set("address")} /></label>
        <label className="text-sm font-medium">{t("Applying as")}
          <select className={field} value={form.desired_designation} onChange={set("desired_designation")}>
            <option value="">{t("Not set")}</option>
            {summary.designations.map((d) => <option key={d} value={d}>{t(d)}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">{t("Branch")}
          <select className={field} value={form.branch_id} onChange={set("branch_id")}>
            <option value="">{t("Not set")}</option>
            {branches.filter((b) => b.is_active).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">{t("Source")}
          <select className={field} value={form.source} onChange={set("source")}>
            <option value="">{t("Not set")}</option>
            {summary.sources.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">{t("Years of experience")}<input type="number" min={0} step="0.5" className={field} value={form.experience_years} onChange={set("experience_years")} /></label>
        <label className="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" checked={form.has_license} onChange={(e) => setForm((f) => ({ ...f, has_license: e.target.checked }))} className="h-4 w-4 accent-[var(--color-ab-accent)]" />
          {t("Has a real estate license")}
        </label>
        <label className="text-sm font-medium">{t("License number")}<input className={field} value={form.license_number} onChange={set("license_number")} disabled={!form.has_license} /></label>
        <label className="text-sm font-medium">{t("Screening score (0–100)")}<input type="number" min={0} max={100} className={field} value={form.screening_score} onChange={set("screening_score")} /></label>
        <label className="text-sm font-medium">{t("Interview date")}<input type="date" className={field} value={form.interview_on} onChange={set("interview_on")} /></label>
        <label className="text-sm font-medium sm:col-span-2">{t("Notes")}<textarea className={`${field} min-h-20`} value={form.notes} onChange={set("notes")} /></label>
        {error && <p role="alert" className="rounded-lg border border-ab-danger/40 bg-ab-danger/10 px-3 py-2 text-sm text-ab-danger sm:col-span-2">{error}</p>}
      </div>
    </Dialog>
  )
}
