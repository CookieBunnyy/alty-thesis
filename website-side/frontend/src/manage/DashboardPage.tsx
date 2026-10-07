import { useCallback, useEffect, useState, type ReactNode } from "react"
import { AlertTriangle, ArrowLeftRight, Building2, FileWarning, RefreshCw, TrendingUp, UserRound, Users, type LucideIcon } from "lucide-react"
import { Legend, ShareBar, StackedBarChart, TableToggle } from "./charts"
import { useStaffAuth } from "./staffContext"
import { statusLabel, transactionDate } from "./format"
import { locale, t } from "./i18n"

// Every number below comes from the same API the desktop dashboard uses.
type Summary = {
  total_properties: number; available_properties: number; reserved_properties: number; sold_properties: number
  total_clients: number; total_transactions: number; completed_revenue: number
  active_agents: number; total_agents: number
  processing_documents: number; failed_documents: number; successful_documents: number; pending_documents: number
}
type PropertyStatus = { available: number; reserved: number; sold: number; on_hold: number; unavailable: number; total: number }
type TxTrend = { months: string[]; counts: number[]; reservations: number[]; sales: number[]; has_data: boolean }
type RevenueTrend = { months: string[]; revenue: number[]; has_data: boolean }
type TxSummary = { total: number; reserved: number; completed: number; cancelled: number; amount_total: string }
type Recent = { transaction_id: string; client_name: string | null; property_title: string | null; agent_name: string | null; transaction_type: string; transaction_date: string; amount: number; status: string }
type Overview = {
  absorption_rate: number | null
  transactions: { average_sale_value: number | null }
  agents: { agent_id: string; full_name: string; status: string; transactions: number; completed_sales: number; sales_value: number; recorded_total_commission: number | null }[]
}
type Forecast = {
  status: "estimated" | "insufficient_data" | string; message?: string; method?: string
  observations: number; nonzero_months: number; minimum_required: number
  forecast: { month: string; value: number; lower: number; upper: number }[]
}

type Data = {
  summary: Summary; status: PropertyStatus; tx: TxTrend; revenue: RevenueTrend; txSummary: TxSummary
  recent: Recent[]; overview: Overview; forecast: Forecast
}

const peso = (value: number) => `₱${Math.round(value).toLocaleString(locale())}`
const pesoShort = (value: number) =>
  value >= 1e9 ? `₱${+(value / 1e9).toFixed(1)}B` : value >= 1e6 ? `₱${+(value / 1e6).toFixed(1)}M` : value >= 1e3 ? `₱${Math.round(value / 1e3)}K` : `₱${value}`
const count = (value: number) => String(Math.round(value))

const STATUS_STYLE: Record<string, string> = {
  RESERVED: "bg-ab-info/15 text-ab-info",
  COMPLETED: "bg-ab-success/15 text-ab-success",
  SOLD: "bg-ab-success/15 text-ab-success",
  CANCELLED: "bg-ab-danger/15 text-ab-danger",
}

function greeting(): string {
  const hour = new Date().getHours()
  return t(hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening")
}

function Card({ title, action, children, className = "" }: { title: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-ab-border bg-ab-card p-5 ${className}`}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="font-bold text-ab-text">{t(title)}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

function Kpi({ icon: Icon, label, value, detail, tone = "text-ab-muted" }: { icon: LucideIcon; label: string; value: string; detail: ReactNode; tone?: string }) {
  return (
    <div className="rounded-2xl border border-ab-border bg-ab-card p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-ab-muted">{t(label)}</p>
        <Icon className="h-4 w-4 text-ab-faint" aria-hidden />
      </div>
      <p className="mt-2 text-2xl font-extrabold tabular-nums text-ab-text">{value}</p>
      <p className={`mt-1 text-xs ${tone}`}>{detail}</p>
    </div>
  )
}

function Skeleton({ className }: { className: string }) {
  return <div className={`ab-skeleton rounded-2xl ${className}`} />
}

export function DashboardPage() {
  const { api, user } = useStaffAuth()
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState("")
  const [txTable, setTxTable] = useState(false)
  const [revenueTable, setRevenueTable] = useState(false)

  const load = useCallback(async () => {
    setError("")
    try {
      const [summary, status, tx, revenue, txSummary, recent, overview, forecast] = await Promise.all([
        api<Summary>("/dashboard/summary"),
        api<PropertyStatus>("/dashboard/property-status"),
        api<TxTrend>("/dashboard/transaction-trend?months=12"),
        api<RevenueTrend>("/dashboard/revenue-trend"),
        api<TxSummary>("/transactions/summary"),
        api<Recent[]>("/dashboard/recent-transactions"),
        api<Overview>("/analytics/overview"),
        api<Forecast>("/dashboard/forecast"),
      ])
      setData({ summary, status, tx, revenue, txSummary, recent, overview, forecast })
    } catch (loadError) {
      setError((loadError as Error).message)
    }
  }, [api])

  useEffect(() => {
    // Fetching from the API (an external system) when the page opens.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load()
  }, [load])

  const today = new Date().toLocaleDateString(locale(), { weekday: "long", month: "long", day: "numeric", year: "numeric" })

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-ab-muted">{today}</p>
          <p className="text-2xl font-extrabold">{greeting()}, {user?.full_name}</p>
        </div>
        <button
          type="button"
          onClick={() => { setData(null); void load() }}
          className="inline-flex items-center gap-1.5 rounded-xl border border-ab-border-strong px-3 py-2 text-sm font-semibold hover:bg-ab-hover"
        >
          <RefreshCw className="h-4 w-4" /> {t("Refresh")}
        </button>
      </div>

      {error && (
        <p role="alert" className="flex items-center gap-2 rounded-xl border border-ab-danger/40 bg-ab-danger/10 px-4 py-3 text-sm text-ab-danger">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {t("Couldn't load the dashboard: {error}", { error })}
          <button type="button" onClick={() => void load()} className="ml-auto font-semibold underline">{t("Try again")}</button>
        </p>
      )}

      {!data && !error && (
        <div className="space-y-5" aria-busy="true" aria-label={t("Loading dashboard")}>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-28" />)}</div>
          <div className="grid gap-5 lg:grid-cols-3"><Skeleton className="h-72 lg:col-span-2" /><Skeleton className="h-72" /></div>
        </div>
      )}

      {data && <DashboardBody data={data} txTable={txTable} setTxTable={setTxTable} revenueTable={revenueTable} setRevenueTable={setRevenueTable} />}
    </div>
  )
}

function DashboardBody({ data, txTable, setTxTable, revenueTable, setRevenueTable }: {
  data: Data; txTable: boolean; setTxTable: (v: boolean) => void; revenueTable: boolean; setRevenueTable: (v: boolean) => void
}) {
  const { summary, status, tx, revenue, txSummary, recent, overview, forecast } = data
  const attention = summary.failed_documents + summary.processing_documents + summary.pending_documents
  const agents = [...overview.agents].sort((a, b) => b.sales_value - a.sales_value || b.transactions - a.transactions).slice(0, 6)

  return (
    <>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        <Kpi icon={Building2} label="Total properties" value={count(summary.total_properties)}
          detail={t("{a} available · {r} reserved · {s} sold", { a: summary.available_properties, r: summary.reserved_properties, s: summary.sold_properties })} />
        <Kpi icon={Users} label="Buyers & sellers" value={count(summary.total_clients)} detail={t("From client records")} />
        <Kpi icon={ArrowLeftRight} label="Transactions" value={count(txSummary.total)}
          detail={t("{r} reserved · {c} completed · {x} cancelled", { r: txSummary.reserved, c: txSummary.completed, x: txSummary.cancelled })} />
        <Kpi icon={TrendingUp} label="Sales revenue" value={pesoShort(summary.completed_revenue)}
          detail={overview.transactions.average_sale_value ? t("Avg sale {v}", { v: pesoShort(overview.transactions.average_sale_value) }) : t("Completed sales")} />
        <Kpi icon={UserRound} label="Active agents" value={count(summary.active_agents)} detail={t("of {n} agent records", { n: summary.total_agents })} />
        <Kpi icon={FileWarning} label="Documents needing attention" value={count(attention)}
          detail={t("{f} failed · {p} processing · {d} done", { f: summary.failed_documents, p: summary.processing_documents, d: summary.successful_documents })}
          tone={summary.failed_documents ? "text-ab-danger" : "text-ab-muted"} />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card
          title="Transactions per month"
          className="lg:col-span-2"
          action={<TableToggle shown={txTable} onToggle={() => setTxTable(!txTable)} />}
        >
          <div className="mb-3"><Legend items={[{ label: t("Reservations"), color: "var(--color-ab-chart-2)" }, { label: t("Completed sales"), color: "var(--color-ab-chart-1)" }]} /></div>
          {tx.has_data ? (
            <StackedBarChart
              caption={t("Reservations and completed sales recorded per month, last 12 months")}
              months={tx.months}
              series={[
                { key: "reservations", label: t("Reservations"), color: "var(--color-ab-chart-2)", values: tx.reservations },
                { key: "sales", label: t("Completed sales"), color: "var(--color-ab-chart-1)", values: tx.sales },
              ]}
              format={count}
              integer
              showTable={txTable}
            />
          ) : (
            <p className="py-10 text-center text-sm text-ab-muted">{t("No transactions recorded in the last 12 months.")}</p>
          )}
        </Card>

        <Card title="Property status">
          <p className="mb-3 text-3xl font-extrabold tabular-nums">{status.total}<span className="ml-1.5 text-sm font-semibold text-ab-muted">{t("listings")}</span></p>
          <ShareBar
            parts={[
              { label: t("Available"), value: status.available, color: "var(--color-ab-chart-1)" },
              { label: t("Reserved"), value: status.reserved, color: "var(--color-ab-chart-2)" },
              { label: t("Sold"), value: status.sold, color: "var(--color-ab-muted)" },
              { label: t("On hold"), value: status.on_hold, color: "var(--color-ab-warning)" },
              { label: t("Unavailable"), value: status.unavailable, color: "var(--color-ab-danger)" },
            ]}
          />
          {overview.absorption_rate != null && (
            <p className="mt-4 border-t border-ab-border pt-3 text-xs text-ab-muted">
              {t("Absorption rate")} <span className="font-semibold text-ab-text">{Math.round(overview.absorption_rate * 100)}%</span> — {t("share of listings already sold.")}
            </p>
          )}
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card title="Sales revenue per month" className="lg:col-span-2" action={<TableToggle shown={revenueTable} onToggle={() => setRevenueTable(!revenueTable)} />}>
          {revenue.has_data ? (
            <StackedBarChart
              caption={t("Revenue from completed sales per month, last 12 months")}
              months={revenue.months}
              series={[{ key: "revenue", label: t("Revenue"), color: "var(--color-ab-chart-1)", values: revenue.revenue }]}
              format={peso}
              axisFormat={pesoShort}
              showTable={revenueTable}
            />
          ) : (
            <p className="py-10 text-center text-sm text-ab-muted">{t("No completed sales in the last 12 months.")}</p>
          )}
        </Card>

        <Card title="Revenue forecast">
          {forecast.status === "estimated" && forecast.forecast.length ? (
            <>
              <p className="text-xs text-ab-muted">{t("Next month ({month})", { month: forecast.forecast[0].month })}</p>
              <p className="text-3xl font-extrabold tabular-nums">{pesoShort(forecast.forecast[0].value)}</p>
              <p className="mt-1 text-sm text-ab-muted">
                {t("Likely range {low} – {high}", { low: pesoShort(forecast.forecast[0].lower), high: pesoShort(forecast.forecast[0].upper) })}
              </p>
              <p className="mt-3 text-xs text-ab-faint">{t(forecast.method ?? "")} · {t("{n} months of history.", { n: forecast.observations })}</p>
            </>
          ) : (
            <div className="rounded-xl border border-dashed border-ab-border p-4">
              <p className="font-semibold text-ab-text">{t(forecast.message || "Forecast unavailable.")}</p>
              <p className="mt-1 text-sm text-ab-muted">
                {t("Needs at least {min} complete months, with sales in 3 or more of them. Recorded so far: {n} month(s), {s} with sales. No forecast is shown until there's enough real data.", { min: forecast.minimum_required, n: forecast.observations, s: forecast.nonzero_months })}
              </p>
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card title="Agent performance" className="lg:col-span-2">
          {agents.length === 0 ? (
            <p className="text-sm text-ab-muted">{t("No agent records.")}</p>
          ) : (
            <>
              {/* Phones: one card per agent. */}
              <ul className="space-y-2 sm:hidden">
                {agents.map((a) => (
                  <li key={a.agent_id} className="rounded-xl border border-ab-border p-3 text-sm">
                    <p className="font-semibold">{a.full_name}</p>
                    <p className="mt-1 text-xs text-ab-muted">
                      {t("{n} transactions · {s} sales", { n: a.transactions, s: a.completed_sales })} · {peso(a.sales_value)}
                      {a.recorded_total_commission != null && ` · ${t("commission {v}", { v: peso(a.recorded_total_commission) })}`}
                    </p>
                  </li>
                ))}
              </ul>
              <div className="ab-table-scroll hidden sm:block">
                <table className="w-full text-left text-sm">
                  <thead className="text-[11px] uppercase tracking-wide text-ab-faint">
                    <tr>
                      <th className="pb-2 pr-3 font-semibold">{t("Agent")}</th>
                      <th className="pb-2 pr-3 text-right font-semibold">{t("Transactions")}</th>
                      <th className="pb-2 pr-3 text-right font-semibold">{t("Completed sales")}</th>
                      <th className="pb-2 pr-3 text-right font-semibold">{t("Sales value")}</th>
                      <th className="pb-2 text-right font-semibold">{t("Recorded commission")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agents.map((a) => (
                      <tr key={a.agent_id} className="border-t border-ab-border">
                        <td className="py-2.5 pr-3">
                          <span className="font-semibold">{a.full_name}</span>
                          <span className="ml-2 text-xs text-ab-faint">{a.agent_id}</span>
                        </td>
                        <td className="py-2.5 pr-3 text-right tabular-nums">{a.transactions}</td>
                        <td className="py-2.5 pr-3 text-right tabular-nums">{a.completed_sales}</td>
                        <td className="py-2.5 pr-3 text-right tabular-nums">{peso(a.sales_value)}</td>
                        <td className="py-2.5 text-right tabular-nums text-ab-muted">{a.recorded_total_commission != null ? peso(a.recorded_total_commission) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-xs text-ab-faint">{t("Top {n} by sales value. Commission is the figure recorded on the agent's record.", { n: agents.length })}</p>
            </>
          )}
        </Card>

        <Card title="Recent transactions">
          {recent.length === 0 ? (
            <p className="text-sm text-ab-muted">{t("No transactions recorded yet.")}</p>
          ) : (
            <ul className="space-y-3">
              {recent.slice(0, 6).map((tx) => (
                <li key={tx.transaction_id} className="text-sm">
                  <div className="flex items-start justify-between gap-2">
                    <p className="min-w-0 truncate font-semibold">{tx.client_name ?? t("Unknown client")}</p>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${STATUS_STYLE[tx.status] ?? "bg-ab-hover text-ab-muted"}`}>{statusLabel(tx.status)}</span>
                  </div>
                  <p className="truncate text-xs text-ab-muted">{tx.property_title ?? "—"}</p>
                  <p className="text-xs text-ab-faint">
                    {transactionDate(tx.transaction_date)} · {peso(tx.amount)}
                    {tx.agent_name && ` · ${tx.agent_name}`}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  )
}
