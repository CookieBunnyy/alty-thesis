// Management reports on sales and recruitment (/reports/*), the two
// activities Abellar's management monitors. The Filing Manager sees sales only.
import { useCallback, useMemo, useState } from "react"
import { Printer } from "lucide-react"
import { useLocation } from "@/lib/router"
import { StackedBarChart, TableToggle } from "./charts"
import { date, isManagement, peso, pesoShort, statusLabel, text } from "./format"
import { Button, DataTable, LoadState, PageHeader, Section, Select, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"
import { t } from "./i18n"
import { useBranchOptions, useSellerOptions } from "./branches"

type SalesGroup = { name: string; sales: number; revenue: number; commission: number; agent_id?: string; team?: string | null; developer?: string | null }
type Sales = {
  totals: { sales: number; revenue: number; commission: number; average_sale: number | null }
  by_period: ({ period: string } & SalesGroup)[]; top_sellers: SalesGroup[]; by_project: SalesGroup[]; by_team: SalesGroup[]
  sales: { transaction_id: string; date: string; buyer: string | null; property: string | null; project: string | null; developer: string | null; seller: string | null; team: string | null; amount: number; commission: number }[]
}
type RecGroup = { name: string; applications: number; recruited: number }
type Recruitment = {
  totals: { applications: number; recruited: number }; by_status: Record<string, number>
  by_period: { period: string; applications: number; recruited: number }[]; top_recruiters: RecGroup[]; by_team: RecGroup[]
  applications: { id: number; full_name: string; status: string; applied_on: string; onboarded_on: string | null; recruiter: string; team: string | null }[]
}

const field = "min-h-10 rounded-xl border border-ab-border bg-ab-input px-3 text-sm"
const thisYear = () => `${new Date().getFullYear()}-01-01`
const todayIso = () => new Date().toISOString().slice(0, 10)

export function ReportsPage() {
  const { user } = useStaffAuth()
  const { search } = useLocation()
  const management = isManagement(user?.role)
  const [view, setView] = useState<"sales" | "recruitment">(management && search.get("view") === "recruitment" ? "recruitment" : "sales")
  const [start, setStart] = useState(thisYear)
  const [end, setEnd] = useState(todayIso)
  const [period, setPeriod] = useState("month")
  const [team, setTeam] = useState("")
  const teams = useBranchOptions()
  return (
    <div className="mx-auto max-w-7xl space-y-5 print:max-w-none">
      <PageHeader
        title="Sales and recruitment reports"
        subtitle="Recorded sales and recruitment for any period, by seller, recruiter, team / cluster and project. Use Export PDF on a table, or Print for the whole report."
        actions={<Button onClick={() => window.print()}><Printer className="h-4 w-4" /> {t("Print")}</Button>}
      />
      {management && (
        <div role="tablist" aria-label={t("Report")} className="flex w-fit rounded-xl border border-ab-border bg-ab-card p-1 print:hidden">
          {([["sales", "Sales"], ["recruitment", "Recruitment"]] as const).map(([key, label]) => (
            <button key={key} type="button" role="tab" aria-selected={view === key} onClick={() => setView(key)}
              className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${view === key ? "bg-ab-accent text-ab-ink" : "text-ab-muted hover:text-ab-text"}`}>{t(label)}</button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-end gap-2 print:hidden" aria-label={t("Report filters")}>
        <label className="text-xs font-semibold text-ab-muted">{t("From")}<input type="date" className={`${field} mt-1 block`} value={start} onChange={(e) => setStart(e.target.value)} /></label>
        <label className="text-xs font-semibold text-ab-muted">{t("To")}<input type="date" className={`${field} mt-1 block`} value={end} onChange={(e) => setEnd(e.target.value)} /></label>
        <Select label="Group by" value={period} onChange={setPeriod} options={[{ value: "day", label: "Day" }, { value: "month", label: "Month" }, { value: "quarter", label: "Quarter" }, { value: "year", label: "Year" }]} />
        <Select label="Team / Cluster" value={team} onChange={setTeam} options={[{ value: "", label: "All teams" }, ...teams.map((b) => ({ value: String(b.id), label: b.name })), { value: "0", label: "No team" }]} />
      </div>
      <p className="hidden text-sm print:block">{t("Period: {from} to {to}", { from: date(start), to: date(end) })}</p>
      {view === "sales" ? <SalesReport start={start} end={end} period={period} team={team} /> : <RecruitmentReport start={start} end={end} period={period} team={team} />}
    </div>
  )
}

function SalesReport({ start, end, period, team }: { start: string; end: string; period: string; team: string }) {
  const { api } = useStaffAuth()
  const sellers = useSellerOptions()
  const [seller, setSeller] = useState("")
  const [project, setProject] = useState("")
  const [table, setTable] = useState(false)
  const query = useMemo(() => {
    const q = new URLSearchParams({ start, end, period })
    if (team) q.set("team_id", team)
    if (seller) q.set("agent_id", seller)
    if (project.trim()) q.set("project", project.trim())
    return q.toString()
  }, [start, end, period, team, seller, project])
  const load = useCallback(() => api<Sales>(`/reports/sales?${query}`), [api, query])
  const { data, error, loading, reload } = useApiData(load, `report-sales:${query}`)
  const groupColumns = (label: string, extra?: Column<SalesGroup>): Column<SalesGroup>[] => [
    { key: "name", label, sort: (g) => g.name, render: (g) => <span className="font-semibold">{g.name}</span> },
    ...(extra ? [extra] : []),
    { key: "sales", label: "Sales", align: "right", sort: (g) => g.sales, render: (g) => g.sales },
    { key: "revenue", label: "Sales value", align: "right", sort: (g) => g.revenue, render: (g) => peso(g.revenue) },
    { key: "commission", label: "Recorded commission", align: "right", sort: (g) => g.commission, render: (g) => (g.commission ? peso(g.commission) : "—"), hideOnPhone: true },
  ]
  const saleColumns: Column<Sales["sales"][number]>[] = [
    { key: "date", label: "Date", sort: (s) => s.date, render: (s) => date(s.date) },
    { key: "property", label: "Property / project", sort: (s) => s.project ?? s.property ?? "", render: (s) => <span className="min-w-0"><span className="block truncate">{text(s.property)}</span>{s.project && <span className="block truncate text-xs text-ab-faint">{s.project}</span>}</span> },
    { key: "seller", label: "Seller", sort: (s) => s.seller ?? "", render: (s) => text(s.seller) },
    { key: "team", label: "Team", sort: (s) => s.team ?? "", render: (s) => text(s.team), hideOnPhone: true },
    { key: "buyer", label: "Buyer", sort: (s) => s.buyer ?? "", render: (s) => text(s.buyer), hideOnPhone: true },
    { key: "amount", label: "Sale value", align: "right", sort: (s) => s.amount, render: (s) => peso(s.amount) },
  ]
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-2 print:hidden">
        <Select label="Seller" value={seller} onChange={setSeller} options={[{ value: "", label: "All sellers" }, ...sellers.map((s) => ({ value: s.agent_id, label: s.full_name }))]} />
        <label className="text-xs font-semibold text-ab-muted">{t("Property / project")}<input className={`${field} mt-1 block`} value={project} onChange={(e) => setProject(e.target.value)} placeholder={t("Any")} /></label>
      </div>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <>
          <Tiles items={[
            { label: "Recorded sales", value: data.totals.sales },
            { label: "Sales value", value: pesoShort(data.totals.revenue) },
            { label: "Average sale", value: data.totals.average_sale ? pesoShort(data.totals.average_sale) : "—" },
            { label: "Recorded commission", value: pesoShort(data.totals.commission), detail: "From commission records" },
          ]} />
          <Section title={t("Sales value over time")} action={<TableToggle shown={table} onToggle={() => setTable((v) => !v)} />}>
            {data.by_period.length ? (
              <StackedBarChart caption={t("Sales value per period")} months={data.by_period.map((p) => p.period)} showTable={table}
                series={[{ key: "revenue", label: t("Sales value"), color: "var(--color-ab-chart-1)", values: data.by_period.map((p) => p.revenue) }]}
                format={(v) => peso(v)} axisFormat={(v) => pesoShort(v)} />
            ) : <p className="text-sm italic text-ab-faint">{t("No completed sales in this period.")}</p>}
          </Section>
          <div className="grid gap-5 lg:grid-cols-2">
            <div><h2 className="mb-2 font-bold">{t("Top sellers")}</h2>
              <DataTable exportTitle="Top sellers" rows={data.top_sellers} columns={groupColumns("Seller", { key: "team", label: "Team", sort: (g) => g.team ?? "", render: (g) => text(g.team), hideOnPhone: true })} rowKey={(g) => g.agent_id ?? g.name} empty="No sales." initialSort={{ key: "revenue", dir: "desc" }} /></div>
            <div><h2 className="mb-2 font-bold">{t("By team / cluster")}</h2>
              <DataTable exportTitle="Sales by team" rows={data.by_team} columns={groupColumns("Team / Cluster")} rowKey={(g) => g.name} empty="No sales." initialSort={{ key: "revenue", dir: "desc" }} /></div>
          </div>
          <div><h2 className="mb-2 font-bold">{t("By property / project")}</h2>
            <DataTable exportTitle="Sales by project" rows={data.by_project} columns={groupColumns("Property / project", { key: "developer", label: "Developer", sort: (g) => g.developer ?? "", render: (g) => text(g.developer), hideOnPhone: true })} rowKey={(g) => g.name} empty="No sales." initialSort={{ key: "revenue", dir: "desc" }} /></div>
          <div><h2 className="mb-2 font-bold">{t("Every sale in the period")}</h2>
            <DataTable exportTitle="Sales" rows={data.sales} columns={saleColumns} rowKey={(s) => s.transaction_id} empty="No completed sales in this period." initialSort={{ key: "date", dir: "desc" }} /></div>
        </>
      )}
    </div>
  )
}

function RecruitmentReport({ start, end, period, team }: { start: string; end: string; period: string; team: string }) {
  const { api } = useStaffAuth()
  const sellers = useSellerOptions()
  const [recruiter, setRecruiter] = useState("")
  const [table, setTable] = useState(false)
  const query = useMemo(() => {
    const q = new URLSearchParams({ start, end, period })
    if (team) q.set("team_id", team)
    if (recruiter) q.set("recruiter", recruiter)
    return q.toString()
  }, [start, end, period, team, recruiter])
  const load = useCallback(() => api<Recruitment>(`/reports/recruitment?${query}`), [api, query])
  const { data, error, loading, reload } = useApiData(load, `report-recruitment:${query}`)
  const columns = (label: string): Column<RecGroup>[] => [
    { key: "name", label, sort: (g) => g.name, render: (g) => <span className="font-semibold">{g.name}</span> },
    { key: "applications", label: "Applications", align: "right", sort: (g) => g.applications, render: (g) => g.applications },
    { key: "recruited", label: "Sellers recruited", align: "right", sort: (g) => g.recruited, render: (g) => g.recruited },
  ]
  const appColumns: Column<Recruitment["applications"][number]>[] = [
    { key: "name", label: "Applicant", sort: (a) => a.full_name, render: (a) => <span className="font-semibold">{a.full_name}</span> },
    { key: "recruiter", label: "Recruiter", sort: (a) => a.recruiter, render: (a) => a.recruiter },
    { key: "team", label: "Team", sort: (a) => a.team ?? "", render: (a) => text(a.team), hideOnPhone: true },
    { key: "applied", label: "Applied", sort: (a) => a.applied_on, render: (a) => date(a.applied_on) },
    { key: "onboarded", label: "Recruited", sort: (a) => a.onboarded_on ?? "", render: (a) => (a.onboarded_on ? date(a.onboarded_on) : "—") },
    { key: "status", label: "Stage", sort: (a) => a.status, render: (a) => statusLabel(a.status) },
  ]
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-2 print:hidden">
        <Select label="Recruiter" value={recruiter} onChange={setRecruiter} options={[{ value: "", label: "All recruiters" }, ...sellers.map((s) => ({ value: s.agent_id, label: s.full_name }))]} />
      </div>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <>
          <Tiles items={[
            { label: "Applications", value: data.totals.applications },
            { label: "Sellers recruited", value: data.totals.recruited, detail: "Onboarded in the period" },
            ...Object.entries(data.by_status).map(([status, n]) => ({ label: statusLabel(status), value: n, detail: "Applications at this stage" })),
          ]} />
          <Section title={t("Recruitment over time")} action={<TableToggle shown={table} onToggle={() => setTable((v) => !v)} />}>
            {data.by_period.length ? (
              <StackedBarChart caption={t("Sellers recruited per period")} months={data.by_period.map((p) => p.period)} showTable={table} integer
                series={[{ key: "recruited", label: t("Sellers recruited"), color: "var(--color-ab-chart-2)", values: data.by_period.map((p) => p.recruited) }]}
                format={(v) => String(Math.round(v))} />
            ) : <p className="text-sm italic text-ab-faint">{t("No recruitment in this period.")}</p>}
          </Section>
          <div className="grid gap-5 lg:grid-cols-2">
            <div><h2 className="mb-2 font-bold">{t("Top recruiters")}</h2>
              <DataTable exportTitle="Top recruiters" rows={data.top_recruiters} columns={columns("Recruiter")} rowKey={(g) => g.name} empty="No recruitment." initialSort={{ key: "recruited", dir: "desc" }} /></div>
            <div><h2 className="mb-2 font-bold">{t("By team / cluster")}</h2>
              <DataTable exportTitle="Recruitment by team" rows={data.by_team} columns={columns("Team / Cluster")} rowKey={(g) => g.name} empty="No recruitment." initialSort={{ key: "recruited", dir: "desc" }} /></div>
          </div>
          <div><h2 className="mb-2 font-bold">{t("Applications and recruits in the period")}</h2>
            <DataTable exportTitle="Recruitment" rows={data.applications} columns={appColumns} rowKey={(a) => String(a.id)} empty="No recruitment in this period." initialSort={{ key: "applied", dir: "desc" }} /></div>
        </>
      )}
    </div>
  )
}
