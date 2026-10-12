import { useCallback, useMemo, useState } from "react"
import { ForecastChart, Legend, type BacktestPoint } from "./charts"
import { peso, pesoShort, statusLabel, transactionDate } from "./format"
import { InsightPanel, type Insight } from "./Insights"
import { LoadState, PageHeader, Section, Select } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"
import { locale, t } from "./i18n"
import { Link } from "@/components/Link"

type Model = { months_used: number; first_month: string; intercept: number; slope: number; x: number; sigma: number }
type Point = { month: string; value: number; lower: number; upper: number; model?: Model }
type Outlook = {
  metric: string; status: "estimated" | "insufficient_data"; message?: string
  observations: number; nonzero_months: number; minimum_required: number
  history: { month: string; value: number }[]
  forecast: Point[]
  backtest: (BacktestPoint & { model: Model })[]
  accuracy: { months: number; within: number; above: number; below: number }
  method?: string; slope_per_month?: number; r_squared?: number | null; interval?: string
}
type MonthDetail = {
  month: string; metric: string; count: number; total: number
  items: { transaction_id: string; date: string; type: string; status: string; amount: number; client: string | null; property: string | null; agent: string | null }[]
}

const count = (v: number) => String(Math.round(v))
const METRICS = {
  revenue: { label: "Sales revenue", format: peso, axis: pesoShort, unit: "sales revenue" },
  transactions: { label: "Transactions", format: count, axis: count, unit: "transactions" },
  sales: { label: "Completed sales", format: count, axis: count, unit: "completed sales" },
} as const
type Metric = keyof typeof METRICS

const monthName = (key: string) => {
  const [year, month] = key.split("-").map(Number)
  return new Date(year, month - 1, 1).toLocaleDateString(locale(), { month: "long", year: "numeric" })
}
const shiftMonth = (key: string, delta: number) => {
  const [year, month] = key.split("-").map(Number)
  const index = year * 12 + (month - 1) + delta
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`
}

const VERDICT = {
  WITHIN: { label: "Met the likely range", tone: "bg-ab-accent-soft text-ab-accent" },
  ABOVE: { label: "Above the likely range", tone: "bg-ab-warning/15 text-ab-text" },
  BELOW: { label: "Below the likely range", tone: "bg-ab-danger/10 text-ab-danger" },
} as const

type AgentRow = {
  agent_id: string; full_name: string; status: string; observations: number; nonzero_months: number
  minimum_required: number; recent_sales: number; expected_sales: number | null; trend_per_month: number | null
}

/** Each active agent's expected completed sales for the next 3 months. */
function AgentOutlook() {
  const { api } = useStaffAuth()
  const load = useCallback(() => api<{ horizon: number; agents: AgentRow[] }>("/intelligence/agent-forecasts?horizon=3"), [api])
  const { data, error, loading, reload } = useApiData(load, "agent-forecasts")
  const rows = [...(data?.agents ?? [])].sort((a, b) => (b.expected_sales ?? -1) - (a.expected_sales ?? -1))
  return (
    <Section title="Agent performance outlook">
      <p className="mb-3 text-xs text-ab-faint">
        {t("Expected completed sales per agent for the next 3 months, from each agent's own monthly history (same method as above). Agents without enough history show why.")}
      </p>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (rows.length === 0 ? <p className="text-sm italic text-ab-faint">{t("No active agents.")}</p> : (
        <ul className="divide-y divide-ab-border text-sm">
          {rows.map((row) => (
            <li key={row.agent_id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2.5">
              <Link to={`/manage/agents?id=${encodeURIComponent(row.agent_id)}`} className="min-w-40 flex-1 font-semibold hover:underline">{row.full_name}</Link>
              {row.status === "estimated" ? (
                <>
                  <span className="tabular-nums"><span className="text-lg font-extrabold">{row.expected_sales?.toFixed(1)}</span> <span className="text-xs text-ab-faint">{t("expected sales")}</span></span>
                  <span className="text-xs text-ab-muted">
                    {t("{n} in the last 3 months", { n: row.recent_sales })}
                    {row.trend_per_month != null && ` · ${row.trend_per_month >= 0 ? "▲" : "▼"} ${Math.abs(row.trend_per_month).toFixed(2)} ${t("per month")}`}
                  </span>
                </>
              ) : (
                <span className="text-xs text-ab-faint">
                  {t("Not enough history ({n} month(s), {s} with sales)", { n: row.observations, s: row.nonzero_months })}
                </span>
              )}
            </li>
          ))}
        </ul>
      ))}
    </Section>
  )
}

/** "How this month was worked out": the records behind the figure, the
 *  forecast formula with its numbers, and whether the month met the range. */
function MonthWorking({ month, metric, outlook }: { month: string; metric: Metric; outlook: Outlook }) {
  const { api } = useStaffAuth()
  const look = METRICS[metric]
  const recorded = outlook.history.find((h) => h.month === month)
  const past = outlook.backtest.find((b) => b.month === month)
  const future = outlook.forecast.find((f) => f.month === month)
  const point: Point | undefined = past ?? future
  const hasRecord = Boolean(recorded)
  const load = useCallback(
    () => (hasRecord ? api<MonthDetail>(`/intelligence/outlook/month?month=${month}&metric=${metric}`) : Promise.resolve(null)),
    [api, month, metric, hasRecord],
  )
  const { data, error, loading, reload } = useApiData(load, `outlook-month:${metric}:${month}`)
  const signed = (v: number) => `${v < 0 ? "−" : "+"} ${look.format(Math.abs(v))}`

  return (
    <Section title={t("How {month} was worked out", { month: monthName(month) })}>
      <div className="grid gap-5 lg:grid-cols-2">
        {/* 1. The recorded figure, summed up */}
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("1. What was recorded")}</p>
          {!recorded ? (
            <p className="mt-2 text-sm text-ab-muted">{t("This month hasn't happened yet, so there is nothing recorded to compare.")}</p>
          ) : (
            <>
              <LoadState loading={loading && !data} error={error} onRetry={reload} />
              {data && (
                <>
                  <p className="mt-2 text-sm text-ab-muted">
                    {metric === "revenue"
                      ? t("Sales revenue is the sum of the completed sales dated in this month (reservations and cancelled records are left out).")
                      : metric === "sales"
                        ? t("Completed sales are counted when the sale is dated in this month.")
                        : t("Every reservation and sale dated in this month, except cancelled ones.")}
                  </p>
                  {data.items.length === 0 ? (
                    <p className="mt-3 rounded-xl bg-ab-card-2 p-3 text-sm text-ab-muted">{t("Nothing was recorded this month, so the figure is {v}.", { v: look.format(0) })}</p>
                  ) : (
                    <ol className="mt-3 max-h-72 space-y-1 overflow-y-auto rounded-xl bg-ab-card-2 p-3 text-sm">
                      {data.items.map((item, index) => (
                        <li key={item.transaction_id} className="flex items-baseline justify-between gap-3">
                          <span className="min-w-0">
                            <span className="text-ab-faint">{index === 0 ? "" : "+ "}</span>
                            <span className="font-medium">{item.property ?? t("Property")}</span>
                            <span className="block truncate text-xs text-ab-faint">{transactionDate(item.date)} · {item.client ?? "—"} · {item.agent ?? "—"}{metric === "transactions" ? ` · ${statusLabel(item.type)}` : ""}</span>
                          </span>
                          <span className="shrink-0 tabular-nums">{metric === "revenue" ? peso(item.amount) : "1"}</span>
                        </li>
                      ))}
                      <li className="mt-1 flex items-baseline justify-between gap-3 border-t border-ab-border pt-2 font-bold">
                        <span>{t("Total for the month")}</span>
                        <span className="tabular-nums">{look.format(data.total)}</span>
                      </li>
                    </ol>
                  )}
                </>
              )}
            </>
          )}
        </div>

        {/* 2. The forecast for it, and 3. the verdict */}
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("2. What the forecast said")}</p>
          {!point?.model ? (
            <p className="mt-2 text-sm text-ab-muted">
              {t("No forecast for this month: a forecast needs at least {min} earlier complete months, with activity in 3 or more of them.", { min: outlook.minimum_required })}
            </p>
          ) : (
            <div className="mt-2 space-y-2 text-sm">
              <p className="text-ab-muted">
                {t("A straight trend line was fitted to the {n} complete months before it ({from} to {to}), months numbered 0, 1, 2…", {
                  n: point.model.months_used, from: monthName(point.model.first_month), to: monthName(shiftMonth(point.model.first_month, point.model.months_used - 1)),
                })}
              </p>
              <div className="space-y-1 rounded-xl bg-ab-card-2 p-3 font-mono text-[12px] leading-relaxed">
                <p>{t("forecast = starting level + trend × month number")}</p>
                <p>= {look.format(point.model.intercept)} {signed(point.model.slope)} × {point.model.x}</p>
                <p className="font-bold">= {look.format(point.value)}{point.model.intercept + point.model.slope * point.model.x < 0 ? ` ${t("(never below zero)")}` : ""}</p>
                <p className="pt-1">{t("likely range = forecast ± 1.96 × spread")}</p>
                <p>{t("spread (how far past months sat from the line) = {s}", { s: look.format(point.model.sigma) })}</p>
                <p className="font-bold">= {look.format(point.lower)} – {look.format(point.upper)}</p>
              </div>
            </div>
          )}

          <p className="mt-4 text-xs font-bold uppercase tracking-wide text-ab-faint">{t("3. Did it meet the range?")}</p>
          {past ? (
            <div className={`mt-2 rounded-xl px-3 py-2.5 text-sm ${VERDICT[past.verdict].tone}`}>
              <p className="font-bold">{t(VERDICT[past.verdict].label)}</p>
              <p className="mt-0.5">
                {past.verdict === "WITHIN"
                  ? t("Recorded {a}, inside {low} – {high}.", { a: look.format(past.actual), low: look.format(past.lower), high: look.format(past.upper) })
                  : past.verdict === "ABOVE"
                    ? t("Recorded {a}, {d} more than the top of the range ({high}).", { a: look.format(past.actual), d: look.format(past.actual - past.upper), high: look.format(past.upper) })
                    : t("Recorded {a}, {d} less than the bottom of the range ({low}).", { a: look.format(past.actual), d: look.format(past.lower - past.actual), low: look.format(past.lower) })}
              </p>
            </div>
          ) : (
            <p className="mt-2 text-sm text-ab-muted">
              {future ? t("Not yet: check back after {month} ends.", { month: monthName(month) }) : t("There was no forecast to compare with.")}
            </p>
          )}
        </div>
      </div>
    </Section>
  )
}

export function ForecastingPage() {
  const { api } = useStaffAuth()
  const [metric, setMetric] = useState<Metric>("revenue")
  const [horizon, setHorizon] = useState("3")
  const [picked, setMonth] = useState<string | null>(null)
  const load = useCallback(() => api<{ forecast: Outlook; insights: Insight[] }>(`/intelligence/forecast?metric=${metric}&horizon=${horizon}`), [api, metric, horizon])
  const { data, error, loading, reload } = useApiData(load, `outlook:${metric}:${horizon}`)
  const look = METRICS[metric]
  const f = data?.forecast
  const months = useMemo(() => (f ? [...f.history.map((h) => h.month), ...f.forecast.map((p) => p.month)] : []), [f])
  // The picked month, or by default the latest month checked against a forecast (or the latest recorded one).
  const month = picked && months.includes(picked) ? picked : f?.backtest.at(-1)?.month ?? f?.history.at(-1)?.month ?? null
  const backtest = useMemo(() => new Map((f?.backtest ?? []).map((b) => [b.month, b])), [f])

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="How the business is doing, and what may come next"
        subtitle="Recorded months next to what the forecast expected for them, and the forecast for the coming months. Pick a month to see how its figure was added up, the formula behind its forecast, and whether it met the likely range."
        actions={
          <>
            <div role="tablist" aria-label={t("Measure")} className="flex rounded-xl border border-ab-border bg-ab-card p-1">
              {(Object.keys(METRICS) as Metric[]).map((key) => (
                <button key={key} type="button" role="tab" aria-selected={metric === key} onClick={() => setMetric(key)}
                  className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${metric === key ? "bg-ab-accent text-ab-ink" : "text-ab-muted hover:text-ab-text"}`}>
                  {t(METRICS[key].label)}
                </button>
              ))}
            </div>
            <Select label="Horizon" value={horizon} onChange={setHorizon} options={[{ value: "3", label: "Next 3 months" }, { value: "6", label: "Next 6 months" }, { value: "12", label: "Next 12 months" }]} />
            {months.length > 0 && (
              <Select label="Month" value={month ?? ""} onChange={setMonth}
                options={[...months].reverse().map((key) => ({ value: key, label: `${monthName(key)}${f?.forecast.some((p) => p.month === key) ? ` · ${t("forecast")}` : ""}` }))} />
            )}
          </>
        }
      />
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {f && (
        <>
          {f.status === "estimated" ? (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <div className="rounded-2xl border border-ab-border bg-ab-card p-4">
                <p className="text-xs font-semibold text-ab-muted">{t("Past months checked")}</p>
                <p className="mt-1.5 text-2xl font-extrabold tabular-nums">
                  {f.accuracy.within}<span className="text-base font-semibold text-ab-faint"> / {f.accuracy.months}</span>
                </p>
                <p className="mt-0.5 text-xs text-ab-faint">{t("met their likely range")}</p>
              </div>
              {f.forecast.slice(0, 3).map((p) => (
                <button key={p.month} type="button" onClick={() => setMonth(p.month)}
                  className={`rounded-2xl border bg-ab-card p-4 text-left transition hover:border-ab-border-strong ${month === p.month ? "border-ab-accent ring-2 ring-ab-accent/30" : "border-ab-border"}`}>
                  <p className="text-xs font-semibold text-ab-muted">{monthName(p.month)} · {t("forecast")}</p>
                  <p className="mt-1.5 text-2xl font-extrabold tabular-nums">{look.axis(p.value)}</p>
                  <p className="mt-0.5 text-xs text-ab-faint">{t("Likely {low} – {high}", { low: look.axis(p.lower), high: look.axis(p.upper) })}</p>
                </button>
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-ab-border bg-ab-card p-5">
              <p className="font-bold">{t(f.message ?? "Forecast unavailable.")}</p>
              <p className="mt-1 text-sm text-ab-muted">
                {t("A forecast needs at least {min} complete months, with activity in 3 or more of them. Recorded so far: {n} complete month(s), {a} with activity. ALTY doesn't show a forecast until the history supports one.", { min: f.minimum_required, n: f.observations, a: f.nonzero_months })}
              </p>
            </div>
          )}

          <Section title={t("{measure}: recorded, expected and forecast", { measure: t(look.label) })}>
            <div className="mb-3">
              <Legend items={[
                { label: t("Recorded"), color: "var(--color-ab-chart-1)" },
                ...(f.backtest.length ? [{ label: t("What the forecast expected (◆) and its likely range"), color: "var(--color-ab-chart-2)" }] : []),
                ...(f.status === "estimated" ? [{ label: t("Forecast (with likely range)"), color: "var(--color-ab-chart-2)" }] : []),
              ]} />
            </div>
            {f.history.length ? (
              <ForecastChart caption={t("{measure} per month with forecast", { measure: t(look.label) })} history={f.history} forecast={f.forecast}
                backtest={f.backtest} selected={month} onSelect={setMonth} format={look.format} axisFormat={look.axis} />
            ) : (
              <p className="py-10 text-center text-sm text-ab-muted">{t("No complete months recorded yet.")}</p>
            )}
            <p className="mt-3 text-xs text-ab-faint">
              {t("Click a month to see how it was worked out.")}{" "}
              {f.status === "estimated" && (
                <>
                  {t(f.method ?? "")}. {t("Trend {v} per month", { v: f.slope_per_month != null ? `${f.slope_per_month >= 0 ? "+" : ""}${look.format(f.slope_per_month)}` : "—" })}
                  {f.r_squared != null && ` · R² ${f.r_squared.toFixed(2)}`} · {t("range:")} {t(f.interval ?? "")}.
                </>
              )}
            </p>
          </Section>

          {month && <MonthWorking key={`${metric}:${month}`} month={month} metric={metric} outlook={f} />}

          <div className="ab-table-scroll rounded-2xl border border-ab-border bg-ab-card">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">{t("Recorded and forecast values per month")}</caption>
              <thead className="text-[11px] uppercase tracking-wide text-ab-faint">
                <tr className="border-b border-ab-border">
                  <th className="px-4 py-3 font-semibold">{t("Month")}</th>
                  <th className="px-4 py-3 text-right font-semibold">{t("Recorded")}</th>
                  <th className="px-4 py-3 text-right font-semibold">{t("Forecast")}</th>
                  <th className="px-4 py-3 text-right font-semibold">{t("Likely range")}</th>
                  <th className="px-4 py-3 font-semibold">{t("Result")}</th>
                </tr>
              </thead>
              <tbody>
                {[...months].reverse().map((key) => {
                  const recorded = f.history.find((h) => h.month === key)
                  const point = backtest.get(key) ?? f.forecast.find((p) => p.month === key)
                  const verdict = backtest.get(key)?.verdict
                  return (
                    <tr key={key} onClick={() => setMonth(key)} tabIndex={0}
                      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setMonth(key))}
                      className={`cursor-pointer border-b border-ab-border last:border-0 hover:bg-ab-hover focus:bg-ab-hover focus:outline-none ${month === key ? "bg-ab-accent-soft/60" : ""}`}>
                      <td className="px-4 py-3">{monthName(key)}</td>
                      <td className="px-4 py-3 text-right font-semibold tabular-nums">{recorded ? look.format(recorded.value) : "—"}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{point ? look.format(point.value) : "—"}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ab-muted">{point ? `${look.format(point.lower)} – ${look.format(point.upper)}` : "—"}</td>
                      <td className="px-4 py-3">
                        {verdict ? <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${VERDICT[verdict].tone}`}>{t(VERDICT[verdict].label)}</span>
                          : !recorded ? <span className="text-xs text-ab-faint">{t("Upcoming")}</span>
                            : <span className="text-xs text-ab-faint">{t("Not enough earlier history")}</span>}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <AgentOutlook />
          <InsightPanel insights={data!.insights} />
        </>
      )}
    </div>
  )
}
