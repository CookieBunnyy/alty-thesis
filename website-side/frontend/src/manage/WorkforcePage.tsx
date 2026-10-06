import { useCallback, useMemo } from "react"
import { Link } from "@/components/Link"
import { BarList } from "./charts"
import { dateTime } from "./format"
import { InsightPanel, type Insight } from "./Insights"
import { Badge, DataTable, LoadState, PageHeader, Section, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"

type Workforce = {
  generated_at: string
  users: { total: number; active: number; by_role: { role: string; users: number; active: number; logged_in_30d: number }[] }
  agents: { total: number; active: number; rows: { agent_id: string; full_name: string; status: string; assigned_clients: number; transactions: number; active_reservations: number; sales_last_90_days: number }[] }
}
type AgentRow = Workforce["agents"]["rows"][number]

/** Staff accounts by role and agent workload (management roles). Workload
 *  insights come from ALTY's agent rules. */
export function WorkforcePage() {
  const { api } = useStaffAuth()
  const load = useCallback(() => Promise.all([api<Workforce>("/analytics/workforce"), api<{ items: Insight[] }>("/intelligence/insights")]), [api])
  const { data, error, loading, reload } = useApiData(load)
  const [workforce, feed] = data ?? [null, null]
  const agentInsights = useMemo(() => (feed?.items ?? []).filter((i) => i.scope === "agent"), [feed])
  const rows = workforce?.agents.rows ?? []
  const openReservations = rows.reduce((s, a) => s + a.active_reservations, 0)
  const activeAgents = rows.filter((a) => a.status.toUpperCase() === "ACTIVE")

  const columns: Column<AgentRow>[] = [
    { key: "name", label: "Agent", sort: (a) => a.full_name, render: (a) => <Link to={`/manage/agents?id=${a.agent_id}`} className="font-semibold hover:underline">{a.full_name}</Link> },
    { key: "status", label: "Status", sort: (a) => a.status, render: (a) => <Badge value={a.status} /> },
    { key: "clients", label: "Assigned clients", align: "right", sort: (a) => a.assigned_clients, render: (a) => a.assigned_clients },
    { key: "open", label: "Open reservations", align: "right", sort: (a) => a.active_reservations, render: (a) => a.active_reservations },
    { key: "transactions", label: "Transactions", align: "right", sort: (a) => a.transactions, render: (a) => a.transactions, hideOnPhone: true },
    { key: "sales90", label: "Sales (90 days)", align: "right", sort: (a) => a.sales_last_90_days, render: (a) => a.sales_last_90_days },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader title="Workforce" subtitle="Staff accounts by role and how client work is spread across agents, from the records in ALTY." />
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {workforce && (
        <>
          <Tiles items={[
            { label: "Staff accounts", value: workforce.users.total, detail: `${workforce.users.active} active` },
            { label: "Agents", value: workforce.agents.total, detail: `${workforce.agents.active} active` },
            { label: "Open reservations", value: openReservations, detail: activeAgents.length ? `${(openReservations / activeAgents.length).toFixed(1)} per active agent` : undefined },
            { label: "Sales (90 days)", value: rows.reduce((s, a) => s + a.sales_last_90_days, 0), detail: "Completed, recorded in ALTY" },
          ]} />
          <div className="grid gap-5 lg:grid-cols-2">
            <Section title="Open reservations per agent">
              <BarList empty="No open reservations right now." format={(v) => String(v)}
                rows={[...rows].sort((a, b) => b.active_reservations - a.active_reservations).filter((a) => a.active_reservations > 0)
                  .map((a) => ({ name: a.full_name, value: a.active_reservations, note: `${a.assigned_clients} assigned client(s)` }))} />
            </Section>
            <Section title="Staff by role">
              <ul className="space-y-2 text-sm">
                {workforce.users.by_role.map((r) => (
                  <li key={r.role} className="flex items-center justify-between gap-3 rounded-xl border border-ab-border px-3 py-2">
                    <span className="font-semibold">{r.role}</span>
                    <span className="text-xs text-ab-muted">{r.users} account(s) · {r.active} active · {r.logged_in_30d} signed in (30 days)</span>
                  </li>
                ))}
              </ul>
            </Section>
          </div>
          <InsightPanel title="ALTY Workforce Insights" insights={agentInsights} empty="No agent needs attention right now — workload and performance are within the normal range." />
          <div>
            <h2 className="mb-2 font-bold">Agent workload</h2>
            <DataTable rows={rows} columns={columns} rowKey={(a) => a.agent_id} empty="No agents." initialSort={{ key: "open", dir: "desc" }} />
            <p className="mt-2 text-xs text-ab-faint">Generated {dateTime(workforce.generated_at)}. Counts are from records in ALTY (transactions from documents and sync).</p>
          </div>
        </>
      )}
    </div>
  )
}
