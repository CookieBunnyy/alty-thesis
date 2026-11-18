// The top 3 sellers by sales value (second interview: ranked by amount,
// monthly and quarterly), as a podium on the Sellers page. Hovering a seller
// shows the figures behind the place; clicking opens the seller's profile.
import { useCallback, useState } from "react"
import { Crown } from "lucide-react"
import { Link } from "@/components/Link"
import { AgentAvatar } from "./avatars"
import { peso, pesoShort } from "./format"
import { LoadState, Section } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"
import { t } from "./i18n"

type Seller = { name: string; agent_id?: string | null; team?: string | null; sales: number; revenue: number; commission?: number }
type Team = { name: string; sales: number; revenue: number }
type Dashboard = { year: number; sales: { top_sellers: Seller[]; top_sellers_month?: Seller[]; top_sellers_quarter?: Seller[]; by_team: Team[] } }
type Period = "month" | "quarter" | "year"

const PERIODS: { key: Period; label: string; empty: string }[] = [
  { key: "month", label: "This month", empty: "No completed sales yet this month." },
  { key: "quarter", label: "This quarter", empty: "No completed sales yet this quarter." },
  { key: "year", label: "This year", empty: "No completed sales yet this year." },
]
// Podium order on screen: 2nd, 1st, 3rd.
const PLACES = [
  { rank: 2, label: "2nd", height: "h-32", bar: "from-sky-200/80 to-sky-50 dark:from-sky-500/30 dark:to-sky-500/5", ring: "ring-sky-300" },
  { rank: 1, label: "1st", height: "h-44", bar: "from-violet-300/80 to-violet-50 dark:from-violet-500/40 dark:to-violet-500/5", ring: "ring-violet-400" },
  { rank: 3, label: "3rd", height: "h-24", bar: "from-pink-200/80 to-pink-50 dark:from-pink-500/30 dark:to-pink-500/5", ring: "ring-pink-300" },
] as const

/** The figures behind a place, shown on hover / keyboard focus. */
function Kpis({ seller, rank, periodLabel }: { seller: Seller; rank: number; periodLabel: string }) {
  // The side places open toward the middle, so the box stays on screen on phones.
  const align = rank === 2 ? "left-0" : rank === 3 ? "right-0" : "left-1/2 -translate-x-1/2"
  const rows: [string, string][] = [
    ["Sales value", peso(seller.revenue)],
    ["Sales closed", String(seller.sales)],
    ["Average per sale", seller.sales ? peso(seller.revenue / seller.sales) : "—"],
    ...(seller.commission ? [["Commission recorded", peso(seller.commission)] as [string, string]] : []),
    ...(seller.team ? [["Team / cluster", seller.team] as [string, string]] : []),
  ]
  return (
    <span role="tooltip"
      className={`pointer-events-none absolute bottom-full ${align} z-20 mb-2 hidden w-60 rounded-xl border border-ab-border bg-ab-card p-3 text-left text-xs shadow-xl group-hover:block group-focus-visible:block`}>
      <span className="block font-bold text-ab-text">{t("Why {name} is #{rank}", { name: seller.name, rank })}</span>
      <span className="mb-2 block text-ab-faint">{t("Ranked by total sales value, {period}", { period: t(periodLabel).toLowerCase() })}</span>
      {rows.map(([label, value]) => (
        <span key={label} className="flex justify-between gap-3 border-t border-ab-border/60 py-1">
          <span className="text-ab-muted">{t(label)}</span><span className="font-semibold tabular-nums text-ab-text">{value}</span>
        </span>
      ))}
      <span className="mt-1 block font-semibold text-ab-accent">{t("Click to open the seller's profile")}</span>
    </span>
  )
}

function Podium({ sellers, photos, periodLabel, empty }: { sellers: Seller[]; photos: Record<string, number | null | undefined>; periodLabel: string; empty: string }) {
  if (!sellers.length) return <p className="py-10 text-center text-sm italic text-ab-faint">{t(empty)}</p>
  return (
    <ol className="grid grid-cols-3 items-end gap-2 sm:gap-4" aria-label={t("Top 3 sellers")}>
      {PLACES.map((place) => {
        const seller = sellers[place.rank - 1]
        if (!seller) return <li key={place.rank} aria-hidden className="min-w-0" />
        const body = (
          <>
            <span className="relative mb-2 flex flex-col items-center">
              {place.rank === 1 && <Crown className="mb-1 h-5 w-5 text-amber-500" aria-hidden />}
              <span className={`rounded-full ring-4 ${place.ring}`}>
                <AgentAvatar agentId={seller.agent_id ?? seller.name} name={seller.name} version={seller.agent_id ? photos[seller.agent_id] : null} size="md" />
              </span>
              <span className="mt-2 max-w-full truncate px-1 text-sm font-bold text-ab-text">{seller.name}</span>
            </span>
            <span className={`flex w-full flex-col items-center justify-center gap-2 rounded-t-2xl bg-gradient-to-b ${place.bar} ${place.height} transition group-hover:brightness-105`}>
              <span className="text-2xl font-extrabold text-ab-text sm:text-3xl">{t(place.label)}</span>
              <span className="rounded-full bg-ab-card px-2.5 py-0.5 text-xs font-bold tabular-nums text-ab-text shadow-sm">{pesoShort(seller.revenue)}</span>
            </span>
          </>
        )
        return (
          <li key={place.rank} className="min-w-0">
            {seller.agent_id ? (
              <Link to={`/manage/agents?id=${encodeURIComponent(seller.agent_id)}`}
                aria-label={t("{place}: {name}, {value} from {n} sale(s). Open profile", { place: t(place.label), name: seller.name, value: peso(seller.revenue), n: seller.sales })}
                className="group relative flex flex-col items-center rounded-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-ab-accent">
                <Kpis seller={seller} rank={place.rank} periodLabel={periodLabel} />
                {body}
              </Link>
            ) : <div className="group relative flex flex-col items-center"><Kpis seller={seller} rank={place.rank} periodLabel={periodLabel} />{body}</div>}
          </li>
        )
      })}
    </ol>
  )
}

export function TopSellers({ photos = {} }: { photos?: Record<string, number | null | undefined> }) {
  const { api } = useStaffAuth()
  const load = useCallback(() => api<Dashboard>("/reports/dashboard"), [api])
  const { data, error, loading, reload } = useApiData(load, "reports-dashboard")
  const [period, setPeriod] = useState<Period>("month")
  if (!data) return <LoadState loading={loading} error={error} onRetry={reload} />
  const current = PERIODS.find((p) => p.key === period)!
  const sellers = period === "month" ? data.sales.top_sellers_month ?? [] : period === "quarter" ? data.sales.top_sellers_quarter ?? [] : data.sales.top_sellers
  const mostTeam = Math.max(1, ...data.sales.by_team.map((team) => team.revenue))
  return (
    <div className="grid gap-5 lg:grid-cols-3" data-tour="top-sellers">
      <Section title={t("Top 3 performing sellers")} className="lg:col-span-2"
        action={<Link to="/manage/reports" className="text-xs font-semibold text-ab-accent hover:underline">{t("Full sales report")}</Link>}>
        <div role="tablist" aria-label={t("Period")} className="mb-5 flex w-fit rounded-xl border border-ab-border bg-ab-card-2 p-1">
          {PERIODS.map((p) => (
            <button key={p.key} type="button" role="tab" aria-selected={period === p.key} onClick={() => setPeriod(p.key)}
              className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${period === p.key ? "bg-ab-accent text-ab-ink" : "text-ab-muted hover:text-ab-text"}`}>{t(p.label)}</button>
          ))}
        </div>
        <div className="mx-auto max-w-xl pt-28 sm:pt-24">
          <Podium sellers={sellers.slice(0, 3)} photos={photos} periodLabel={current.label} empty={current.empty} />
        </div>
        <p className="mt-3 text-center text-xs text-ab-faint">{t("Ranked by total sales value. Point at a seller to see why; click to open their profile.")}</p>
      </Section>
      <Section title={t("Teams / clusters in {year}", { year: data.year })}>
        {data.sales.by_team.length === 0 ? <p className="py-6 text-center text-sm italic text-ab-faint">{t("No completed sales yet this year.")}</p> : (
          <ol className="space-y-3">
            {data.sales.by_team.map((team, index) => (
              <li key={team.name} className="text-sm">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="truncate font-semibold"><span className="mr-1.5 text-xs text-ab-faint">{index + 1}</span>{team.name}</span>
                  <span className="shrink-0 tabular-nums"><span className="font-bold">{pesoShort(team.revenue)}</span> <span className="text-xs text-ab-faint">{t("{n} sale(s)", { n: team.sales })}</span></span>
                </div>
                <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-ab-card-2">
                  <span className="block h-full rounded-full bg-ab-accent" style={{ width: `${(team.revenue / mostTeam) * 100}%` }} />
                </span>
              </li>
            ))}
          </ol>
        )}
      </Section>
    </div>
  )
}
