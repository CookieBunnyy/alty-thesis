import { useCallback, useMemo, useState, type FormEvent } from "react"
import { Building, LoaderCircle, Pencil, Plus, Trash2, TrendingDown, TrendingUp, X } from "lucide-react"
import { Link } from "@/components/Link"
import { BarList, StackedBarChart, TableToggle } from "./charts"
import { contains, dateTime, peso, pesoShort, text } from "./format"
import { Badge, Button, Confirm, DataTable, Drawer, Facts, LoadState, PageHeader, SearchBox, Section, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData, useOpenRecord } from "./useApiData"
import { locale, t } from "./i18n"
import type { BranchOption } from "./branches"

type Branch = BranchOption & {
  address: string | null; contact_number: string | null; email: string | null; notes: string | null
  created_at: string; updated_at: string; agents: number; listings: number
}
type Month = { month: string; revenue: number; sales: number; transactions: number; commission: number }
type Figures = {
  branch_id: number; name: string; code: string | null; is_active: boolean; address: string | null
  agents: number; active_agents: number; available_listings: number
  months: Month[]; last_month: Month | null; previous_month: Month | null; change_pct: number | null
  trend_per_month: number | null; trend_pct: number | null
  forecast_next: { month: string; value: number; lower: number; upper: number } | null; forecast_status: string
  totals: { transactions: number; sales: number; revenue: number; commission: number; conversion: number | null }
  revenue_share: number | null
}
type Comparison = { branches: Figures[]; best_last_month: string | null; trend_months: number }
type BranchDetail = Branch & { agent_rows: { agent_id: string; full_name: string; status: string; designation: string | null; work_area: string | null }[] }

const monthShort = (key: string) => new Date(`${key}-01T00:00:00`).toLocaleDateString(locale(), { month: "short", year: "numeric" })
const NO_BRANCH = 0

/** Branches (offices) and how each one is doing: management roles. */
export function BranchesPage() {
  const { api } = useStaffAuth()
  const { id, open, close } = useOpenRecord()
  const [search, setSearch] = useState("")
  const [editing, setEditing] = useState<Branch | "new" | null>(null)
  const load = useCallback(() => Promise.all([api<Branch[]>("/branches"), api<Comparison>("/branches/comparison")]), [api])
  const { data, error, loading, reload } = useApiData(load, "branches")
  const [branches, comparison] = data ?? [null, null]
  const figures = useMemo(() => new Map((comparison?.branches ?? []).map((f) => [f.branch_id, f])), [comparison])
  const rows = useMemo(() => comparison?.branches ?? [], [comparison])
  const shown = rows.filter((r) => contains([r.name, r.code, r.address], search))
  const selected = id ? branches?.find((b) => String(b.id) === id) ?? null : null
  const lastMonthTotal = rows.reduce((s, r) => s + (r.last_month?.revenue ?? 0), 0)
  const lastMonthKey = rows.find((r) => r.last_month)?.last_month?.month

  const columns: Column<Figures>[] = [
    {
      key: "name", label: "Branch", sort: (r) => r.name.toLowerCase(),
      render: (r) => (
        <span className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-ab-accent-soft text-ab-accent"><Building className="h-4 w-4" /></span>
          <span className="min-w-0">
            <span className="block truncate font-semibold">{r.branch_id === NO_BRANCH ? t("No branch") : r.name}</span>
            <span className="block truncate text-xs text-ab-faint">{r.branch_id === NO_BRANCH ? t("Agents and listings not given a branch yet") : text(r.address)}</span>
          </span>
        </span>
      ),
    },
    { key: "agents", label: "Active agents", align: "right", sort: (r) => r.active_agents, render: (r) => r.active_agents },
    { key: "listings", label: "Available listings", align: "right", sort: (r) => r.available_listings, render: (r) => r.available_listings, hideOnPhone: true },
    { key: "last", label: "Revenue last month", align: "right", sort: (r) => r.last_month?.revenue ?? 0, render: (r) => (r.last_month?.revenue ? pesoShort(r.last_month.revenue) : "—") },
    { key: "change", label: "vs month before", align: "right", sort: (r) => r.change_pct ?? -999, render: (r) => <Change pct={r.change_pct} /> },
    { key: "trend", label: "Trend", align: "right", sort: (r) => r.trend_pct ?? -999, render: (r) => <Trend pct={r.trend_pct} />, hideOnPhone: true },
    { key: "forecast", label: "Next month (forecast)", align: "right", sort: (r) => r.forecast_next?.value ?? -1, render: (r) => (r.forecast_next ? pesoShort(r.forecast_next.value) : <span className="text-xs text-ab-faint">{t("Not enough history")}</span>), hideOnPhone: true },
    { key: "commission", label: "Commission last month", align: "right", sort: (r) => r.last_month?.commission ?? 0, render: (r) => (r.last_month?.commission ? pesoShort(r.last_month.commission) : "—"), hideOnPhone: true },
    { key: "share", label: "Share of revenue", align: "right", sort: (r) => r.revenue_share ?? 0, render: (r) => (r.revenue_share != null ? `${r.revenue_share}%` : "—") },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Branches and how each one is doing"
        subtitle="Your offices side by side: agents, listings, sales, commission and where each branch is heading. A sale counts for the branch of its agent (or of the listing when the agent has none)."
        actions={<Button variant="primary" onClick={() => setEditing("new")}><Plus className="h-4 w-4" /> {t("New branch")}</Button>}
      />
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {branches && comparison && (
        <>
          <Tiles items={[
            { label: "Branches", value: branches.length, detail: t("{n} active", { n: branches.filter((b) => b.is_active).length }) },
            { label: "Best last month", value: comparison.best_last_month ?? "—", detail: lastMonthKey ? monthShort(lastMonthKey) : undefined },
            { label: "Revenue last month", value: lastMonthTotal ? pesoShort(lastMonthTotal) : "—", detail: "All branches" },
            { label: "Agents without a branch", value: figures.get(NO_BRANCH)?.agents ?? 0, detail: (figures.get(NO_BRANCH)?.agents ?? 0) ? "Assign them on the Agents page" : "Everyone is assigned" },
          ]} />
          {branches.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-ab-border bg-ab-card p-6 text-center">
              <p className="font-bold">{t("No branches yet")}</p>
              <p className="mt-1 text-sm text-ab-muted">{t("Add your offices first, then give each agent and listing a branch to compare them.")}</p>
            </div>
          ) : (
            <Section title={t("Revenue last month by branch")}>
              <BarList format={(v) => peso(v)} empty="No completed sales last month."
                rows={rows.filter((r) => (r.last_month?.revenue ?? 0) > 0).sort((a, b) => (b.last_month?.revenue ?? 0) - (a.last_month?.revenue ?? 0))
                  .map((r) => ({ name: r.branch_id === NO_BRANCH ? t("No branch") : r.name, value: r.last_month?.revenue ?? 0,
                    note: t("{s} sale(s) · {c} commission", { s: r.last_month?.sales ?? 0, c: pesoShort(r.last_month?.commission ?? 0) }) }))} />
            </Section>
          )}
          <div className="w-full sm:max-w-sm"><SearchBox value={search} onChange={setSearch} placeholder="Search branch name, code or address" /></div>
          <DataTable exportTitle="Branch comparison" rows={shown} columns={columns} rowKey={(r) => String(r.branch_id)}
            onOpen={(r) => r.branch_id !== NO_BRANCH && open(String(r.branch_id))} empty="No branches match." initialSort={{ key: "last", dir: "desc" }} />
          <p className="text-xs text-ab-faint">
            {t("Trend: the average change per month over the last {n} complete months, as a share of the branch's average month. Forecast: the same trend method as Business Outlook, per branch.", { n: comparison.trend_months })}
          </p>
        </>
      )}
      {selected && (
        <BranchDrawer branch={selected} figures={figures.get(selected.id) ?? null} onClose={close} onEdit={() => setEditing(selected)}
          onDeleted={() => { close(); void reload() }} />
      )}
      {editing && (
        <BranchForm branch={editing === "new" ? null : editing} onClose={() => setEditing(null)}
          onSaved={(b) => { setEditing(null); void reload().then(() => open(String(b.id))) }} />
      )}
    </div>
  )
}

function Change({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-ab-faint">—</span>
  return <span className={`tabular-nums font-semibold ${pct < 0 ? "text-ab-danger" : pct > 0 ? "text-ab-success" : ""}`}>{pct > 0 ? "+" : ""}{pct}%</span>
}

function Trend({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-xs text-ab-faint">{t("Not enough history")}</span>
  const Icon = pct < 0 ? TrendingDown : TrendingUp
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap tabular-nums ${pct < 0 ? "text-ab-danger" : "text-ab-success"}`}>
      <Icon className="h-3.5 w-3.5" aria-hidden /> {pct > 0 ? "+" : ""}{pct}% {t("a month")}
    </span>
  )
}

function BranchDrawer({ branch, figures, onClose, onEdit, onDeleted }: { branch: Branch; figures: Figures | null; onClose: () => void; onEdit: () => void; onDeleted: () => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [table, setTable] = useState(false)
  const loadDetail = useCallback(() => api<BranchDetail>(`/branches/${branch.id}`), [api, branch.id])
  const detail = useApiData(loadDetail)
  const remove = async () => {
    setBusy(true)
    try {
      await api(`/branches/${branch.id}`, { method: "DELETE" })
      toast(t("Deleted {name}.", { name: branch.name }))
      onDeleted()
    } catch (deleteError) {
      toast(t((deleteError as Error).message), "error")
      setBusy(false)
      setConfirm(false)
    }
  }
  const months = figures?.months ?? []
  return (
    <Drawer
      title={branch.name}
      subtitle={<span className="flex items-center gap-2"><Badge value={branch.is_active ? "ACTIVE" : "INACTIVE"} /> {branch.code ?? ""}</span>}
      onClose={onClose}
      footer={(
        <>
          <Button variant="danger" onClick={() => setConfirm(true)}><Trash2 className="h-4 w-4" /> {t("Delete")}</Button>
          <Button variant="primary" onClick={onEdit}><Pencil className="h-4 w-4" /> {t("Edit")}</Button>
        </>
      )}
    >
      {figures && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {([
              ["Active agents", figures.active_agents],
              ["Available listings", figures.available_listings],
              ["Revenue last month", figures.last_month?.revenue ? peso(figures.last_month.revenue) : "—"],
              ["Commission last month", figures.last_month?.commission ? peso(figures.last_month.commission) : "—"],
              ["Deals on record", figures.totals.transactions],
              ["Completed sales", figures.totals.sales],
              ["Conversion", figures.totals.conversion != null ? `${figures.totals.conversion}%` : "—"],
              ["Next month (forecast)", figures.forecast_next ? peso(figures.forecast_next.value) : "—"],
            ] as const).map(([label, value]) => (
              <div key={label} className="min-w-0 rounded-xl border border-ab-border bg-ab-card p-3"><p className="text-[11px] text-ab-faint">{t(label)}</p><p className="mt-0.5 break-words font-bold tabular-nums">{value}</p></div>
            ))}
          </div>
          <Section title={t("Revenue in the last {n} months", { n: months.length })} action={months.length > 0 && <TableToggle shown={table} onToggle={() => setTable((v) => !v)} />}>
            {months.length ? (
              <StackedBarChart caption={t("Revenue per month for {name}", { name: branch.name })} months={months.map((m) => m.month)} showTable={table}
                series={[{ key: "revenue", label: t("Revenue"), color: "var(--color-ab-chart-1)", values: months.map((m) => m.revenue) }]}
                format={(v) => peso(v)} axisFormat={(v) => pesoShort(v)} />
            ) : <p className="text-sm italic text-ab-faint">{t("No complete months recorded yet.")}</p>}
            {figures.forecast_next && (
              <p className="mt-2 text-xs text-ab-faint">
                {t("Forecast for {month}: {v} (likely {low} – {high}).", { month: monthShort(figures.forecast_next.month), v: peso(figures.forecast_next.value), low: peso(figures.forecast_next.lower), high: peso(figures.forecast_next.upper) })}
              </p>
            )}
          </Section>
        </>
      )}
      <Section title="Details">
        <Facts items={[
          ["Code", branch.code],
          ["Address", branch.address],
          ["Contact number", branch.contact_number],
          ["Email", branch.email],
          ["Notes", branch.notes],
          ["Last updated", dateTime(branch.updated_at)],
        ]} />
      </Section>
      <Section title="Agents in this branch">
        <LoadState loading={detail.loading} error={detail.error} onRetry={detail.reload} />
        {detail.data && (detail.data.agent_rows.length === 0 ? (
          <p className="text-sm italic text-ab-faint">{t("No agents yet. Open an agent and set their branch.")}</p>
        ) : (
          <ul className="space-y-2">
            {detail.data.agent_rows.map((a) => (
              <li key={a.agent_id} className="flex items-center justify-between gap-2 rounded-xl border border-ab-border p-3 text-sm">
                <span className="min-w-0">
                  <Link to={`/manage/agents?id=${a.agent_id}`} className="block truncate font-semibold hover:underline">{a.full_name}</Link>
                  <span className="text-xs text-ab-faint">{t(a.designation ?? "No designation")}{a.work_area ? ` · ${a.work_area}` : ""}</span>
                </span>
                <Badge value={a.status} />
              </li>
            ))}
          </ul>
        ))}
      </Section>
      {confirm && (
        <Confirm typeToConfirm="Delete" title="Delete branch?" confirmLabel="Delete" busy={busy} onConfirm={remove} onCancel={() => setConfirm(false)}
          message={t("Delete {name}? A branch with agents, listings or staff can't be deleted — move them first or mark it inactive.", { name: branch.name })} />
      )}
    </Drawer>
  )
}

const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"

function BranchForm({ branch, onClose, onSaved }: { branch: Branch | null; onClose: () => void; onSaved: (b: Branch) => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const [form, setForm] = useState({
    name: branch?.name ?? "", code: branch?.code ?? "", address: branch?.address ?? "", contact_number: branch?.contact_number ?? "",
    email: branch?.email ?? "", notes: branch?.notes ?? "", is_active: branch?.is_active ?? true,
  })
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value }))
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!form.name.trim()) return setError(t("Enter the branch name."))
    setBusy(true)
    setError("")
    try {
      const body = JSON.stringify(form)
      const saved = branch
        ? await api<Branch>(`/branches/${branch.id}`, { method: "PUT", body })
        : await api<Branch>("/branches", { method: "POST", body })
      toast(t(branch ? "Saved {name}." : "Added {name}.", { name: saved.name }))
      onSaved(saved)
    } catch (saveError) {
      setError(t((saveError as Error).message))
      setBusy(false)
    }
  }
  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={branch ? t("Edit branch") : t("New branch")}>
      <button type="button" aria-label={t("Cancel")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={submit} noValidate className="ab-pop relative flex max-h-[94dvh] w-full max-w-2xl flex-col rounded-t-2xl border border-ab-border bg-ab-card shadow-2xl sm:rounded-2xl">
        <header className="flex items-center justify-between border-b border-ab-border px-5 py-4">
          <h2 className="text-lg font-bold">{branch ? t("Edit {name}", { name: branch.name }) : t("New branch")}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close")} className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><X className="h-4 w-4" /></button>
        </header>
        <div className="grid gap-3 overflow-y-auto p-5 sm:grid-cols-2">
          <label className="text-sm font-medium">{t("Name *")}<input className={field} value={form.name} onChange={set("name")} placeholder={t("e.g. Cavite Branch")} /></label>
          <label className="text-sm font-medium">{t("Code")}<input className={field} value={form.code} onChange={set("code")} placeholder="CAV" /></label>
          <label className="text-sm font-medium sm:col-span-2">{t("Address")}<input className={field} value={form.address} onChange={set("address")} /></label>
          <label className="text-sm font-medium">{t("Contact number")}<input className={field} value={form.contact_number} onChange={set("contact_number")} /></label>
          <label className="text-sm font-medium">{t("Email")}<input className={field} type="email" value={form.email} onChange={set("email")} /></label>
          <label className="text-sm font-medium sm:col-span-2">{t("Notes")}<textarea className={`${field} min-h-20`} value={form.notes} onChange={set("notes")} /></label>
          <label className="flex items-center gap-2 text-sm font-medium sm:col-span-2">
            <input type="checkbox" checked={form.is_active} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))} className="h-4 w-4 accent-[var(--color-ab-accent)]" />
            {t("Active branch (counted in workforce planning)")}
          </label>
        </div>
        {error && <p role="alert" className="mx-5 mb-2 rounded-lg border border-ab-danger/40 bg-ab-danger/10 px-3 py-2 text-sm text-ab-danger">{error}</p>}
        <footer className="flex justify-end gap-2 border-t border-ab-border px-5 py-3">
          <Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button>
          <Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {branch ? t("Save") : t("Add branch")}</Button>
        </footer>
      </form>
    </div>
  )
}
