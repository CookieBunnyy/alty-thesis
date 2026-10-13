// Business Outlook decision support: when a month falls below its likely
// range or below the month before, the backend traces the drop to its causes
// (/intelligence/outlook/diagnosis). This panel shows each cause with the
// evidence behind it, then suggestions management can choose from.
import { useCallback } from "react"
import { Lightbulb, SearchCheck } from "lucide-react"
import { categoryLabel } from "@/lib/categories"
import { peso } from "./format"
import { locale, t } from "./i18n"
import { LoadState, Section } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"

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
  month: string
  previous_month: string
  actual: number
  previous: number
  change_pct: number | null
  expected: { value: number; lower: number; upper: number } | null
  reasons: ("BELOW_RANGE" | "BELOW_PREVIOUS")[]
  triggered: boolean
  now?: Stats
  before?: Stats
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

function title(f: Finding, monthOnly: string): string {
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
        <>
          <p>{t("Most common reasons:")}</p>
          <ul className="list-disc space-y-0.5 pl-5">
            {f.params.reasons.map((r) => <li key={r.reason} className="break-words">{r.reason === "No reason recorded" ? t(r.reason) : r.reason} <span className="text-ab-faint">× {r.count}</span></li>)}
          </ul>
        </>
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
              <span className="tabular-nums">{peso(a.now)} <span className="text-ab-faint">({t("was {v}", { v: peso(a.before) })} · {t("{now} of {before} sale(s)", { now: a.sales_now, before: a.sales_before })})</span></span>
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

export function OutlookDiagnosis({ month, metric, monthName, format }: {
  month: string
  metric: "revenue" | "transactions" | "sales" | "commission"
  monthName: (key: string) => string
  format: (value: number) => string
}) {
  const { api } = useStaffAuth()
  const load = useCallback(() => api<Diagnosis>(`/intelligence/outlook/diagnosis?month=${month}&metric=${metric}`), [api, month, metric])
  const { data, error, loading, reload } = useApiData(load, `outlook-diagnosis:${metric}:${month}`)
  if (!data) return loading || error ? <LoadState loading={loading} error={error} onRetry={reload} /> : null
  if (!data.triggered) return null
  const monthOnly = new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)) - 1, 1).toLocaleDateString(locale(), { month: "long" })
  const change = data.revenue_change
  const before = data.before

  return (
    <Section title={t("Why {month} fell short, and what to try", { month: monthName(month) })}>
      <div className="flex flex-wrap gap-2">
        {data.reasons.includes("BELOW_RANGE") && data.expected && (
          <span className="rounded-full bg-ab-danger/10 px-2.5 py-1 text-xs font-semibold text-ab-danger">
            {t("Below the likely range ({low} – {high})", { low: format(data.expected.lower), high: format(data.expected.upper) })}
          </span>
        )}
        {data.reasons.includes("BELOW_PREVIOUS") && (
          <span className="rounded-full bg-ab-danger/10 px-2.5 py-1 text-xs font-semibold text-ab-danger">
            {data.change_pct != null
              ? t("{pct}% lower than {month} ({v})", { pct: Math.abs(Math.round(data.change_pct)), month: monthName(data.previous_month), v: format(data.previous) })
              : t("Lower than {month} ({v})", { month: monthName(data.previous_month), v: format(data.previous) })}
          </span>
        )}
      </div>

      {change && before && data.now && change.total < 0 && (
        <p className="mt-3 break-words rounded-xl bg-ab-card-2 p-3 text-sm text-ab-muted">
          {t("Sales revenue went from {before} to {now}.", { before: peso(before.revenue), now: peso(data.now.revenue) })}{" "}
          {t("Of the {total} difference, {count} came from the number of deals and {price} from the average price per deal.", {
            total: peso(Math.abs(change.total)),
            count: `${change.from_sales_count < 0 ? "−" : "+"}${peso(Math.abs(change.from_sales_count))}`,
            price: `${change.from_average_price < 0 ? "−" : "+"}${peso(Math.abs(change.from_average_price))}`,
          })}
        </p>
      )}

      <p className="mt-4 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-ab-faint">
        <SearchCheck className="h-4 w-4" aria-hidden /> {t("What the records show (biggest cause first)")}
      </p>
      <ol className="mt-2 grid gap-3 md:grid-cols-2">
        {data.findings.map((f, index) => (
          <li key={f.code} className="min-w-0 rounded-xl border border-ab-border bg-ab-card-2 p-3">
            <p className="text-sm font-bold break-words">{index + 1}. {title(f, monthOnly)}</p>
            <div className="mt-1.5 space-y-1 text-sm text-ab-muted"><Evidence f={f} /></div>
            <p className="mt-3 flex items-center gap-1.5 text-xs font-semibold text-ab-accent">
              <Lightbulb className="h-3.5 w-3.5" aria-hidden /> {t("What to try")}
            </p>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
              {SUGGESTIONS[f.code].map((s) => <li key={s} className="break-words">{t(s)}</li>)}
            </ul>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-xs text-ab-faint">
        {t("Findings are computed from recorded transactions, clients and listings. Suggestions are options to consider, not automatic actions: the decision stays with management.")}
      </p>
    </Section>
  )
}
