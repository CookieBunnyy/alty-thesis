// Dashboard: sales and recruitment this year (/reports/dashboard), the two
// activities Abellar's management monitors. Recruitment shows for management only.
import { useCallback, useState } from "react"
import { Link } from "@/components/Link"
import { StackedBarChart, TableToggle } from "./charts"
import { peso, pesoShort } from "./format"
import { LoadState, Section } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"
import { t } from "./i18n"

type Group = { name: string; sales?: number; revenue?: number; applications?: number; recruited?: number }
type Dashboard = {
  year: number
  sales: { totals: { sales: number; revenue: number; commission: number }; top_sellers: Group[]; by_team: Group[]; trend: { period: string; sales: number; revenue: number }[] }
  recruitment?: { totals: { applications: number; recruited: number }; top_recruiters: Group[]; by_team: Group[]; trend: { period: string; applications: number; recruited: number }[] }
}

function Ranked({ title, rows, value, empty }: { title: string; rows: Group[]; value: (g: Group) => string; empty: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t(title)}</p>
      {rows.length === 0 ? <p className="mt-1 text-sm italic text-ab-faint">{t(empty)}</p> : (
        <ol className="mt-1 space-y-1">
          {rows.map((g, i) => (
            <li key={`${g.name}-${i}`} className="flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0 truncate"><span className="text-ab-faint">{i + 1}. </span>{g.name}</span>
              <span className="shrink-0 font-semibold tabular-nums">{value(g)}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

export function SalesRecruitmentPanel() {
  const { api } = useStaffAuth()
  const load = useCallback(() => api<Dashboard>("/reports/dashboard"), [api])
  const { data, error, loading, reload } = useApiData(load, "reports-dashboard")
  const [salesTable, setSalesTable] = useState(false)
  const [recTable, setRecTable] = useState(false)
  if (!data) return <LoadState loading={loading} error={error} onRetry={reload} />
  const { sales, recruitment } = data
  return (
    <div className="space-y-5" data-tour="dash-sales-recruitment">
      <div className={`grid gap-5 ${recruitment ? "lg:grid-cols-2" : ""}`}>
        <Section title={t("Sales in {year}", { year: data.year })} action={<Link to="/manage/reports" className="text-xs font-semibold text-ab-accent hover:underline">{t("Open sales report")}</Link>}>
          <div className="grid grid-cols-3 gap-2">
            {([["Recorded sales", String(sales.totals.sales)], ["Sales value", pesoShort(sales.totals.revenue)], ["Recorded commission", pesoShort(sales.totals.commission)]] as const).map(([label, v]) => (
              <div key={label} className="min-w-0 rounded-xl border border-ab-border p-3"><p className="text-[11px] text-ab-faint">{t(label)}</p><p className="mt-0.5 truncate text-lg font-extrabold tabular-nums">{v}</p></div>
            ))}
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Ranked title="Top sellers" rows={sales.top_sellers} value={(g) => pesoShort(g.revenue ?? 0)} empty="No completed sales yet this year." />
            <Ranked title="By team / cluster" rows={sales.by_team} value={(g) => pesoShort(g.revenue ?? 0)} empty="No completed sales yet this year." />
          </div>
          <div className="mt-4">
            <div className="mb-1 flex items-center justify-between"><p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("Sales value per month")}</p><TableToggle shown={salesTable} onToggle={() => setSalesTable((v) => !v)} /></div>
            <StackedBarChart caption={t("Sales value per month")} months={sales.trend.map((p) => p.period)} showTable={salesTable} height={170}
              series={[{ key: "revenue", label: t("Sales value"), color: "var(--color-ab-chart-1)", values: sales.trend.map((p) => p.revenue) }]}
              format={(v) => peso(v)} axisFormat={(v) => pesoShort(v)} />
          </div>
        </Section>
        {recruitment && (
          <Section title={t("Recruitment in {year}", { year: data.year })} action={<Link to="/manage/reports?view=recruitment" className="text-xs font-semibold text-ab-accent hover:underline">{t("Open recruitment report")}</Link>}>
            <div className="grid grid-cols-2 gap-2">
              {([["Applications", recruitment.totals.applications], ["Sellers recruited", recruitment.totals.recruited]] as const).map(([label, v]) => (
                <div key={label} className="rounded-xl border border-ab-border p-3"><p className="text-[11px] text-ab-faint">{t(label)}</p><p className="mt-0.5 text-lg font-extrabold tabular-nums">{v}</p></div>
              ))}
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Ranked title="Top recruiters" rows={recruitment.top_recruiters} value={(g) => t("{n} recruited", { n: g.recruited ?? 0 })} empty="No recruitment recorded yet this year." />
              <Ranked title="By team / cluster" rows={recruitment.by_team} value={(g) => t("{n} recruited", { n: g.recruited ?? 0 })} empty="No recruitment recorded yet this year." />
            </div>
            <div className="mt-4">
              <div className="mb-1 flex items-center justify-between"><p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("Sellers recruited per month")}</p><TableToggle shown={recTable} onToggle={() => setRecTable((v) => !v)} /></div>
              <StackedBarChart caption={t("Sellers recruited per month")} months={recruitment.trend.map((p) => p.period)} showTable={recTable} height={170} integer
                series={[{ key: "recruited", label: t("Sellers recruited"), color: "var(--color-ab-chart-2)", values: recruitment.trend.map((p) => p.recruited) }]}
                format={(v) => String(Math.round(v))} />
            </div>
          </Section>
        )}
      </div>
    </div>
  )
}
