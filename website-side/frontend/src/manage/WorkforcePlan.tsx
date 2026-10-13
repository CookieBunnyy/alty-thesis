// Workforce demand vs capacity: expected deals next month ÷ deals one agent
// handles = agents needed, against active agents, per branch, with the
// recommendations to reallocate or recruit (/intelligence/workforce-plan).
import { useCallback, useState } from "react"
import { ArrowRightLeft, Megaphone, Scale, UserPlus, Users } from "lucide-react"
import { Link } from "@/components/Link"
import { DataTable, LoadState, Section, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"
import { locale, t } from "./i18n"

type Demand = { month: string; value: number; high: number; method: "forecast" | "recent_average" }
type PlanRow = {
  branch_id: number | null; name: string; active_agents: number; demand: Demand
  agents_needed: number; agents_needed_high: number; gap: number; utilization: number | null; status: "SHORT" | "OVER" | "BALANCED"
}
type Recommendation = { kind: "ASSIGN" | "REALLOCATE" | "RECRUIT" | "LEADS" | "REBALANCE"; detail: string; rule: string; agents: number; from_branch?: string; to_branch?: string | null }
type Plan = {
  capacity: { per_agent: number; overridden: boolean; observed: { value: number; agent_months: number; basis: string; median?: number; busiest?: number } }
  company: PlanRow; branches: PlanRow[]
  overloaded_agents: { agent_id: string; full_name: string; branch: string | null; open_reservations: number }[]
  recommendations: Recommendation[]
}

const ICONS = { ASSIGN: Users, REALLOCATE: ArrowRightLeft, RECRUIT: UserPlus, LEADS: Megaphone, REBALANCE: Scale }
const STATUS = {
  SHORT: { label: "Short of agents", tone: "bg-ab-danger/10 text-ab-danger" },
  OVER: { label: "More than needed", tone: "bg-ab-warning/15 text-ab-text" },
  BALANCED: { label: "Balanced", tone: "bg-ab-accent-soft text-ab-accent" },
} as const
const monthName = (key: string) => new Date(`${key}-01T00:00:00`).toLocaleDateString(locale(), { month: "long", year: "numeric" })
const one = (v: number) => v.toLocaleString(locale(), { maximumFractionDigits: 1 })

/** The recommendation as a sentence (built here so it follows the chosen language). */
function sentence(r: Recommendation, plan: Plan): string {
  if (r.kind === "ASSIGN") return t("Assign {n} agent(s) without a branch to {to}.", { n: r.agents, to: r.to_branch ?? "" })
  if (r.kind === "REALLOCATE") return t("Move {n} agent(s) from {from} to {to}.", { n: r.agents, from: r.from_branch ?? "", to: r.to_branch ?? "" })
  if (r.kind === "RECRUIT") return r.to_branch ? t("Recruit {n} agent(s) for {to}.", { n: r.agents, to: r.to_branch }) : t("Recruit {n} agent(s).", { n: r.agents })
  if (r.kind === "LEADS") return t("Agents have more capacity than the expected deals: focus on lead generation and marketing before hiring.")
  return t("Give new clients to other agents until these agents' open reservations go down: {names}.", { names: plan.overloaded_agents.map((a) => a.full_name).join(", ") })
}

export function WorkforcePlan() {
  const { api } = useStaffAuth()
  const [capacity, setCapacity] = useState("")
  const [applied, setApplied] = useState("")
  const load = useCallback(() => api<Plan>(`/intelligence/workforce-plan${applied ? `?capacity=${applied}` : ""}`), [api, applied])
  const { data, error, loading, reload } = useApiData(load, `workforce-plan:${applied}`)
  const company = data?.company

  const columns: Column<PlanRow>[] = [
    { key: "name", label: "Branch", sort: (r) => r.name, render: (r) => <span className="font-semibold">{r.branch_id === 0 ? t("No branch") : r.name}</span> },
    { key: "demand", label: "Expected deals", align: "right", sort: (r) => r.demand.value, render: (r) => one(r.demand.value) },
    { key: "needed", label: "Agents needed", align: "right", sort: (r) => r.agents_needed, render: (r) => r.agents_needed },
    { key: "active", label: "Active agents", align: "right", sort: (r) => r.active_agents, render: (r) => r.active_agents },
    { key: "gap", label: "Gap", align: "right", sort: (r) => r.gap, render: (r) => <span className={`font-semibold tabular-nums ${r.gap > 0 ? "text-ab-danger" : ""}`}>{r.gap > 0 ? `+${r.gap}` : r.gap}</span> },
    { key: "use", label: "Utilization", align: "right", sort: (r) => r.utilization ?? -1, render: (r) => (r.utilization != null ? `${r.utilization}%` : "—"), hideOnPhone: true },
    { key: "status", label: "Status", sort: (r) => r.status, render: (r) => <span className={`whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS[r.status].tone}`}>{t(STATUS[r.status].label)}</span> },
  ]

  return (
    <Section title={t("Workforce demand vs capacity")}>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && company && (
        <div className="space-y-4">
          <div className="rounded-xl bg-ab-card-2 p-4 text-sm leading-relaxed">
            <p>
              {t("For {month} we expect about {d} deal(s) (reservations and sales).", { month: monthName(company.demand.month), d: one(company.demand.value) })}{" "}
              {t("One agent handles about {c} deal(s) in a busy month, so the company needs {n} agent(s).", { c: one(data.capacity.per_agent), n: company.agents_needed })}{" "}
              {t("You have {a} active agent(s):", { a: company.active_agents })}{" "}
              <span className={`font-bold ${company.gap > 0 ? "text-ab-danger" : company.gap < 0 ? "text-ab-text" : "text-ab-accent"}`}>
                {company.gap > 0 ? t("{n} short.", { n: company.gap }) : company.gap < 0 ? t("{n} more than needed.", { n: -company.gap }) : t("exactly enough.")}
              </span>
            </p>
            <p className="mt-2 text-xs text-ab-muted">
              {company.demand.method === "forecast"
                ? t("Expected deals come from the Business Outlook forecast (likely up to {h}).", { h: one(company.demand.high) })
                : t("Not enough history for a forecast: expected deals are the average of the last 3 months.")}{" "}
              {data.capacity.overridden
                ? t("Deals per agent set by you (measured: {v}).", { v: one(data.capacity.observed.value) })
                : data.capacity.observed.basis === "observed"
                  ? t("Deals per agent is measured: in 3 of 4 months, an agent with work handled {v} deal(s) or fewer (last 12 months, {n} agent-months).", { v: one(data.capacity.observed.value), n: data.capacity.observed.agent_months })
                  : t("No history yet: 1 deal per agent is assumed until there is.")}
            </p>
            <form className="mt-3 flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); setApplied(capacity) }}>
              <label className="text-xs font-semibold text-ab-muted">{t("Deals one agent can handle in a month")}
                <input type="number" min={0.5} max={100} step={0.5} value={capacity} placeholder={one(data.capacity.observed.value)} onChange={(e) => setCapacity(e.target.value)}
                  className="mt-1 block w-32 rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none" />
              </label>
              <button type="submit" className="min-h-9 rounded-xl border border-ab-border-strong px-3 text-sm font-semibold hover:bg-ab-hover">{t("Recalculate")}</button>
              {applied && <button type="button" onClick={() => { setCapacity(""); setApplied("") }} className="min-h-9 px-2 text-sm font-semibold text-ab-accent hover:underline">{t("Use the measured value")}</button>}
            </form>
          </div>

          {data.branches.length > 0 ? (
            <DataTable exportTitle="Workforce demand vs capacity" rows={data.branches} columns={columns} rowKey={(r) => String(r.branch_id)} empty="No branches." initialSort={{ key: "gap", dir: "desc" }} />
          ) : (
            <p className="text-sm text-ab-muted">
              {t("Add branches and assign agents to see this per branch.")} <Link to="/manage/branches" className="font-semibold text-ab-accent hover:underline">{t("Open Branches")}</Link>
            </p>
          )}

          <div>
            <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("Recommendations")}</p>
            {data.recommendations.length === 0 ? (
              <p className="mt-2 text-sm text-ab-muted">{t("No changes needed: every branch has about the agents its expected deals need.")}</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {data.recommendations.map((r, index) => {
                  const Icon = ICONS[r.kind]
                  return (
                    <li key={index} className="flex gap-3 rounded-xl border border-ab-border p-3 text-sm">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ab-accent-soft text-ab-accent"><Icon className="h-4 w-4" aria-hidden /></span>
                      <span className="min-w-0">
                        <span className="block break-words font-semibold">{sentence(r, data)}</span>
                        <span className="block text-xs text-ab-faint">{t("Rule: {rule}", { rule: t(r.rule) })}</span>
                        {r.kind === "RECRUIT" && <Link to="/manage/recruitment" className="mt-1 inline-block text-xs font-semibold text-ab-accent hover:underline">{t("Open Recruitment")}</Link>}
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}
            <p className="mt-2 text-xs text-ab-faint">{t("Suggestions from recorded data and the rules shown; the decision stays with management.")}</p>
          </div>
        </div>
      )}
    </Section>
  )
}
