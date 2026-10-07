import { useCallback, useState } from "react"
import { ForecastChart, Legend } from "./charts"
import { peso, pesoShort } from "./format"
import { InsightPanel, type Insight } from "./Insights"
import { LoadState, PageHeader, Section, Select } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"
import { locale, t } from "./i18n"

type Forecast = {
  metric: string; status: "estimated" | "insufficient_data"; message?: string
  observations: number; nonzero_months: number; minimum_required: number
  history: { month: string; value: number }[]
  forecast: { month: string; value: number; lower: number; upper: number }[]
  method?: string; slope_per_month?: number; r_squared?: number | null; interval?: string
}

const METRICS = {
  revenue: { label: "Sales revenue", format: peso, axis: pesoShort },
  transactions: { label: "Transactions", format: (v: number) => String(Math.round(v)), axis: (v: number) => String(Math.round(v)) },
  sales: { label: "Completed sales", format: (v: number) => String(Math.round(v)), axis: (v: number) => String(Math.round(v)) },
} as const
type Metric = keyof typeof METRICS

const monthName = (key: string) => {
  const [year, month] = key.split("-").map(Number)
  return new Date(year, month - 1, 1).toLocaleDateString(locale(), { month: "long", year: "numeric" })
}

export function ForecastingPage() {
  const { api } = useStaffAuth()
  const [metric, setMetric] = useState<Metric>("revenue")
  const [horizon, setHorizon] = useState("3")
  const load = useCallback(() => api<{ forecast: Forecast; insights: Insight[] }>(`/intelligence/forecast?metric=${metric}&horizon=${horizon}`), [api, metric, horizon])
  const { data, error, loading, reload } = useApiData(load)
  const look = METRICS[metric]
  const f = data?.forecast

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Forecasting"
        subtitle="Projections from the recorded monthly history (linear trend over complete months). A forecast is only shown when there is enough real history; ALTY then interprets it."
        actions={
          <>
            <div role="tablist" aria-label={t("Forecast measure")} className="flex rounded-xl border border-ab-border bg-ab-card p-1">
              {(Object.keys(METRICS) as Metric[]).map((key) => (
                <button key={key} type="button" role="tab" aria-selected={metric === key} onClick={() => setMetric(key)}
                  className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${metric === key ? "bg-ab-accent text-ab-ink" : "text-ab-muted hover:text-ab-text"}`}>
                  {t(METRICS[key].label)}
                </button>
              ))}
            </div>
            <Select label="Horizon" value={horizon} onChange={setHorizon} options={[{ value: "3", label: "Next 3 months" }, { value: "6", label: "Next 6 months" }, { value: "12", label: "Next 12 months" }]} />
          </>
        }
      />
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {f && (
        <>
          {f.status === "estimated" ? (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              {f.forecast.slice(0, 3).map((p) => (
                <div key={p.month} className="rounded-2xl border border-ab-border bg-ab-card p-4">
                  <p className="text-xs font-semibold text-ab-muted">{monthName(p.month)}</p>
                  <p className="mt-1.5 text-2xl font-extrabold tabular-nums">{look.axis(p.value)}</p>
                  <p className="mt-0.5 text-xs text-ab-faint">{t("Likely {low} – {high}", { low: look.axis(p.lower), high: look.axis(p.upper) })}</p>
                </div>
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

          <Section title={t(f.status === "estimated" ? "{measure}: history and forecast" : "{measure}: history", { measure: t(look.label) })}>
            <div className="mb-3">
              <Legend items={[
                { label: t("Recorded"), color: "var(--color-ab-chart-1)" },
                ...(f.status === "estimated" ? [{ label: t("Forecast (with likely range)"), color: "var(--color-ab-chart-2)" }] : []),
              ]} />
            </div>
            {f.history.length ? (
              <ForecastChart caption={t("{measure} per month with forecast", { measure: t(look.label) })} history={f.history} forecast={f.forecast} format={look.format} axisFormat={look.axis} />
            ) : (
              <p className="py-10 text-center text-sm text-ab-muted">{t("No complete months recorded yet.")}</p>
            )}
            {f.status === "estimated" && (
              <p className="mt-3 text-xs text-ab-faint">
                {t(f.method ?? "")}. {t("Trend {v} per month", { v: f.slope_per_month != null ? `${f.slope_per_month >= 0 ? "+" : ""}${look.format(f.slope_per_month)}` : "—" })}
                {f.r_squared != null && ` · R² ${f.r_squared.toFixed(2)}`} · {t("range:")} {t(f.interval ?? "")}.
              </p>
            )}
          </Section>

          {f.status === "estimated" && (
            <div className="ab-table-scroll rounded-2xl border border-ab-border bg-ab-card">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">{t("Forecast values")}</caption>
                <thead className="text-[11px] uppercase tracking-wide text-ab-faint">
                  <tr className="border-b border-ab-border"><th className="px-4 py-3 font-semibold">{t("Month")}</th><th className="px-4 py-3 text-right font-semibold">{t("Forecast")}</th><th className="px-4 py-3 text-right font-semibold">{t("Likely range")}</th></tr>
                </thead>
                <tbody>
                  {f.forecast.map((p) => (
                    <tr key={p.month} className="border-b border-ab-border last:border-0">
                      <td className="px-4 py-3">{monthName(p.month)}</td>
                      <td className="px-4 py-3 text-right font-semibold tabular-nums">{look.format(p.value)}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ab-muted">{look.format(p.lower)} – {look.format(p.upper)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <InsightPanel insights={data!.insights} />
        </>
      )}
    </div>
  )
}
