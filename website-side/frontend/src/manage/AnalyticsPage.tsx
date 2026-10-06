import { useCallback, useMemo, useState } from "react"
import { Link } from "@/components/Link"
import { categoryLabel } from "@/lib/categories"
import { BarList, Legend, StackedBarChart, TableToggle } from "./charts"
import { peso, pesoShort } from "./format"
import { InsightPanel, type Insight } from "./Insights"
import { Badge, DataTable, LoadState, PageHeader, Section, Select, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"

type Month = { month: string; transactions: number; reservations: number; sales: number; revenue: number; average_sale: number | null }
type Group = { name: string; transactions: number; reservations: number; sales: number; cancelled: number; revenue: number; listings?: number; available?: number }
type PropertyRow = Group & { listing_id: number; title: string | null; category: string | null; status: string; price_total: number | null }
type Data = {
  overview: {
    properties: { total: number; by_status: Record<string, number> }
    transactions: { total: number; active_reservations: number; completed_sales: number; revenue: number; average_sale_value: number | null }
    absorption_rate: number | null
    agents: { agent_id: string; full_name: string; status: string; transactions: number; completed_sales: number; sales_value: number; recorded_total_commission: number | null }[]
    price_by_category: { category: string; listings: number; average_price: number | null; min_price: number | null; max_price: number | null }[]
  }
  monthly: Month[]
  breakdown: { by_category: Group[]; by_area: Group[]; area_basis: string; properties: PropertyRow[] }
  insights: Insight[]
}

const count = (v: number) => String(Math.round(v))

export function AnalyticsPage() {
  const { api } = useStaffAuth()
  const [months, setMonths] = useState("12")
  const [segmentMeasure, setSegmentMeasure] = useState<"transactions" | "revenue">("transactions")
  const [activityTable, setActivityTable] = useState(false)
  const [revenueTable, setRevenueTable] = useState(false)
  const load = useCallback(() => api<Data>(`/intelligence/analytics?months=${months}`), [api, months])
  const { data, error, loading, reload } = useApiData(load)

  const period = useMemo(() => {
    const rows = data?.monthly ?? []
    const revenue = rows.reduce((s, r) => s + r.revenue, 0)
    const sales = rows.reduce((s, r) => s + r.sales, 0)
    return { revenue, sales, reservations: rows.reduce((s, r) => s + r.reservations, 0), average: sales ? revenue / sales : null }
  }, [data])

  const propertyColumns: Column<PropertyRow>[] = [
    { key: "title", label: "Property", sort: (p) => p.title ?? "", render: (p) => <Link to={`/manage/properties?id=${p.listing_id}`} onClick={(e) => e.stopPropagation()} className="font-semibold hover:underline">{p.title ?? `#${p.listing_id}`}</Link> },
    { key: "category", label: "Type", sort: (p) => categoryLabel(p.category), render: (p) => categoryLabel(p.category), hideOnPhone: true },
    { key: "status", label: "Status", sort: (p) => p.status, render: (p) => <Badge value={p.status} /> },
    { key: "reservations", label: "Reservations", align: "right", sort: (p) => p.reservations, render: (p) => p.reservations },
    { key: "sales", label: "Sales", align: "right", sort: (p) => p.sales, render: (p) => p.sales },
    { key: "cancelled", label: "Cancelled", align: "right", sort: (p) => p.cancelled, render: (p) => p.cancelled, hideOnPhone: true },
    { key: "revenue", label: "Revenue", align: "right", sort: (p) => p.revenue, render: (p) => (p.revenue ? peso(p.revenue) : "—") },
  ]
  type AgentRow = Data["overview"]["agents"][number]
  const agentColumns: Column<AgentRow>[] = [
    { key: "name", label: "Agent", sort: (a) => a.full_name, render: (a) => <Link to={`/manage/agents?id=${a.agent_id}`} onClick={(e) => e.stopPropagation()} className="font-semibold hover:underline">{a.full_name}</Link> },
    { key: "transactions", label: "Transactions", align: "right", sort: (a) => a.transactions, render: (a) => a.transactions },
    { key: "sales", label: "Completed sales", align: "right", sort: (a) => a.completed_sales, render: (a) => a.completed_sales },
    { key: "value", label: "Sales value", align: "right", sort: (a) => a.sales_value, render: (a) => peso(a.sales_value) },
    { key: "commission", label: "Recorded commission", align: "right", sort: (a) => a.recorded_total_commission ?? -1, render: (a) => (a.recorded_total_commission != null ? peso(a.recorded_total_commission) : "—"), hideOnPhone: true },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Analytics"
        subtitle="Historical and current performance computed from recorded properties, transactions and agents. ALTY interprets the results below the charts."
        actions={<Select label="Period" value={months} onChange={setMonths} options={[{ value: "6", label: "Last 6 months" }, { value: "12", label: "Last 12 months" }, { value: "24", label: "Last 24 months" }]} />}
      />
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <>
          <Tiles items={[
            { label: "Sales revenue", value: pesoShort(period.revenue), detail: `Last ${months} months` },
            { label: "Completed sales", value: period.sales, detail: `Last ${months} months` },
            { label: "Reservations", value: period.reservations, detail: `Last ${months} months` },
            { label: "Average sale", value: period.average ? pesoShort(period.average) : "—", detail: "Revenue ÷ completed sales" },
            { label: "Absorption rate", value: data.overview.absorption_rate != null ? `${Math.round(data.overview.absorption_rate * 100)}%` : "—", detail: "Share of listings sold" },
          ]} />

          <div className="grid gap-5 lg:grid-cols-2">
            <Section title="Activity per month" action={<TableToggle shown={activityTable} onToggle={() => setActivityTable(!activityTable)} />}>
              <div className="mb-3"><Legend items={[{ label: "Reservations", color: "var(--color-ab-chart-2)" }, { label: "Completed sales", color: "var(--color-ab-chart-1)" }]} /></div>
              <StackedBarChart caption="Reservations and completed sales per month" months={data.monthly.map((m) => m.month)} integer showTable={activityTable} format={count}
                series={[
                  { key: "reservations", label: "Reservations", color: "var(--color-ab-chart-2)", values: data.monthly.map((m) => m.reservations) },
                  { key: "sales", label: "Completed sales", color: "var(--color-ab-chart-1)", values: data.monthly.map((m) => m.sales) },
                ]} />
            </Section>
            <Section title="Sales revenue per month" action={<TableToggle shown={revenueTable} onToggle={() => setRevenueTable(!revenueTable)} />}>
              <StackedBarChart caption="Revenue from completed sales per month" months={data.monthly.map((m) => m.month)} showTable={revenueTable} format={peso} axisFormat={pesoShort}
                series={[{ key: "revenue", label: "Revenue", color: "var(--color-ab-chart-1)", values: data.monthly.map((m) => m.revenue) }]} />
            </Section>
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Section title="By property type" action={<Select label="Measure" value={segmentMeasure} onChange={(v) => setSegmentMeasure(v as "transactions" | "revenue")} options={[{ value: "transactions", label: "Transactions" }, { value: "revenue", label: "Revenue" }]} />}>
              <BarList empty="No recorded activity yet." format={segmentMeasure === "revenue" ? pesoShort : count}
                rows={data.breakdown.by_category.map((g) => ({ name: g.name, value: g[segmentMeasure], note: `${g.listings ?? 0} listings · ${g.available ?? 0} available · ${g.reservations} reservations · ${g.sales} sales` }))} />
            </Section>
            <Section title="By agent base location">
              <BarList empty="No recorded activity yet." format={segmentMeasure === "revenue" ? pesoShort : count}
                rows={data.breakdown.by_area.map((g) => ({ name: g.name, value: g[segmentMeasure], note: `${g.reservations} reservations · ${g.sales} sales · ${peso(g.revenue)}` }))} />
              <p className="mt-3 text-xs text-ab-faint">{data.breakdown.area_basis}</p>
            </Section>
          </div>

          <InsightPanel title="ALTY Analysis" insights={data.insights} empty="No analysis items right now." />

          <div>
            <h2 className="mb-2 font-bold">Property performance</h2>
            <DataTable rows={data.breakdown.properties} columns={propertyColumns} rowKey={(p) => String(p.listing_id)} empty="No listings." initialSort={{ key: "revenue", dir: "desc" }} />
            <p className="mt-2 text-xs text-ab-faint">Counts are reservations and sales recorded in ALTY. Website views and inquiries aren't recorded yet, so interest before a reservation isn't shown.</p>
          </div>

          <div className="space-y-5">
            <div>
              <h2 className="mb-2 font-bold">Agent performance</h2>
              <DataTable rows={data.overview.agents} columns={agentColumns} rowKey={(a) => a.agent_id} empty="No agents." initialSort={{ key: "value", dir: "desc" }} />
            </div>
            <div>
              <h2 className="mb-2 font-bold">Prices by property type</h2>
              <div className="overflow-x-auto rounded-2xl border border-ab-border bg-ab-card">
                <table className="w-full text-left text-sm">
                  <thead className="text-[11px] uppercase tracking-wide text-ab-faint">
                    <tr className="border-b border-ab-border"><th className="px-4 py-3 font-semibold">Type</th><th className="px-4 py-3 text-right font-semibold">Listings</th><th className="px-4 py-3 text-right font-semibold">Average</th><th className="px-4 py-3 text-right font-semibold">Range</th></tr>
                  </thead>
                  <tbody>
                    {data.overview.price_by_category.map((c) => (
                      <tr key={c.category} className="border-b border-ab-border last:border-0">
                        <td className="px-4 py-3">{categoryLabel(c.category)}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{c.listings}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{c.average_price != null ? pesoShort(c.average_price) : "—"}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-ab-muted">{c.min_price != null && c.max_price != null ? `${pesoShort(c.min_price)} – ${pesoShort(c.max_price)}` : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
