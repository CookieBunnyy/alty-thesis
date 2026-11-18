// Business Outlook: a month's report, generated when asked for. It reads the
// month's recorded transactions and the forecast, then lays out a summary, the
// month's timeline, how the figure was worked out, why it fell short (when it
// did) and what to try. Everything comes from recorded data
// (/intelligence/outlook/month and /intelligence/outlook/diagnosis): no
// figures are invented, and suggestions are options for management to weigh.
import { useEffect, useMemo, useState, type ReactNode } from "react"
import {
  CalendarDays, CheckCircle2, ChevronDown, CircleAlert, FileText, Lightbulb, ListChecks, LoaderCircle, RotateCcw,
  SearchCheck, Sparkles, TrendingDown, TrendingUp,
} from "lucide-react"
import { categoryLabel } from "@/lib/categories"
import { peso, transactionDate } from "./format"
import { locale, t } from "./i18n"
import { useStaffAuth } from "./staffContext"

type Metric = "revenue" | "transactions" | "sales" | "commission"
type Verdict = "WITHIN" | "ABOVE" | "BELOW"
type Item = { transaction_id: string; date: string; type: string; status: string; amount: number; client: string | null; property: string | null; agent: string | null }
type MonthDetail = { month: string; count: number; total: number; items: Item[] }
type Group = { before: number; now: number; sales_before: number; sales_now: number }
type Finding =
  | { code: "FEWER_SALES"; impact: number; params: { now: number; before: number } }
  | { code: "LOWER_PRICE"; impact: number; params: { now: number; before: number; pct: number } }
  | { code: "CANCELLATIONS"; impact: null; params: { now: number; before: number; reasons: { reason: string; count: number }[] } }
  | { code: "FEWER_RESERVATIONS" | "FEWER_NEW_CLIENTS"; impact: null; params: { now: number; before: number } }
  | { code: "AGENT_DROP"; impact: number; params: { agents: (Group & { agent_id: string; name: string | null })[] } }
  | { code: "CATEGORY_DROP"; impact: number; params: { categories: (Group & { category: string })[] } }
  | { code: "LOW_STOCK"; impact: null; params: { categories: { category: string; available: number }[] } }
  | { code: "SEASONAL_LOW"; impact: null; params: { pct: number } }
  | { code: "NO_CLEAR_CAUSE"; impact: null; params: Record<string, never> }
type Stats = { sales: number; revenue: number; average_sale: number | null; reservations: number; cancellations: number; new_clients: number }
type Diagnosis = {
  previous_month: string; previous: number; change_pct: number | null; triggered: boolean
  reasons: ("BELOW_RANGE" | "BELOW_PREVIOUS")[]
  now?: Stats; before?: Stats
  revenue_change?: { total: number; from_sales_count: number; from_average_price: number }
  findings: Finding[]
}

/** What each cause means and what management could try. */
const SUGGESTIONS: Record<Finding["code"], string[]> = {
  FEWER_SALES: [
    "Follow up open reservations that are close to their down payment, so they turn into sales.",
    "Call back clients who enquired or visited but did not reserve, and ask what stopped them.",
    "Hold a short pipeline review with the agents: who is close to buying, and what is holding them back?",
  ],
  LOWER_PRICE: [
    "Check whether discounts or price cuts were given, and whether they were really needed to close.",
    "Put higher-value listings back in front of clients: feature them on the website and schedule site visits.",
    "Match clients with bigger budgets to the higher-priced listings.",
  ],
  CANCELLATIONS: [
    "Contact the clients who cancelled; some may take another property or a longer payment plan instead.",
    "Fix the most common reason at its source, for example check loan eligibility before the reservation, or explain the terms more clearly.",
  ],
  FEWER_RESERVATIONS: [
    "Fewer reservations now usually means fewer sales in the next months: run a reservation promo, such as a lower reservation fee for a limited time.",
    "Schedule site trippings for clients who enquired recently.",
  ],
  FEWER_NEW_CLIENTS: [
    "Increase marketing: refresh listing photos and details, post on social media, and ask past buyers for referrals.",
    "Make sure website and chatbot enquiries are answered the same day.",
  ],
  AGENT_DROP: [
    "Talk with these agents about their open clients and where the deals are stuck.",
    "Rebalance new clients so agents with free time get more of them.",
    "Pair them with the top seller this month for coaching on closing.",
  ],
  CATEGORY_DROP: [
    "Compare the prices and terms of these property types with similar listings nearby.",
    "Promote these types to the kind of clients who bought them before.",
  ],
  LOW_STOCK: [
    "Ask partner developers for more listings of these types; clients can't buy what isn't available.",
    "Offer interested clients similar properties in nearby areas.",
  ],
  SEASONAL_LOW: [
    "Plan promos ahead of this month next year.",
    "Use slow months for follow-ups and paperwork, so the next month starts with more clients ready to buy.",
  ],
  NO_CLEAR_CAUSE: [
    "Watch next month before changing the strategy: one weaker month can be normal.",
  ],
}
const KEEP_GOING = [
  "Keep following up open reservations so they become next month's sales.",
  "Ask this month's buyers for referrals while the experience is fresh.",
  "Keep the best-selling projects in front of clients: website, social media and site trippings.",
]

function findingTitle(f: Finding, monthOnly: string): string {
  switch (f.code) {
    case "FEWER_SALES": return t("Fewer deals closed: {now}, down from {before}", f.params)
    case "LOWER_PRICE": return t("Cheaper deals: {now} per sale on average, {pct}% below {before}", { ...f.params, now: peso(f.params.now), before: peso(f.params.before) })
    case "CANCELLATIONS": return t("{now} deal(s) cancelled (month before: {before})", { now: f.params.now, before: f.params.before })
    case "FEWER_RESERVATIONS": return t("Fewer new reservations: {now}, down from {before}", f.params)
    case "FEWER_NEW_CLIENTS": return t("Fewer new clients recorded: {now}, down from {before}", f.params)
    case "AGENT_DROP": return t("Agents who sold less")
    case "CATEGORY_DROP": return t("Property types that sold less")
    case "LOW_STOCK": return t("Little stock left in types that sell")
    case "SEASONAL_LOW": return t("{month} is usually a slow month", { month: monthOnly })
    case "NO_CLEAR_CAUSE": return t("No single cause stands out")
  }
}

function Evidence({ f }: { f: Finding }) {
  switch (f.code) {
    case "FEWER_SALES":
      return <p>{t("At the month before's average price, the missing deals explain about {v} of the drop.", { v: peso(f.impact) })}</p>
    case "LOWER_PRICE":
      return <p>{t("The deals that did close were cheaper, which explains about {v} of the drop.", { v: peso(f.impact) })}</p>
    case "CANCELLATIONS":
      return (
        <ul className="list-disc space-y-0.5 pl-5">
          {f.params.reasons.map((r) => <li key={r.reason} className="break-words">{r.reason === "No reason recorded" ? t(r.reason) : r.reason} <span className="text-ab-faint">× {r.count}</span></li>)}
        </ul>
      )
    case "FEWER_RESERVATIONS":
      return <p>{t("Reservations become the next months' sales, so this can keep sales low for a while.")}</p>
    case "FEWER_NEW_CLIENTS":
      return <p>{t("Fewer people started talking to ALTY, so there were fewer clients to sell to.")}</p>
    case "AGENT_DROP":
      return (
        <ul className="space-y-1">
          {f.params.agents.map((a) => (
            <li key={a.agent_id} className="flex flex-wrap justify-between gap-x-3">
              <span className="min-w-0 break-words font-medium text-ab-text">{a.name ?? t("Agent")}</span>
              <span className="tabular-nums">{peso(a.now)} <span className="text-ab-faint">({t("was {v}", { v: peso(a.before) })})</span></span>
            </li>
          ))}
        </ul>
      )
    case "CATEGORY_DROP":
      return (
        <ul className="space-y-1">
          {f.params.categories.map((c) => (
            <li key={c.category} className="flex flex-wrap justify-between gap-x-3">
              <span className="min-w-0 break-words font-medium text-ab-text">{t(categoryLabel(c.category))}</span>
              <span className="tabular-nums">{peso(c.now)} <span className="text-ab-faint">({t("was {v}", { v: peso(c.before) })})</span></span>
            </li>
          ))}
        </ul>
      )
    case "LOW_STOCK":
      return (
        <ul className="space-y-1">
          {f.params.categories.map((c) => (
            <li key={c.category} className="flex flex-wrap justify-between gap-x-3">
              <span className="min-w-0 break-words font-medium text-ab-text">{t(categoryLabel(c.category))}</span>
              <span className="tabular-nums">{t("{n} available now", { n: c.available })}</span>
            </li>
          ))}
        </ul>
      )
    case "SEASONAL_LOW":
      return <p>{t("In past years this month sold about {pct}% below the trend line, so part of the drop is the usual pattern.", f.params)}</p>
    case "NO_CLEAR_CAUSE":
      return <p>{t("Deals, prices, cancellations, agents and stock were about the same as the month before. The drop may be normal month-to-month variation.")}</p>
  }
}

const STEPS = ["Adding up the month's records…", "Comparing with what was expected…", "Looking for the causes…", "Writing the report…"]
const VERDICT_STYLE: Record<Verdict, { label: string; tone: string; icon: typeof CheckCircle2 }> = {
  WITHIN: { label: "Met the expected range", tone: "border-ab-success/40 bg-ab-success/10 text-ab-success", icon: CheckCircle2 },
  ABOVE: { label: "Better than expected", tone: "border-ab-success/40 bg-ab-success/10 text-ab-success", icon: TrendingUp },
  BELOW: { label: "Below the expected range", tone: "border-ab-danger/40 bg-ab-danger/10 text-ab-danger", icon: TrendingDown },
}

/** A numbered part of the report. */
function Part({ n, icon: Icon, title, children }: { n: number; icon: typeof FileText; title: string; children: ReactNode }) {
  return (
    <section className="ab-pop border-t border-ab-border pt-5" style={{ animationDelay: `${n * 80}ms` }}>
      <h3 className="mb-3 flex items-center gap-2 text-sm font-extrabold">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-ab-accent text-xs text-ab-ink">{n}</span>
        <Icon className="h-4 w-4 text-ab-accent" aria-hidden /> {title}
      </h3>
      {children}
    </section>
  )
}

export function MonthReport({ month, metric, label, monthName, format, recorded, expected, verdict, working }: {
  month: string
  metric: Metric
  label: string
  monthName: (key: string) => string
  format: (value: number) => string
  recorded: number | null
  expected: { value: number; lower: number; upper: number } | null
  verdict: Verdict | null
  working: ReactNode
}) {
  const { api } = useStaffAuth()
  const [state, setState] = useState<"idle" | "generating" | "ready" | "error">("idle")
  const [step, setStep] = useState(0)
  const [detail, setDetail] = useState<MonthDetail | null>(null)
  const [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null)
  const [problem, setProblem] = useState("")
  const [showWorking, setShowWorking] = useState(false)
  const [allCauses, setAllCauses] = useState(false)
  const [generatedAt, setGeneratedAt] = useState("")
  const name = monthName(month)
  const monthOnly = new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)) - 1, 1).toLocaleDateString(locale(), { month: "long" })
  const over = recorded != null

  // The steps advance while the records are read.
  useEffect(() => {
    if (state !== "generating") return
    const timer = window.setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 550)
    return () => window.clearInterval(timer)
  }, [state])

  const generate = async () => {
    setState("generating")
    setStep(0)
    setProblem("")
    const started = performance.now()
    try {
      const [nextDetail, nextDiagnosis] = await Promise.all([
        api<MonthDetail>(`/intelligence/outlook/month?month=${month}&metric=${metric}`),
        api<Diagnosis>(`/intelligence/outlook/diagnosis?month=${month}&metric=${metric}`),
      ])
      // Long enough to follow the steps, never longer than needed.
      const wait = Math.max(0, 2200 - (performance.now() - started))
      window.setTimeout(() => {
        setDetail(nextDetail)
        setDiagnosis(nextDiagnosis)
        setGeneratedAt(new Date().toLocaleString(locale(), { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }))
        setState("ready")
      }, wait)
    } catch (loadError) {
      setProblem((loadError as Error).message)
      setState("error")
    }
  }

  const highlights = useMemo(() => {
    if (!detail || !detail.items.length) return null
    const bySeller = new Map<string, { amount: number; deals: number }>()
    for (const item of detail.items) {
      if (!item.agent) continue
      const current = bySeller.get(item.agent) ?? { amount: 0, deals: 0 }
      bySeller.set(item.agent, { amount: current.amount + item.amount, deals: current.deals + 1 })
    }
    const topSeller = [...bySeller.entries()].sort((a, b) => b[1].amount - a[1].amount)[0]
    const biggest = [...detail.items].sort((a, b) => b.amount - a.amount)[0]
    return { topSeller, biggest }
  }, [detail])
  const actions = useMemo(() => {
    if (!diagnosis?.triggered) return KEEP_GOING
    return [...new Set(diagnosis.findings.slice(0, 3).flatMap((f) => SUGGESTIONS[f.code]))].slice(0, 5)
  }, [diagnosis])

  const verdictLook = verdict ? VERDICT_STYLE[verdict] : null
  const summary = recorded == null ? null
    : expected
      ? verdict === "BELOW"
        ? t("{month} recorded {v}, below what was expected ({e}; likely {low} – {high}).", { month: name, v: format(recorded), e: format(expected.value), low: format(expected.lower), high: format(expected.upper) })
        : verdict === "ABOVE"
          ? t("{month} recorded {v}, better than expected ({e}; likely {low} – {high}).", { month: name, v: format(recorded), e: format(expected.value), low: format(expected.lower), high: format(expected.upper) })
          : t("{month} recorded {v}, within what was expected ({e}; likely {low} – {high}).", { month: name, v: format(recorded), e: format(expected.value), low: format(expected.lower), high: format(expected.upper) })
      : t("{month} recorded {v}. There wasn't enough earlier history to expect a figure.", { month: name, v: format(recorded) })

  return (
    <section className="overflow-hidden rounded-2xl border border-ab-border bg-ab-card" aria-labelledby="month-report-title">
      <header className="flex flex-wrap items-center justify-between gap-3 bg-ab-card-2 px-5 py-4">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-ab-faint">{t("Month report")} · {t(label)}</p>
          <h2 id="month-report-title" className="text-xl font-extrabold">{name}</h2>
          {state === "ready" && <p className="text-xs text-ab-faint">{t("Generated {when} from the recorded data", { when: generatedAt })}</p>}
        </div>
        {over && state !== "generating" && (
          <button type="button" onClick={() => void generate()}
            className={`inline-flex min-h-10 items-center gap-2 rounded-xl px-4 text-sm font-bold transition ${state === "ready" ? "border border-ab-border-strong hover:bg-ab-hover" : "bg-ab-accent text-ab-ink hover:bg-ab-accent-hover"}`}>
            {state === "ready" ? <><RotateCcw className="h-4 w-4" /> {t("Generate again")}</> : <><Sparkles className="h-4 w-4" /> {t("Generate {month} report", { month: monthOnly })}</>}
          </button>
        )}
      </header>

      <div className="space-y-5 p-5">
        {!over ? (
          <p className="text-sm text-ab-muted">
            {expected
              ? t("{month} hasn't ended yet. It is expected to reach about {e} (likely {low} – {high}). The report can be generated once the month is over.", { month: name, e: format(expected.value), low: format(expected.lower), high: format(expected.upper) })
              : t("{month} hasn't ended yet. The report can be generated once the month is over.", { month: name })}
          </p>
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            {verdictLook && (
              <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-bold ${verdictLook.tone}`}>
                <verdictLook.icon className="h-4 w-4" aria-hidden /> {t(verdictLook.label)}
              </span>
            )}
            <span className="text-sm text-ab-muted">{t("Recorded")} <span className="font-bold text-ab-text">{format(recorded ?? 0)}</span></span>
            {expected && <span className="text-sm text-ab-muted">{t("Expected")} <span className="font-bold text-ab-text">{format(expected.value)}</span></span>}
          </div>
        )}

        {state === "idle" && over && (
          <p className="rounded-xl border border-dashed border-ab-border p-4 text-sm text-ab-muted">
            {t("Generate the report to see the month's timeline, how its figure was worked out, why it fell short (if it did) and what to try next.")}
          </p>
        )}

        {state === "generating" && (
          <ol className="space-y-2 rounded-xl bg-ab-card-2 p-4 text-sm" aria-live="polite">
            {STEPS.map((text, index) => (
              <li key={text} className={`flex items-center gap-2 transition ${index > step ? "opacity-30" : ""}`}>
                {index < step ? <CheckCircle2 className="h-4 w-4 text-ab-success" /> : index === step ? <LoaderCircle className="h-4 w-4 animate-spin text-ab-accent" /> : <span className="h-4 w-4 rounded-full border border-ab-border" />}
                {t(text)}
              </li>
            ))}
          </ol>
        )}

        {state === "error" && (
          <p role="alert" className="flex items-center gap-2 rounded-xl border border-ab-danger/40 bg-ab-danger/10 p-3 text-sm text-ab-danger">
            <CircleAlert className="h-4 w-4 shrink-0" /> {t("The report couldn't be generated: {error}", { error: problem })}
          </p>
        )}

        {state === "ready" && detail && diagnosis && (
          <article className="space-y-5">
            <Part n={1} icon={FileText} title={t("Summary")}>
              <p className="text-base leading-relaxed">{summary}</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                <div className="rounded-xl bg-ab-card-2 p-3"><p className="text-xs text-ab-faint">{t("Deals counted")}</p><p className="text-lg font-extrabold tabular-nums">{detail.count}</p></div>
                {highlights?.topSeller && (
                  <div className="rounded-xl bg-ab-card-2 p-3"><p className="text-xs text-ab-faint">{t("Top seller this month")}</p><p className="truncate text-lg font-extrabold">{highlights.topSeller[0]}</p></div>
                )}
                {highlights?.biggest && (
                  <div className="rounded-xl bg-ab-card-2 p-3"><p className="text-xs text-ab-faint">{t("Biggest deal")}</p><p className="text-lg font-extrabold tabular-nums">{peso(highlights.biggest.amount)}</p></div>
                )}
              </div>
              {diagnosis.change_pct != null && (
                <p className="mt-3 text-sm text-ab-muted">
                  {diagnosis.change_pct < 0
                    ? t("That is {pct}% lower than {month} ({v}).", { pct: Math.abs(Math.round(diagnosis.change_pct)), month: monthName(diagnosis.previous_month), v: format(diagnosis.previous) })
                    : t("That is {pct}% higher than {month} ({v}).", { pct: Math.round(diagnosis.change_pct), month: monthName(diagnosis.previous_month), v: format(diagnosis.previous) })}
                </p>
              )}
            </Part>

            <Part n={2} icon={CalendarDays} title={t("Timeline of the month")}>
              {detail.items.length === 0 ? (
                <p className="text-sm text-ab-muted">{t("Nothing was recorded this month, so the figure is {v}.", { v: format(0) })}</p>
              ) : (
                <ol className="relative ml-2 space-y-4 border-l-2 border-ab-border pl-5">
                  {[...detail.items].sort((a, b) => a.date.localeCompare(b.date)).map((item) => (
                    <li key={item.transaction_id} className="relative text-sm">
                      <span className={`absolute -left-[1.72rem] top-1 h-3 w-3 rounded-full border-2 border-ab-card ${item.type === "SOLD" ? "bg-ab-success" : "bg-ab-info"}`} aria-hidden />
                      <p className="text-xs font-semibold text-ab-faint">{transactionDate(item.date)} · {t(item.type === "SOLD" ? "Sale" : "Reservation")}</p>
                      <p className="font-bold">{item.property ?? t("Property")}</p>
                      <p className="text-xs text-ab-muted">
                        <span className="font-semibold tabular-nums text-ab-text">{peso(item.amount)}</span>
                        {item.agent && <> · <span className="text-ab-faint">{t("Seller")}</span> {item.agent}</>}
                        {item.client && <> · <span className="text-ab-faint">{t("Buyer")}</span> {item.client}</>}
                      </p>
                    </li>
                  ))}
                  <li className="relative text-sm">
                    <span className="absolute -left-[1.72rem] top-1 h-3 w-3 rounded-full border-2 border-ab-card bg-ab-accent" aria-hidden />
                    <p className="font-extrabold">{t("Total for {month}", { month: name })}: {format(detail.total)}</p>
                  </li>
                </ol>
              )}
            </Part>

            <Part n={3} icon={ListChecks} title={t("How the figure was worked out")}>
              <ol className="grid gap-3 md:grid-cols-3">
                <li className="rounded-xl border border-ab-border p-3 text-sm">
                  <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("What happened")}</p>
                  <p className="mt-1 text-lg font-extrabold tabular-nums">{format(detail.total)}</p>
                  <p className="text-ab-muted">{metric === "revenue" ? t("Every sale finished this month, added up.") : metric === "transactions" ? t("Every reservation and sale this month, except cancelled ones.") : metric === "sales" ? t("Every sale finished this month, counted.") : t("The commission on every sale finished this month.")}</p>
                </li>
                <li className="rounded-xl border border-ab-border p-3 text-sm">
                  <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("What was expected")}</p>
                  <p className="mt-1 text-lg font-extrabold tabular-nums">{expected ? format(expected.value) : "—"}</p>
                  <p className="text-ab-muted">{expected ? t("From the trend of the earlier months and how {month} usually goes. Likely {low} – {high}.", { month: monthOnly, low: format(expected.lower), high: format(expected.upper) }) : t("Not enough earlier months to expect a figure.")}</p>
                </li>
                <li className={`rounded-xl border p-3 text-sm ${verdictLook ? verdictLook.tone : "border-ab-border"}`}>
                  <p className="text-xs font-bold uppercase tracking-wide opacity-80">{t("Result")}</p>
                  <p className="mt-1 text-lg font-extrabold">{verdictLook ? t(verdictLook.label) : "—"}</p>
                  {expected && verdict && (
                    <p className="text-ab-text">
                      {verdict === "BELOW" ? t("{d} short of the low end.", { d: format(expected.lower - detail.total) })
                        : verdict === "ABOVE" ? t("{d} above the high end.", { d: format(detail.total - expected.upper) })
                          : t("Inside the likely range.")}
                    </p>
                  )}
                </li>
              </ol>
              <button type="button" onClick={() => setShowWorking((v) => !v)} aria-expanded={showWorking}
                className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-ab-accent hover:underline">
                <ChevronDown className={`h-3.5 w-3.5 transition ${showWorking ? "rotate-180" : ""}`} /> {t(showWorking ? "Hide the calculation" : "Show the calculation")}
              </button>
              {showWorking && <div className="mt-3">{working}</div>}
            </Part>

            {diagnosis.triggered && (
              <Part n={4} icon={SearchCheck} title={diagnosis.reasons.includes("BELOW_RANGE")
                ? t("Why {month} fell short", { month: name })
                : t("Why {month} was lower than {previous}", { month: name, previous: monthName(diagnosis.previous_month) })}>
                {diagnosis.revenue_change && diagnosis.before && diagnosis.now && diagnosis.revenue_change.total < 0 && (
                  <p className="mb-3 rounded-xl bg-ab-card-2 p-3 text-sm text-ab-muted">
                    {t("Sales revenue went from {before} to {now}.", { before: peso(diagnosis.before.revenue), now: peso(diagnosis.now.revenue) })}{" "}
                    {t("Of the {total} difference, {count} came from the number of deals and {price} from the average price per deal.", {
                      total: peso(Math.abs(diagnosis.revenue_change.total)),
                      count: `${diagnosis.revenue_change.from_sales_count < 0 ? "−" : "+"}${peso(Math.abs(diagnosis.revenue_change.from_sales_count))}`,
                      price: `${diagnosis.revenue_change.from_average_price < 0 ? "−" : "+"}${peso(Math.abs(diagnosis.revenue_change.from_average_price))}`,
                    })}
                  </p>
                )}
                <ol className="space-y-3">
                  {diagnosis.findings.slice(0, allCauses ? undefined : 3).map((f, index) => (
                    <li key={f.code} className="rounded-xl border border-ab-border p-3">
                      <p className="text-sm font-bold">{index + 1}. {findingTitle(f, monthOnly)}</p>
                      <div className="mt-1 space-y-1 text-sm text-ab-muted"><Evidence f={f} /></div>
                    </li>
                  ))}
                </ol>
                {diagnosis.findings.length > 3 && (
                  <button type="button" onClick={() => setAllCauses((v) => !v)} aria-expanded={allCauses}
                    className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-ab-accent hover:underline">
                    <ChevronDown className={`h-3.5 w-3.5 transition ${allCauses ? "rotate-180" : ""}`} />
                    {allCauses ? t("Show only the main causes") : t("Show {n} more cause(s)", { n: diagnosis.findings.length - 3 })}
                  </button>
                )}
              </Part>
            )}

            <Part n={diagnosis.triggered ? 5 : 4} icon={Lightbulb} title={t(diagnosis.triggered ? "What to try" : "Keep it going")}>
              <ul className="space-y-2">
                {actions.map((action) => (
                  <li key={action} className="flex items-start gap-2 rounded-xl bg-ab-accent-soft/60 p-3 text-sm">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ab-accent" aria-hidden /> {t(action)}
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-ab-faint">{t("Worked out from the recorded transactions, clients and listings. Suggestions are options to consider; the decision stays with management.")}</p>
            </Part>
          </article>
        )}
      </div>
    </section>
  )
}
