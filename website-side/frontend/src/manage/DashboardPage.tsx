import { useCallback, useState, type ReactNode } from "react"
import { AlertTriangle, ArrowLeftRight, Building2, FileWarning, TrendingUp, type LucideIcon } from "lucide-react"
import { Link } from "@/components/Link"
import { Legend, ShareBar, StackedBarChart, TableToggle } from "./charts"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"
import { statusLabel, transactionDate } from "./format"
import { locale, t } from "./i18n"
import { CancelReason } from "./cancellation"

// What the Admin / Marketing staff watch: sales revenue, transactions and the
// status of the properties. Sellers' rankings live on the Sellers page.
type Summary = {
  total_properties: number; available_properties: number; reserved_properties: number; sold_properties: number
  completed_revenue: number
  processing_documents: number; failed_documents: number; pending_documents: number
}
type PropertyStatus = { available: number; reserved: number; sold: number; on_hold: number; unavailable: number; total: number }
type TxTrend = { months: string[]; counts: number[]; reservations: number[]; sales: number[]; has_data: boolean }
type RevenueTrend = { months: string[]; revenue: number[]; has_data: boolean }
type TxSummary = { total: number; reserved: number; completed: number; cancelled: number }
type Recent = { transaction_id: string; client_name: string | null; property_title: string | null; agent_name: string | null; transaction_type: string; transaction_date: string; amount: number; status: string; cancellation_reason?: string | null }
type Forecast = { status: "estimated" | "insufficient_data" | string; forecast: { month: string; value: number; lower: number; upper: number }[] }
type Data = { summary: Summary; status: PropertyStatus; tx: TxTrend; revenue: RevenueTrend; txSummary: TxSummary; recent: Recent[]; forecast: Forecast }

const peso = (value: number) => `₱${Math.round(value).toLocaleString(locale())}`
const pesoShort = (value: number) =>
  value >= 1e9 ? `₱${+(value / 1e9).toFixed(1)}B` : value >= 1e6 ? `₱${+(value / 1e6).toFixed(1)}M` : value >= 1e3 ? `₱${Math.round(value / 1e3)}K` : `₱${value}`
const count = (value: number) => String(Math.round(value))
const monthName = (month: string) => {
  const [y, m] = month.split("-").map(Number)
  return new Date(y, m - 1, 1).toLocaleDateString(locale(), { month: "long", year: "numeric" })
}

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

function Card({ title, action, children, className = "", tour }: { title: string; action?: ReactNode; children: ReactNode; className?: string; tour?: string }) {
  return (
    <section className={`rounded-2xl border border-ab-border bg-ab-card p-5 ${className}`} data-tour={tour}>
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
  const [txTable, setTxTable] = useState(false)
  const [revenueTable, setRevenueTable] = useState(false)

  const load = useCallback(async (): Promise<Data> => {
    const [summary, status, tx, revenue, txSummary, recent, forecast] = await Promise.all([
      api<Summary>("/dashboard/summary"),
      api<PropertyStatus>("/dashboard/property-status"),
      api<TxTrend>("/dashboard/transaction-trend?months=12"),
      api<RevenueTrend>("/dashboard/revenue-trend"),
      api<TxSummary>("/transactions/summary"),
      api<Recent[]>("/dashboard/recent-transactions?limit=8"),
      api<Forecast>("/dashboard/forecast"),
    ])
    return { summary, status, tx, revenue, txSummary, recent, forecast }
  }, [api])
  // Shows the last dashboard straight away on a return visit; it then keeps
  // itself up to date (useApiData refreshes it in the background).
  const { data, error, reload } = useApiData(load, "dashboard")

  const today = new Date().toLocaleDateString(locale(), { weekday: "long", month: "long", day: "numeric", year: "numeric" })

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div data-tour="dash-greeting">
          <p className="text-sm text-ab-muted">{today}</p>
          <p className="text-2xl font-extrabold">{greeting()}, {user?.full_name}</p>
        </div>
        <p className="inline-flex items-center gap-1.5 text-xs text-ab-muted" title={t("The numbers update by themselves.")}>
          <span className="relative flex h-2 w-2" aria-hidden>
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ab-success opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-ab-success" />
          </span>
          {t("Live")}
        </p>
      </div>

      {error && !data && (
        <p role="alert" className="flex items-center gap-2 rounded-xl border border-ab-danger/40 bg-ab-danger/10 px-4 py-3 text-sm text-ab-danger">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {t("Couldn't load the dashboard: {error}", { error })}
          <button type="button" onClick={() => void reload()} className="ml-auto font-semibold underline">{t("Try again")}</button>
        </p>
      )}

      {!data && !error && (
        <div className="space-y-5" aria-busy="true" aria-label={t("Loading dashboard")}>
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-28" />)}</div>
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
  const { summary, status, tx, revenue, txSummary, recent, forecast } = data
  const attention = summary.failed_documents + summary.processing_documents + summary.pending_documents
  const soldShare = status.total ? Math.round((status.sold / status.total) * 100) : null
  const next = forecast.status === "estimated" ? forecast.forecast[0] : undefined

  return (
    <>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4" data-tour="dash-kpis">
        <Kpi icon={TrendingUp} label="Sales revenue" value={pesoShort(summary.completed_revenue)}
          detail={t("From {n} completed sales", { n: txSummary.completed })} />
        <Kpi icon={ArrowLeftRight} label="Transactions" value={count(txSummary.total)}
          detail={t("{r} reserved · {c} completed · {x} cancelled", { r: txSummary.reserved, c: txSummary.completed, x: txSummary.cancelled })} />
        <Kpi icon={Building2} label="Properties" value={count(summary.total_properties)}
          detail={t("{a} available · {r} reserved · {s} sold", { a: summary.available_properties, r: summary.reserved_properties, s: summary.sold_properties })} />
        <Kpi icon={FileWarning} label="Documents to check" value={count(attention)}
          detail={summary.failed_documents ? t("{n} could not be read", { n: summary.failed_documents })
            : attention ? t("Being read now") : t("All documents read")}
          tone={summary.failed_documents ? "text-ab-danger" : "text-ab-muted"} />
      </div>

      <div className="grid gap-5 lg:grid-cols-3" data-tour="dash-charts">
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
          {next && (
            <p className="mt-3 rounded-xl bg-ab-card-2 px-3 py-2 text-sm text-ab-muted">
              {t("Expected in {month}", { month: monthName(next.month) })}: <span className="font-bold text-ab-text">{pesoShort(next.value)}</span>
              <span className="text-xs"> · {t("an estimate from past months, likely between {low} and {high}", { low: pesoShort(next.lower), high: pesoShort(next.upper) })}</span>
            </p>
          )}
        </Card>

        <Card title="Property status">
          <p className="mb-3 text-3xl font-extrabold tabular-nums">{status.total}<span className="ml-1.5 text-sm font-semibold text-ab-muted">{t("properties")}</span></p>
          <ShareBar
            parts={[
              { label: t("Available"), value: status.available, color: "var(--color-ab-chart-1)", always: true },
              { label: t("Reserved"), value: status.reserved, color: "var(--color-ab-chart-2)", always: true },
              { label: t("Sold"), value: status.sold, color: "var(--color-ab-muted)", always: true },
              { label: t("On hold"), value: status.on_hold, color: "var(--color-ab-warning)", always: false },
              { label: t("Unavailable"), value: status.unavailable, color: "var(--color-ab-danger)", always: false },
            ].filter((part) => part.always || part.value > 0).map(({ label, value, color }) => ({ label, value, color }))}
          />
          {soldShare != null && (
            <p className="mt-4 border-t border-ab-border pt-3 text-xs text-ab-muted">
              {t("{p}% of the properties are already sold.", { p: soldShare })}
            </p>
          )}
        </Card>
      </div>

      <Card title="Reservations and sales per month" action={<TableToggle shown={txTable} onToggle={() => setTxTable(!txTable)} />}>
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
            height={200}
          />
        ) : (
          <p className="py-10 text-center text-sm text-ab-muted">{t("No transactions recorded in the last 12 months.")}</p>
        )}
      </Card>

      <Card title="Latest transactions" tour="dash-recent"
        action={<Link to="/manage/transactions" className="text-xs font-semibold text-ab-accent hover:underline">{t("See all")}</Link>}>
        {recent.length === 0 ? (
          <p className="text-sm text-ab-muted">{t("No transactions recorded yet.")}</p>
        ) : <RecentTable rows={recent} />}
      </Card>
    </>
  )
}

/** Property first (with its price and seller underneath), then the buyer, the
 *  date and the status. "Seller" and "Buyer" are always written out so the
 *  two names are never mixed up. */
function RecentTable({ rows }: { rows: Recent[] }) {
  const priceLabel = (tx: Recent) => t(tx.transaction_type === "RESERVED" ? "Reservation fee" : "Sale price")
  return (
    <>
      <table className="hidden w-full text-left text-sm md:table">
        <thead className="text-[11px] uppercase tracking-wide text-ab-faint">
          <tr className="border-b border-ab-border">
            <th className="py-2 pr-4 font-semibold">{t("Property")}</th>
            <th className="py-2 pr-4 font-semibold">{t("Buyer")}</th>
            <th className="py-2 pr-4 font-semibold">{t("Date")}</th>
            <th className="py-2 font-semibold">{t("Status")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((tx) => (
            <tr key={tx.transaction_id} className="border-b border-ab-border last:border-0 align-top">
              <td className="py-3 pr-4">
                <Link to={`/manage/transactions?id=${tx.transaction_id}`} className="font-bold text-ab-text hover:text-ab-accent hover:underline">{tx.property_title ?? "—"}</Link>
                <p className="mt-0.5 text-xs text-ab-muted">
                  <span className="text-ab-faint">{priceLabel(tx)}</span> <span className="font-semibold tabular-nums text-ab-text">{peso(tx.amount)}</span>
                  {tx.agent_name && <> · <span className="text-ab-faint">{t("Seller")}</span> {tx.agent_name}</>}
                </p>
                <CancelReason status={tx.status} reason={tx.cancellation_reason} compact />
              </td>
              <td className="py-3 pr-4">{tx.client_name ?? t("Unknown buyer")}</td>
              <td className="whitespace-nowrap py-3 pr-4 text-ab-muted">{transactionDate(tx.transaction_date)}</td>
              <td className="py-3">
                <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-bold uppercase ${STATUS_STYLE[tx.status] ?? "bg-ab-hover text-ab-muted"}`}>{statusLabel(tx.status)}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ul className="space-y-3 md:hidden">
        {rows.map((tx) => (
          <li key={tx.transaction_id} className="rounded-xl border border-ab-border p-3 text-sm">
            <Link to={`/manage/transactions?id=${tx.transaction_id}`} className="font-bold text-ab-text hover:underline">{tx.property_title ?? "—"}</Link>
            <p className="mt-0.5 text-xs"><span className="text-ab-faint">{priceLabel(tx)}</span> <span className="font-semibold tabular-nums">{peso(tx.amount)}</span></p>
            <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-2 text-xs">
              {tx.agent_name && <><dt className="text-ab-faint">{t("Seller")}</dt><dd>{tx.agent_name}</dd></>}
              <dt className="text-ab-faint">{t("Buyer")}</dt><dd>{tx.client_name ?? t("Unknown buyer")}</dd>
            </dl>
            <p className="mt-2 flex items-center justify-between gap-2 text-xs text-ab-muted">
              {transactionDate(tx.transaction_date)}
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${STATUS_STYLE[tx.status] ?? "bg-ab-hover text-ab-muted"}`}>{statusLabel(tx.status)}</span>
            </p>
            <CancelReason status={tx.status} reason={tx.cancellation_reason} compact />
          </li>
        ))}
      </ul>
    </>
  )
}
