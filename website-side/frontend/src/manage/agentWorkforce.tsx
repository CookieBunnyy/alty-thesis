// Agent drawer sections for management: branch & designation, periodic
// assessments (scores partly suggested from recorded figures), and the
// agent's estimated commission per month.
import { useCallback, useState, type FormEvent } from "react"
import { ClipboardCheck, LoaderCircle, Pencil, Trash2, X } from "lucide-react"
import { StackedBarChart, TableToggle } from "./charts"
import { date, peso, pesoShort, text } from "./format"
import { Button, Confirm, Facts, LoadState, Section } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData } from "./useApiData"
import { t } from "./i18n"
import { useBranchOptions } from "./branches"

export type AgentAssignmentFields = {
  agent_id: string; full_name: string
  branch_id: number | null; branch_name: string | null; designation: string | null; work_area: string | null; hired_on: string | null
}
type Options = { designations: string[]; criteria: string[] }
type Kpis = { deals: number; completed_sales: number; sales_value: number; commission: number; cancellations: number; conversion: number | null; client_rating: number | null; reviews: number }
type Assessment = {
  id: number; period_start: string; period_end: string; scores: Record<string, number>; overall: number; rating: string
  recommendation: string | null; kpis: Kpis; remarks: string | null; assessed_by: string | null; created_at: string
}
type Draft = { period_start: string; period_end: string; kpis: Kpis; team_size: number; suggested: Record<string, number | null>; basis: Record<string, string> }

const CRITERIA: Record<string, { label: string; help: string }> = {
  sales_performance: { label: "Sales performance", help: "Sales value against the other agents in the same period." },
  client_satisfaction: { label: "Client satisfaction", help: "Client reviews and feedback." },
  documentation_compliance: { label: "Documentation & compliance", help: "Complete, correct and on-time reservation and sale documents." },
  product_knowledge: { label: "Product knowledge", help: "Knows the listings, payment terms and the process." },
  teamwork: { label: "Teamwork & conduct", help: "Works well with the team and follows company policy." },
}
const SCALE: Record<number, string> = { 1: "Poor", 2: "Needs improvement", 3: "Satisfactory", 4: "Very satisfactory", 5: "Outstanding" }
const RATING_TONE: Record<string, string> = {
  Outstanding: "bg-ab-success/15 text-ab-success", "Very satisfactory": "bg-ab-accent-soft text-ab-accent",
  Satisfactory: "bg-ab-hover text-ab-text", "Needs improvement": "bg-ab-warning/15 text-ab-warning", Poor: "bg-ab-danger/10 text-ab-danger",
}

const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"

function useOptions() {
  const { api } = useStaffAuth()
  const load = useCallback(() => api<Options>("/agents/designations/options"), [api])
  return useApiData(load, "agent-options").data
}

/** Branch, designation, work area and start date, editable by management. */
export function AgentAssignment({ agent, canManage, onChanged }: { agent: AgentAssignmentFields; canManage: boolean; onChanged: () => Promise<void> }) {
  const [editing, setEditing] = useState(false)
  return (
    <Section title="Assignment" action={canManage && <Button onClick={() => setEditing(true)}><Pencil className="h-4 w-4" /> {t("Edit")}</Button>}>
      <Facts items={[
        ["Branch", agent.branch_name],
        ["Designation", agent.designation ? t(agent.designation) : null],
        ["Work area", agent.work_area],
        ["Start date", agent.hired_on ? date(agent.hired_on) : null],
      ]} />
      {editing && <AssignmentDialog agent={agent} onClose={() => setEditing(false)} onSaved={async () => { setEditing(false); await onChanged() }} />}
    </Section>
  )
}

function AssignmentDialog({ agent, onClose, onSaved }: { agent: AgentAssignmentFields; onClose: () => void; onSaved: () => Promise<void> }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const branches = useBranchOptions()
  const options = useOptions()
  const [form, setForm] = useState({ branch_id: agent.branch_id ? String(agent.branch_id) : "", designation: agent.designation ?? "", work_area: agent.work_area ?? "", hired_on: agent.hired_on ?? "" })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError("")
    try {
      await api(`/agents/${encodeURIComponent(agent.agent_id)}/assignment`, {
        method: "PUT",
        body: JSON.stringify({ branch_id: form.branch_id ? Number(form.branch_id) : null, designation: form.designation || null, work_area: form.work_area || null, hired_on: form.hired_on || null }),
      })
      toast(t("Saved {name}.", { name: agent.full_name }))
      await onSaved()
    } catch (saveError) {
      setError(t((saveError as Error).message))
      setBusy(false)
    }
  }
  return (
    <Modal title={t("Assignment of {name}", { name: agent.full_name })} onClose={onClose} onSubmit={submit}
      footer={<><Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button><Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Save")}</Button></>}>
      <div className="grid gap-3 p-5 sm:grid-cols-2">
        <label className="text-sm font-medium">{t("Branch")}
          <select className={field} value={form.branch_id} onChange={(e) => setForm((f) => ({ ...f, branch_id: e.target.value }))}>
            <option value="">{t("No branch")}</option>
            {branches.map((b) => <option key={b.id} value={b.id}>{b.name}{b.is_active ? "" : ` (${t("inactive")})`}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">{t("Designation")}
          <select className={field} value={form.designation} onChange={(e) => setForm((f) => ({ ...f, designation: e.target.value }))}>
            <option value="">{t("Not set")}</option>
            {(options?.designations ?? []).map((d) => <option key={d} value={d}>{t(d)}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">{t("Work area")}<input className={field} value={form.work_area} onChange={(e) => setForm((f) => ({ ...f, work_area: e.target.value }))} placeholder={t("e.g. Imus, Bacoor")} /></label>
        <label className="text-sm font-medium">{t("Start date")}<input type="date" className={field} value={form.hired_on} onChange={(e) => setForm((f) => ({ ...f, hired_on: e.target.value }))} /></label>
        {error && <p role="alert" className="text-sm text-ab-danger sm:col-span-2">{error}</p>}
      </div>
    </Modal>
  )
}

/** Past assessments and a form for a new one. */
export function AgentAssessments({ agent }: { agent: AgentAssignmentFields }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const load = useCallback(() => api<Assessment[]>(`/agents/${encodeURIComponent(agent.agent_id)}/assessments`), [api, agent.agent_id])
  const { data, error, loading, reload } = useApiData(load)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<Assessment | null>(null)
  const [busy, setBusy] = useState(false)
  const remove = async () => {
    if (!deleting) return
    setBusy(true)
    try {
      await api(`/agents/${encodeURIComponent(agent.agent_id)}/assessments/${deleting.id}`, { method: "DELETE" })
      toast(t("Assessment deleted."))
      setDeleting(null)
      await reload()
    } catch (deleteError) {
      toast(t((deleteError as Error).message), "error")
    } finally {
      setBusy(false)
    }
  }
  return (
    <Section title="Assessments" action={<Button onClick={() => setCreating(true)}><ClipboardCheck className="h-4 w-4" /> {t("New assessment")}</Button>}>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (data.length === 0 ? (
        <p className="text-sm italic text-ab-faint">{t("No assessments yet. Assess agents every quarter to track their growth.")}</p>
      ) : (
        <ul className="space-y-2">
          {data.map((a) => (
            <li key={a.id} className="rounded-xl border border-ab-border p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold">{date(a.period_start)} – {date(a.period_end)}</span>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${RATING_TONE[a.rating] ?? "bg-ab-hover"}`}>{a.overall.toFixed(2)} · {t(a.rating)}</span>
              </div>
              <ul className="mt-2 grid gap-1 text-xs text-ab-muted sm:grid-cols-2">
                {Object.entries(a.scores).map(([key, score]) => (
                  <li key={key} className="flex justify-between gap-2"><span>{t(CRITERIA[key]?.label ?? key)}</span><span className="font-semibold tabular-nums text-ab-text">{score}/5</span></li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-ab-muted">
                {t("Recorded: {s} sale(s), {v}, conversion {c}", { s: a.kpis.completed_sales, v: pesoShort(a.kpis.sales_value), c: a.kpis.conversion != null ? `${a.kpis.conversion}%` : "—" })}
              </p>
              {a.recommendation && <p className="mt-1 text-xs"><span className="font-semibold">{t("Recommendation:")}</span> {t(a.recommendation)}</p>}
              {a.remarks && <p className="mt-1 break-words text-xs text-ab-muted">{a.remarks}</p>}
              <div className="mt-1 flex items-center justify-between gap-2 text-[11px] text-ab-faint">
                <span>{t("By {name}", { name: text(a.assessed_by) })} · {date(a.created_at)}</span>
                <button type="button" onClick={() => setDeleting(a)} className="inline-flex items-center gap-1 font-semibold text-ab-danger hover:underline"><Trash2 className="h-3 w-3" /> {t("Delete")}</button>
              </div>
            </li>
          ))}
        </ul>
      ))}
      {creating && <AssessmentForm agent={agent} onClose={() => setCreating(false)} onSaved={async () => { setCreating(false); await reload() }} />}
      {deleting && (
        <Confirm title="Delete assessment?" confirmLabel="Delete" busy={busy} onConfirm={remove} onCancel={() => setDeleting(null)}
          message={t("Delete the assessment for {from} – {to}?", { from: date(deleting.period_start), to: date(deleting.period_end) })} />
      )}
    </Section>
  )
}

function lastQuarter(): [string, string] {
  const now = new Date()
  const quarterStart = new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1)
  const end = new Date(quarterStart.getTime() - 86_400_000)
  const start = new Date(end.getFullYear(), Math.floor(end.getMonth() / 3) * 3, 1)
  const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
  return [iso(start), iso(end)]
}

function AssessmentForm({ agent, onClose, onSaved }: { agent: AgentAssignmentFields; onClose: () => void; onSaved: () => Promise<void> }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const [period, setPeriod] = useState(() => {
    const [start, end] = lastQuarter()
    return { start, end }
  })
  const loadDraft = useCallback(() => api<Draft>(`/agents/${encodeURIComponent(agent.agent_id)}/assessment-draft?start=${period.start}&end=${period.end}`), [api, agent.agent_id, period.start, period.end])
  const draft = useApiData(loadDraft)
  const [scores, setScores] = useState<Record<string, number>>({})
  const [remarks, setRemarks] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  // Scores start at the suggestion (or 3) until the assessor changes them.
  const value = (key: string) => scores[key] ?? draft.data?.suggested[key] ?? 3
  const overall = Object.keys(CRITERIA).reduce((s, key) => s + value(key), 0) / Object.keys(CRITERIA).length
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError("")
    try {
      await api(`/agents/${encodeURIComponent(agent.agent_id)}/assessments`, {
        method: "POST",
        body: JSON.stringify({ period_start: period.start, period_end: period.end, remarks: remarks || null,
          scores: Object.fromEntries(Object.keys(CRITERIA).map((key) => [key, value(key)])) }),
      })
      toast(t("Assessment saved for {name}.", { name: agent.full_name }))
      await onSaved()
    } catch (saveError) {
      setError(t((saveError as Error).message))
      setBusy(false)
    }
  }
  const k = draft.data?.kpis
  return (
    <Modal title={t("Assess {name}", { name: agent.full_name })} onClose={onClose} onSubmit={submit}
      footer={<><Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button><Button type="submit" variant="primary" disabled={busy || !draft.data}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Save assessment")}</Button></>}>
      <div className="space-y-4 p-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm font-medium">{t("Period from")}<input type="date" className={field} value={period.start} onChange={(e) => setPeriod((p) => ({ ...p, start: e.target.value }))} /></label>
          <label className="text-sm font-medium">{t("to")}<input type="date" className={field} value={period.end} onChange={(e) => setPeriod((p) => ({ ...p, end: e.target.value }))} /></label>
        </div>
        <LoadState loading={draft.loading && !draft.data} error={draft.error} onRetry={draft.reload} />
        {k && (
          <div className="rounded-xl bg-ab-card-2 p-3 text-sm">
            <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("Recorded in this period")}</p>
            <p className="mt-1 text-ab-muted">
              {t("{d} deal(s), {s} completed sale(s) worth {v}, {c} cancelled, conversion {r}. Estimated commission {m}.", {
                d: k.deals, s: k.completed_sales, v: peso(k.sales_value), c: k.cancellations, r: k.conversion != null ? `${k.conversion}%` : "—", m: peso(k.commission),
              })}
              {" "}{k.client_rating != null ? t("Client rating {r} from {n} review(s).", { r: k.client_rating.toFixed(1), n: k.reviews }) : t("No client reviews yet.")}
            </p>
          </div>
        )}
        <ul className="space-y-3">
          {Object.entries(CRITERIA).map(([key, criterion]) => {
            const suggested = draft.data?.suggested[key]
            return (
              <li key={key}>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-sm font-semibold">{t(criterion.label)}</span>
                  <span className="text-xs text-ab-faint">{t(SCALE[value(key)])}</span>
                </div>
                <p className="text-xs text-ab-muted">{t(draft.data?.basis[key] ?? criterion.help)}{suggested != null ? ` ${t("Suggested: {n}.", { n: suggested })}` : ""}</p>
                <div className="mt-1.5 flex gap-1.5" role="radiogroup" aria-label={t(criterion.label)}>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button key={n} type="button" role="radio" aria-checked={value(key) === n} onClick={() => setScores((s) => ({ ...s, [key]: n }))}
                      className={`h-9 w-9 rounded-lg border text-sm font-bold ${value(key) === n ? "border-ab-accent bg-ab-accent text-ab-ink" : "border-ab-border bg-ab-card hover:border-ab-accent"}`}>{n}</button>
                  ))}
                </div>
              </li>
            )
          })}
        </ul>
        <p className="rounded-xl border border-ab-border p-3 text-sm">
          {t("Overall")}: <span className="font-extrabold tabular-nums">{overall.toFixed(2)}</span> · {t(SCALE[Math.min(5, Math.max(1, Math.floor(overall + 0.5)))] ?? "")}
          <span className="block text-xs text-ab-faint">{t("The average of the five scores. 4.5+ Outstanding, 3.5+ Very satisfactory, 2.5+ Satisfactory, 1.5+ Needs improvement.")}</span>
        </p>
        <label className="block text-sm font-medium">{t("Remarks")}<textarea className={`${field} min-h-20`} value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder={t("Strengths, areas to improve, agreed goals")} /></label>
        {error && <p role="alert" className="text-sm text-ab-danger">{error}</p>}
      </div>
    </Modal>
  )
}

/** Estimated commission per month for the last 12 months. */
export function AgentCommission({ agentId }: { agentId: string }) {
  const { api } = useStaffAuth()
  const load = useCallback(() => api<{ rate: number; total: number; months: { month: string; sales: number; revenue: number; commission: number }[] }>(`/agents/${encodeURIComponent(agentId)}/commission?months=12`), [api, agentId])
  const { data, error, loading, reload } = useApiData(load)
  const [table, setTable] = useState(false)
  return (
    <Section title="Commission (last 12 months)" action={data && <TableToggle shown={table} onToggle={() => setTable((v) => !v)} />}>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <>
          <p className="text-sm">{t("Total")}: <span className="font-extrabold tabular-nums">{peso(data.total)}</span>
            <span className="ml-2 text-xs text-ab-faint">{t("at a {r}% commission rate", { r: (data.rate * 100).toFixed(1) })}</span></p>
          <StackedBarChart caption={t("Commission per month")} months={data.months.map((m) => m.month)} showTable={table} height={180}
            series={[{ key: "commission", label: t("Commission"), color: "var(--color-ab-chart-1)", values: data.months.map((m) => m.commission) }]}
            format={(v) => peso(v)} axisFormat={(v) => pesoShort(v)} />
          <p className="mt-2 text-xs text-ab-faint">{t("Completed sales × the agent's commission rate (recorded total commission ÷ total sales; 3% when not recorded).")}</p>
        </>
      )}
    </Section>
  )
}

function Modal({ title, onClose, onSubmit, children, footer }: { title: string; onClose: () => void; onSubmit: (e: FormEvent) => void; children: React.ReactNode; footer: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" aria-label={t("Cancel")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={onSubmit} noValidate className="ab-pop relative flex max-h-[94dvh] w-full max-w-2xl flex-col rounded-t-2xl border border-ab-border bg-ab-card shadow-2xl sm:rounded-2xl">
        <header className="flex items-center justify-between border-b border-ab-border px-5 py-4">
          <h2 className="text-lg font-bold">{title}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close")} className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><X className="h-4 w-4" /></button>
        </header>
        <div className="overflow-y-auto">{children}</div>
        <footer className="flex justify-end gap-2 border-t border-ab-border px-5 py-3">{footer}</footer>
      </form>
    </div>
  )
}
