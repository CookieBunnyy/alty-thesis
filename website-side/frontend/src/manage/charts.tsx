// Small dependency-free charts for the management dashboard.
// Rules followed (dataviz guidance): one y-axis, thin bars with 4px rounded
// data-ends on the baseline, 2px surface gaps between stacked segments,
// recessive grid, legend for 2+ series, text in ink colours (never the series
// colour), per-column hover tooltip, and a table view of the same numbers.
import { useEffect, useId, useRef, useState } from "react"
import { Table2 } from "lucide-react"
import { locale, t } from "./i18n"

export type Series = { key: string; label: string; color: string; values: number[] }

/** "2026-07" -> "Jul" (plus the year on January and the first column). */
function monthLabel(month: string, index: number): string {
  const [year, m] = month.split("-")
  const index0 = Number(m) - 1
  const name = index0 >= 0 && index0 < 12 ? new Date(2000, index0, 1).toLocaleString(locale(), { month: "short" }) : month
  return index === 0 || m === "01" ? `${name} ${year.slice(2)}` : name
}

function niceMax(value: number): number {
  if (value <= 0) return 1
  const exp = 10 ** Math.floor(Math.log10(value))
  const f = value / exp
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * exp
}

export function Legend({ items }: { items: { label: string; color: string; value?: string }[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-ab-muted">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-[3px]" style={{ background: item.color }} aria-hidden />
          <span>{item.label}</span>
          {item.value && <span className="font-semibold tabular-nums text-ab-text">{item.value}</span>}
        </li>
      ))}
    </ul>
  )
}

export function TableToggle({ shown, onToggle }: { shown: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={shown}
      className="inline-flex items-center gap-1 rounded-lg border border-ab-border px-2 py-1 text-[11px] font-semibold text-ab-muted hover:bg-ab-hover hover:text-ab-text"
    >
      <Table2 className="h-3.5 w-3.5" /> {shown ? t("Chart") : t("Table")}
    </button>
  )
}

type BarChartProps = {
  months: string[]
  series: Series[]
  format: (value: number) => string
  /** Compact axis labels (e.g. ₱10M). Defaults to ``format``. */
  axisFormat?: (value: number) => string
  height?: number
  showTable: boolean
  caption: string
  /** Whole-number values (counts): gridlines at whole numbers only. */
  integer?: boolean
}

/** Pixel width of an element, kept up to date (charts are drawn at real size
 *  so their text stays readable on phones). */
function useWidth<T extends HTMLElement>() {
  const ref = useRef<T | null>(null)
  const [width, setWidth] = useState(600)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(240, Math.round(entry.contentRect.width))))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return [ref, width] as const
}

/** Monthly bars; several series are stacked (they are parts of one total). */
export function StackedBarChart({ months, series, format, axisFormat = format, height = 220, showTable, caption, integer = false }: BarChartProps) {
  const [hover, setHover] = useState<number | null>(null)
  const [wrapRef, width] = useWidth<HTMLDivElement>()
  const titleId = useId()
  const totals = months.map((_, i) => series.reduce((sum, s) => sum + (s.values[i] ?? 0), 0))
  const peak = Math.max(0, ...totals)
  const max = integer ? Math.max(2, Math.ceil(peak / 2) * 2) : niceMax(peak)
  const ticks = [0, max / 2, max]

  if (showTable) {
    return (
      <div className="ab-table-scroll">
        <table className="w-full text-left text-xs">
          <caption className="sr-only">{caption}</caption>
          <thead className="text-ab-faint">
            <tr>
              <th className="py-1.5 pr-3 font-semibold">{t("Month")}</th>
              {series.map((s) => <th key={s.key} className="py-1.5 pr-3 text-right font-semibold">{s.label}</th>)}
              {series.length > 1 && <th className="py-1.5 text-right font-semibold">{t("Total")}</th>}
            </tr>
          </thead>
          <tbody>
            {months.map((month, i) => (
              <tr key={month} className="border-t border-ab-border">
                <td className="py-1.5 pr-3 text-ab-muted">{month}</td>
                {series.map((s) => <td key={s.key} className="py-1.5 pr-3 text-right tabular-nums">{format(s.values[i] ?? 0)}</td>)}
                {series.length > 1 && <td className="py-1.5 text-right font-semibold tabular-nums">{format(totals[i])}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  const W = width
  const H = height
  const narrow = W < 480 // phones: label every other month
  const left = 44
  const bottom = 22
  const top = 8
  const plotH = H - bottom - top
  const step = (W - left) / months.length
  const barW = Math.min(28, step * 0.56)
  const y = (v: number) => top + plotH - (v / max) * plotH

  return (
    <div className="relative w-full min-w-0" ref={wrapRef}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} className="block" role="img" aria-labelledby={titleId}>
        <title id={titleId}>{caption}</title>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={left} x2={W} y1={y(t)} y2={y(t)} stroke="var(--color-ab-border)" strokeWidth={1} />
            <text x={left - 6} y={y(t) + 3.5} textAnchor="end" fontSize={11} fill="var(--color-ab-faint)">{axisFormat(t)}</text>
          </g>
        ))}
        {months.map((month, i) => {
          const cx = left + step * i + step / 2
          let base = 0
          const parts = series
            .map((s) => ({ s, v: s.values[i] ?? 0 }))
            .filter((p) => p.v > 0)
          return (
            <g key={month}>
              {hover === i && <rect x={left + step * i + 2} y={top} width={step - 4} height={plotH} rx={6} fill="var(--color-ab-hover)" opacity={0.6} />}
              {parts.map((p, j) => {
                const y0 = y(base)
                base += p.v
                const y1 = y(base)
                const isTop = j === parts.length - 1
                const gap = j > 0 ? 2 : 0 // 2px surface gap between stacked segments
                const h = Math.max(1, y0 - y1 - gap)
                return isTop ? (
                  <path
                    key={p.s.key}
                    d={`M${cx - barW / 2},${y0 - gap} v${-(h - 4)} q0,-4 4,-4 h${barW - 8} q4,0 4,4 v${h - 4} z`}
                    fill={p.s.color}
                  />
                ) : (
                  <rect key={p.s.key} x={cx - barW / 2} y={y0 - gap - h} width={barW} height={h} fill={p.s.color} />
                )
              })}
              {totals[i] === 0 && <rect x={cx - barW / 2} y={y(0) - 2} width={barW} height={2} rx={1} fill="var(--color-ab-border-strong)" />}
              {(!narrow || i % 2 === 0 || hover === i) && (
                <text x={cx} y={H - 6} textAnchor="middle" fontSize={11} fill={hover === i ? "var(--color-ab-text)" : "var(--color-ab-faint)"}>
                  {monthLabel(month, i)}
                </text>
              )}
              {/* hit target: the whole column, bigger than the bar */}
              <rect
                x={left + step * i}
                y={top}
                width={step}
                height={plotH + bottom}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(i)}
                onBlur={() => setHover(null)}
                tabIndex={0}
                aria-label={`${month}: ${series.map((s) => `${s.label} ${format(s.values[i] ?? 0)}`).join(", ")}`}
              />
            </g>
          )
        })}
      </svg>
      {hover !== null && (
        <div
          className={`pointer-events-none absolute top-1 z-10 min-w-36 rounded-xl border border-ab-border-strong bg-ab-card-2 px-3 py-2 text-xs shadow-lg ${
            left + step * hover + step / 2 > W / 2 ? "-translate-x-full" : ""
          }`}
          // Beside the hovered column (left of it on the right half), never over its bars.
          style={{ left: left + step * hover + step / 2 + (left + step * hover + step / 2 > W / 2 ? -(barW / 2 + 8) : barW / 2 + 8) }}
          role="status"
        >
          <p className="mb-1 font-semibold text-ab-text">{months[hover]}</p>
          {series.map((s) => (
            <p key={s.key} className="flex items-center justify-between gap-3 text-ab-muted">
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm" style={{ background: s.color }} />{s.label}</span>
              <span className="font-semibold tabular-nums text-ab-text">{format(s.values[hover] ?? 0)}</span>
            </p>
          ))}
          {series.length > 1 && (
            <p className="mt-1 flex justify-between border-t border-ab-border pt-1 text-ab-muted">
              Total <span className="font-semibold tabular-nums text-ab-text">{format(totals[hover])}</span>
            </p>
          )}
        </div>
      )}
    </div>
  )
}

/** One 100% bar split by category (e.g. property status), with a legend. */
export function ShareBar({ parts }: { parts: { label: string; value: number; color: string }[] }) {
  const total = parts.reduce((sum, p) => sum + p.value, 0)
  const [hover, setHover] = useState<string | null>(null)
  return (
    <div>
      <div className="flex h-4 w-full gap-[2px] overflow-hidden rounded-[4px] bg-ab-card-2" role="img" aria-label={parts.map((p) => `${p.label} ${p.value}`).join(", ")}>
        {total > 0 &&
          parts
            .filter((p) => p.value > 0)
            .map((p) => (
              <span
                key={p.label}
                title={`${p.label}: ${p.value} (${Math.round((p.value / total) * 100)}%)`}
                onMouseEnter={() => setHover(p.label)}
                onMouseLeave={() => setHover(null)}
                className="h-full transition-opacity"
                style={{ width: `${(p.value / total) * 100}%`, background: p.color, opacity: hover && hover !== p.label ? 0.45 : 1 }}
              />
            ))}
      </div>
      <ul className="mt-4 space-y-2 text-sm">
        {parts.map((p) => (
          <li
            key={p.label}
            className={`flex items-center justify-between gap-3 rounded-lg px-1 ${hover === p.label ? "bg-ab-hover" : ""}`}
            onMouseEnter={() => setHover(p.label)}
            onMouseLeave={() => setHover(null)}
          >
            <span className="flex items-center gap-2 text-ab-muted">
              <span className="h-2.5 w-2.5 rounded-[3px]" style={{ background: p.color }} aria-hidden /> {p.label}
            </span>
            <span className="tabular-nums">
              <span className="font-semibold text-ab-text">{p.value}</span>
              <span className="ml-1.5 text-xs text-ab-faint">{total ? `${Math.round((p.value / total) * 100)}%` : "—"}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

type ForecastPoint = { month: string; value: number; lower: number; upper: number }

/** History (solid) followed by forecast months (lighter, outlined) with the
 *  likely range drawn as a whisker. One y-axis; hover shows exact values. */
export function ForecastChart({ history, forecast, format, axisFormat = format, caption, height = 240 }: {
  history: { month: string; value: number }[]; forecast: ForecastPoint[]
  format: (v: number) => string; axisFormat?: (v: number) => string; caption: string; height?: number
}) {
  const [hover, setHover] = useState<number | null>(null)
  const [wrapRef, width] = useWidth<HTMLDivElement>()
  const titleId = useId()
  const columns = [
    ...history.map((h) => ({ month: h.month, value: h.value, kind: "history" as const })),
    ...forecast.map((f) => ({ month: f.month, value: f.value, lower: f.lower, upper: f.upper, kind: "forecast" as const })),
  ]
  const max = niceMax(Math.max(0, ...columns.map((c) => ("upper" in c && c.upper != null ? c.upper : c.value))))
  const W = width
  const H = height
  const left = 52
  const bottom = 22
  const top = 8
  const plotH = H - bottom - top
  const step = (W - left) / Math.max(1, columns.length)
  const barW = Math.min(28, step * 0.56)
  const y = (v: number) => top + plotH - (Math.max(0, v) / max) * plotH
  const narrow = W < 480
  const boundary = left + step * history.length

  return (
    <div className="relative w-full min-w-0" ref={wrapRef}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} className="block" role="img" aria-labelledby={titleId}>
        <title id={titleId}>{caption}</title>
        {[0, max / 2, max].map((t) => (
          <g key={t}>
            <line x1={left} x2={W} y1={y(t)} y2={y(t)} stroke="var(--color-ab-border)" />
            <text x={left - 6} y={y(t) + 3.5} textAnchor="end" fontSize={11} fill="var(--color-ab-faint)">{axisFormat(t)}</text>
          </g>
        ))}
        {forecast.length > 0 && (
          <>
            <rect x={boundary} y={top} width={W - boundary} height={plotH} fill="var(--color-ab-chart-2)" opacity={0.06} />
            <text x={boundary + 6} y={top + 12} fontSize={10} fill="var(--color-ab-faint)">{t("Forecast")}</text>
          </>
        )}
        {columns.map((c, i) => {
          const cx = left + step * i + step / 2
          const h = Math.max(c.value > 0 ? 2 : 0, y(0) - y(c.value))
          return (
            <g key={c.month}>
              {hover === i && <rect x={left + step * i + 2} y={top} width={step - 4} height={plotH} rx={6} fill="var(--color-ab-hover)" opacity={0.6} />}
              {c.kind === "history" ? (
                h > 0 ? <path d={`M${cx - barW / 2},${y(0)} v${-(Math.max(h, 4) - 4)} q0,-4 4,-4 h${barW - 8} q4,0 4,4 v${Math.max(h, 4) - 4} z`} fill="var(--color-ab-chart-1)" />
                  : <rect x={cx - barW / 2} y={y(0) - 2} width={barW} height={2} rx={1} fill="var(--color-ab-border-strong)" />
              ) : (
                <>
                  <rect x={cx - barW / 2} y={y(c.value)} width={barW} height={Math.max(1, h)} rx={4} fill="var(--color-ab-chart-2)" fillOpacity={0.3}
                    stroke="var(--color-ab-chart-2)" strokeWidth={1.5} strokeDasharray="4 3" />
                  {"upper" in c && (
                    <g stroke="var(--color-ab-text)" strokeWidth={1.5} opacity={0.75}>
                      <line x1={cx} x2={cx} y1={y(c.upper)} y2={y(c.lower)} />
                      <line x1={cx - 6} x2={cx + 6} y1={y(c.upper)} y2={y(c.upper)} />
                      <line x1={cx - 6} x2={cx + 6} y1={y(c.lower)} y2={y(c.lower)} />
                    </g>
                  )}
                </>
              )}
              {(!narrow || i % 2 === 0 || hover === i) && (
                <text x={cx} y={H - 6} textAnchor="middle" fontSize={11} fill={hover === i ? "var(--color-ab-text)" : "var(--color-ab-faint)"}>{monthLabel(c.month, i)}</text>
              )}
              <rect x={left + step * i} y={top} width={step} height={plotH + bottom} fill="transparent" tabIndex={0}
                onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}
                aria-label={`${c.month}: ${c.kind === "forecast" ? `${t("forecast")} ` : ""}${format(c.value)}${"upper" in c ? `, ${t("Likely range {low} – {high}", { low: format(c.lower), high: format(c.upper) })}` : ""}`} />
            </g>
          )
        })}
      </svg>
      {hover !== null && (() => {
        const c = columns[hover]
        const x = left + step * hover + step / 2
        const flip = x > W / 2
        return (
          <div className={`pointer-events-none absolute top-1 z-10 min-w-40 rounded-xl border border-ab-border-strong bg-ab-card-2 px-3 py-2 text-xs shadow-lg ${flip ? "-translate-x-full" : ""}`}
            style={{ left: x + (flip ? -(barW / 2 + 8) : barW / 2 + 8) }} role="status">
            <p className="font-semibold text-ab-text">{c.month} {c.kind === "forecast" && <span className="font-normal text-ab-faint">· {t("forecast")}</span>}</p>
            <p className="mt-0.5 tabular-nums text-ab-text">{format(c.value)}</p>
            {"upper" in c && <p className="tabular-nums text-ab-muted">{t("Likely range {low} – {high}", { low: format(c.lower), high: format(c.upper) })}</p>}
          </div>
        )
      })()}
    </div>
  )
}

/** Horizontal bars for a ranked breakdown (one measure, one colour). */
export function BarList({ rows, format, empty }: { rows: { name: string; value: number; note?: string }[]; format: (v: number) => string; empty: string }) {
  const max = Math.max(0, ...rows.map((r) => r.value))
  if (!rows.length || max === 0) return <p className="py-6 text-center text-sm text-ab-muted">{t(empty)}</p>
  return (
    <ul className="space-y-2.5">
      {rows.map((r) => (
        <li key={r.name} className="text-sm">
          <div className="flex items-baseline justify-between gap-2">
            <span className="min-w-0 truncate text-ab-text">{r.name}</span>
            <span className="shrink-0 font-semibold tabular-nums text-ab-text">{format(r.value)}</span>
          </div>
          <div className="mt-1 h-2.5 overflow-hidden rounded-[4px] bg-ab-card-2">
            <div className="h-full rounded-[4px]" style={{ width: `${(r.value / max) * 100}%`, background: "var(--color-ab-chart-1)" }} />
          </div>
          {r.note && <p className="mt-0.5 text-xs text-ab-faint">{r.note}</p>}
        </li>
      ))}
    </ul>
  )
}
