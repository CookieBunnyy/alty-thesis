import { useCallback, useMemo, useState } from "react"
import { ForecastChart, Legend, type BacktestPoint } from "./charts"
import { peso, pesoShort, statusLabel, transactionDate } from "./format"
import { InsightPanel, type Insight } from "./Insights"
import { LoadState, PageHeader, Section, Select } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"
import { locale, t } from "./i18n"
import { Link } from "@/components/Link"

type Model = {
  months_used: number; first_month: string; last_month: string; average_month_number: number; average_value: number
  intercept: number; slope: number; x: number; trend_value: number; sigma: number
  seasonal: boolean; seasonal_months_needed: number; seasonal_factor: number | null; seasonal_seen: number
  seasonal_raw: number | null; seasonal_weight: number | null
}
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

/** One step of the working (a titled box). */
function Step({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0 rounded-xl bg-ab-card-2 p-3">
      <p className="text-sm font-bold">{title}</p>
      <div className="mt-1.5 space-y-1.5 break-words text-sm text-ab-muted">{children}</div>
    </div>
  )
}

/** A labelled number, with what it means underneath (wraps on phones). */
function Line({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-3">
      <span className="min-w-0 text-ab-muted">{label}</span>
      <span className="font-semibold tabular-nums text-ab-text">{value}</span>
      {note && <span className="w-full text-xs text-ab-faint">{note}</span>}
    </div>
  )
}

/** "How this month was worked out", in plain words: the records behind the
 *  figure, the trend line and seasonal step with their numbers, and the verdict. */
function MonthWorking({ month, metric, outlook }: { month: string; metric: Metric; outlook: Outlook }) {
  const { api } = useStaffAuth()
  const look = METRICS[metric]
  // Counts keep one decimal in the working (averages like 2.4 sales a month).
  const num = metric === "revenue" ? peso : (v: number) => v.toLocaleString(locale(), { maximumFractionDigits: 1 })
  const recorded = outlook.history.find((h) => h.month === month)
  const past = outlook.backtest.find((b) => b.month === month)
  const future = outlook.forecast.find((f) => f.month === month)
  const point: Point | undefined = past ?? future
  const model = point?.model
  const hasRecord = Boolean(recorded)
  const load = useCallback(
    () => (hasRecord ? api<MonthDetail>(`/intelligence/outlook/month?month=${month}&metric=${metric}`) : Promise.resolve(null)),
    [api, month, metric, hasRecord],
  )
  const { data, error, loading, reload } = useApiData(load, `outlook-month:${metric}:${month}`)
  const [showMonths, setShowMonths] = useState(false)
  const used = model ? outlook.history.filter((h) => h.month >= model.first_month && h.month <= model.last_month) : []
  const monthOnly = (key: string) => new Date(Number(key.slice(0, 4)), Number(key.slice(5, 7)) - 1, 1).toLocaleDateString(locale(), { month: "long" })
  const weightWords = (w: number | null) => (w == null ? "" : Math.abs(w - 0.5) < 0.01 ? t("half") : Math.abs(w - 2 / 3) < 0.01 ? t("two-thirds") : `${Math.round(w * 100)}%`)


  return (
    <Section title={t("How {month} was worked out", { month: monthName(month) })}>
      <div className="grid gap-5 lg:grid-cols-2">
        {/* 1. The recorded figure, summed up */}
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("1. What actually happened")}</p>
          {!recorded ? (
            <p className="mt-2 text-sm text-ab-muted">{t("This month hasn't happened yet, so there is nothing recorded to compare.")}</p>
          ) : (
            <>
              <LoadState loading={loading && !data} error={error} onRetry={reload} />
              {data && (
                <>
                  <p className="mt-2 text-sm text-ab-muted">
                    {metric === "revenue"
                      ? t("We added up every sale finished this month. Reservations and cancelled deals don't count.")
                      : metric === "sales"
                        ? t("We counted every sale finished this month.")
                        : t("We counted every reservation and sale this month, except cancelled ones.")}
                  </p>
                  {data.items.length === 0 ? (
                    <p className="mt-3 rounded-xl bg-ab-card-2 p-3 text-sm text-ab-muted">{t("Nothing was recorded this month, so the figure is {v}.", { v: look.format(0) })}</p>
                  ) : (
                    <ol className="mt-3 max-h-72 space-y-1 overflow-y-auto rounded-xl bg-ab-card-2 p-3 text-sm">
                      {data.items.map((item, index) => (
                        <li key={item.transaction_id} className="flex items-baseline justify-between gap-3">
                          <span className="min-w-0 flex-1">
                            <span className="text-ab-faint">{index === 0 ? "" : "+ "}</span>
                            <span className="break-words font-medium">{item.property ?? t("Property")}</span>
                            <span className="block break-words text-xs text-ab-faint">{transactionDate(item.date)} · {item.client ?? "—"} · {item.agent ?? "—"}{metric === "transactions" ? ` · ${statusLabel(item.type)}` : ""}</span>
                          </span>
                          <span className="shrink-0 tabular-nums">{metric === "revenue" ? peso(item.amount) : "1"}</span>
                        </li>
                      ))}
                      <li className="mt-1 flex items-baseline justify-between gap-3 border-t border-ab-border pt-2 font-bold">
                        <span>{t("Total for the month")}</span>
                        <span className="shrink-0 tabular-nums">{look.format(data.total)}</span>
                      </li>
                    </ol>
                  )}
                </>
              )}
            </>
          )}
        </div>

        {/* 2. What we expected and how; 3. the verdict */}
        <div className="min-w-0 space-y-3">
          <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("2. What we expected, and how")}</p>
          {!model || !point ? (
            <p className="text-sm text-ab-muted">
              {t("No forecast for this month: we need at least {min} earlier months, with sales in 3 or more of them.", { min: outlook.minimum_required })}
            </p>
          ) : (
            <>
              <Step title={t("Step A · The trend line")}>
                <p>
                  {t("We lined up the {n} months before it ({from} to {to}) and drew the one straight line that comes closest to all of them. That line shows the general direction of sales.", {
                    n: model.months_used, from: monthName(model.first_month), to: monthName(model.last_month),
                  })}
                </p>
                <button type="button" onClick={() => setShowMonths((v) => !v)} aria-expanded={showMonths} className="text-xs font-semibold text-ab-accent hover:underline">
                  {showMonths ? t("Hide the months used") : t("See the months used")}
                </button>
                {showMonths && (
                  <ol className="max-h-56 overflow-y-auto rounded-lg border border-ab-border bg-ab-card p-2 text-xs">
                    {used.map((h, i) => (
                      <li key={h.month} className="flex justify-between gap-2">
                        <span>{t("Month {n}", { n: i })} · {monthName(h.month)}</span>
                        <span className="tabular-nums text-ab-text">{num(h.value)}</span>
                      </li>
                    ))}
                  </ol>
                )}
                <Line label={t("Average sales per month")} value={num(model.average_value)} note={t("All {n} months added up, divided by {n}.", { n: model.months_used })} />
                <Line label={t("Trend")} value={`${model.slope >= 0 ? "+" : "−"}${num(Math.abs(model.slope))} ${t("a month")}`}
                  note={model.slope >= 0 ? t("On average, sales grew by this much from one month to the next.") : t("On average, sales dropped by this much from one month to the next.")} />
                <Line label={t("Starting level")} value={num(model.intercept)}
                  note={t("Where the line starts, at month 0 ({from}): the average ({avg}) minus the trend times the middle month ({mid}).", {
                    from: monthName(model.first_month), avg: num(model.average_value), mid: model.average_month_number,
                  })} />
                <Line label={t("Trend line for {month} (month {x})", { month: monthOnly(month), x: model.x })}
                  value={num(model.trend_value)}
                  note={`${num(model.intercept)} ${model.slope >= 0 ? "+" : "−"} ${num(Math.abs(model.slope))} × ${model.x} = ${num(model.trend_value)}`} />
              </Step>

              <Step title={t("Step B · The usual pattern for {month}", { month: monthOnly(month) })}>
                {model.seasonal && model.seasonal_factor != null && model.seasonal_raw != null ? (
                  <>
                    <p>
                      {model.seasonal_raw >= 1
                        ? t("Before, {month} sold {pct}% more than the trend line (seen {n} time(s)).", { month: monthOnly(month), pct: Math.round((model.seasonal_raw - 1) * 100), n: model.seasonal_seen })
                        : t("Before, {month} sold {pct}% less than the trend line (seen {n} time(s)).", { month: monthOnly(month), pct: Math.round((1 - model.seasonal_raw) * 100), n: model.seasonal_seen })}
                      {" "}
                      {model.seasonal_seen > 0
                        ? t("One year can be a fluke, so we count only {w} of that difference until we have seen more years.", { w: weightWords(model.seasonal_weight) })
                        : t("We haven't seen this month before, so it gets no adjustment.")}
                    </p>
                    {model.seasonal_weight != null && Math.abs(1 + model.seasonal_weight * (model.seasonal_raw - 1) - model.seasonal_factor) > 0.005 && (
                      <p className="text-xs text-ab-faint">
                        {t("That gives × {damped}; the 12 months are then evened out so the whole year still adds up to the trend line, which makes it × {factor}.", {
                          damped: (1 + model.seasonal_weight * (model.seasonal_raw - 1)).toFixed(2), factor: model.seasonal_factor.toFixed(2),
                        })}
                      </p>
                    )}
                    <Line label={t("Seasonal factor")} value={`× ${model.seasonal_factor.toFixed(2)}`} />
                    <Line label={t("Expected for {month}", { month: monthOnly(month) })} value={look.format(point.value)}
                      note={`${num(model.trend_value)} × ${model.seasonal_factor.toFixed(2)} = ${look.format(point.value)}`} />
                  </>
                ) : (
                  <>
                    <p>{t("Not used yet: spotting a seasonal pattern needs at least {need} months of history, and this forecast had {n}. Expected = the trend line.", { need: model.seasonal_months_needed, n: model.months_used })}</p>
                    <Line label={t("Expected for {month}", { month: monthOnly(month) })} value={look.format(point.value)} />
                  </>
                )}
              </Step>

              <Step title={t("Step C · The likely range")}>
                <p>{t("Real months never sit exactly on the line. Past months were usually about {s} above or below it. Allowing about twice that either way covers normal months 95 times out of 100.", { s: num(model.sigma) })}</p>
                <Line label={t("Likely range")} value={`${look.format(point.lower)} – ${look.format(point.upper)}`}
                  note={`${look.format(point.value)} ± 1.96 × ${num(model.sigma)}`} />
              </Step>
            </>
          )}

          <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("3. Did it land in the range?")}</p>
          {past ? (
            <div className={`rounded-xl px-3 py-2.5 text-sm ${VERDICT[past.verdict].tone}`}>
              <p className="font-bold">{t(VERDICT[past.verdict].label)}</p>
              <p className="mt-0.5 break-words">
                {past.verdict === "WITHIN"
                  ? t("Yes. {a} landed inside {low} – {high}: a normal month.", { a: look.format(past.actual), low: look.format(past.lower), high: look.format(past.upper) })
                  : past.verdict === "ABOVE"
                    ? t("Better than expected: {a}, which is {d} above the high end ({high}).", { a: look.format(past.actual), d: look.format(past.actual - past.upper), high: look.format(past.upper) })
                    : t("Lower than expected: {a}, which is {d} below the low end ({low}).", { a: look.format(past.actual), d: look.format(past.lower - past.actual), low: look.format(past.lower) })}
              </p>
            </div>
          ) : (
            <p className="text-sm text-ab-muted">
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
