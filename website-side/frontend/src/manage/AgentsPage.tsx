import { useCallback, useMemo, useState } from "react"
import { ExternalLink, Phone, Star } from "lucide-react"
import { Link } from "@/components/Link"
import { contains, date, dateTime, isManagement, peso, pesoShort, statusLabel, text } from "./format"
import { SubjectInsights } from "./Insights"
import { SyncButton } from "./SyncButton"
import { Badge, DataTable, Drawer, Facts, LoadState, PageHeader, SearchBox, Section, Select, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData, useOpenRecord } from "./useApiData"

type Agent = {
  agent_id: string; full_name: string; phone_number: string | null; agent_location: string | null
  latitude: string | null; longitude: string | null; star_rating: string | null
  assignments_count: number; transactions_count: number; completed_sales: number
  total_sales: string | null; total_commission: string | null; performance_score: string | null
  client_rating: number | null; review_count: number; status: string; sync_status: string
  last_synced_at: string | null; created_at: string | null; updated_at: string | null
}
type Activity = {
  recorded: { clients: number; transactions: number; active_reservations: number; completed_sales: number; sales_value: number; properties: number }
  clients: { client_id: string; full_name: string; status: string; property_id: number | null }[]
  transactions: { transaction_id: string; client_name: string | null; property_id: number; property_title: string | null; transaction_type: string; transaction_date: string; amount: number; status: string }[]
}
type Reviews = {
  client_rating: number | null; review_count: number; distribution: Record<string, number>
  reviews: { id: number; rating: number; review: string | null; reviewer: string; property_title: string | null; created_at: string }[]
}

function Stars({ value }: { value: number | null }) {
  if (value == null) return <span className="text-ab-faint">No reviews</span>
  return (
    <span className="inline-flex items-center gap-1 tabular-nums">
      <Star className="h-3.5 w-3.5 fill-ab-warning text-ab-warning" aria-hidden /> {value.toFixed(1)}
    </span>
  )
}

export function AgentsPage() {
  const { api, user } = useStaffAuth()
  const { id, open, close } = useOpenRecord()
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("")
  const load = useCallback(() => api<Agent[]>("/agents"), [api])
  const { data, error, loading, reload } = useApiData(load)
  const agents = useMemo(() => data ?? [], [data])
  const shown = useMemo(
    () => agents.filter((a) => (!status || a.status === status) && contains([a.full_name, a.agent_id, a.agent_location, a.phone_number], search)),
    [agents, status, search],
  )
  const selected = id ? agents.find((a) => a.agent_id === id) ?? null : null
  const active = agents.filter((a) => a.status === "ACTIVE").length
  const reviewed = agents.filter((a) => a.client_rating != null)

  const columns: Column<Agent>[] = [
    {
      key: "name", label: "Agent", sort: (a) => a.full_name,
      render: (a) => (
        <span className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ab-accent-soft text-xs font-extrabold text-ab-accent">
            {a.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
          </span>
          <span className="min-w-0">
            <span className="block truncate font-semibold">{a.full_name}</span>
            <span className="block truncate text-xs text-ab-faint">{a.agent_id} · {text(a.agent_location)}</span>
          </span>
        </span>
      ),
    },
    { key: "status", label: "Status", sort: (a) => a.status, render: (a) => <Badge value={a.status} /> },
    { key: "client", label: "Client rating", sort: (a) => a.client_rating ?? -1, render: (a) => <span>{<Stars value={a.client_rating} />}{a.review_count ? <span className="ml-1 text-xs text-ab-faint">({a.review_count})</span> : null}</span> },
    { key: "transactions", label: "Transactions", align: "right", sort: (a) => a.transactions_count, render: (a) => a.transactions_count, hideOnPhone: true },
    { key: "sales", label: "Completed sales", align: "right", sort: (a) => a.completed_sales, render: (a) => a.completed_sales },
    { key: "value", label: "Sales value", align: "right", sort: (a) => Number(a.total_sales ?? 0), render: (a) => pesoShort(a.total_sales) },
    { key: "performance", label: "Performance", align: "right", sort: (a) => Number(a.performance_score ?? -1), render: (a) => (a.performance_score ? `${Number(a.performance_score).toFixed(1)}%` : "—"), hideOnPhone: true },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Agents"
        subtitle="Agent records from Supabase, with client reviews and the clients, properties and transactions recorded for each agent."
        actions={isManagement(user?.role) && <SyncButton path="/agents/sync" what="Agents" onDone={reload} />}
      />
      {data && (
        <Tiles items={[
          { label: "Agents", value: agents.length, onClick: () => setStatus(""), active: !status },
          { label: "Active", value: active, onClick: () => setStatus(status === "ACTIVE" ? "" : "ACTIVE"), active: status === "ACTIVE" },
          { label: "Completed sales", value: agents.reduce((s, a) => s + a.completed_sales, 0), detail: "From agent records" },
          { label: "Sales value", value: pesoShort(agents.reduce((s, a) => s + Number(a.total_sales ?? 0), 0)), detail: "From agent records" },
          { label: "Client-reviewed agents", value: reviewed.length, detail: reviewed.length ? `of ${agents.length}` : "No client reviews yet" },
        ]} />
      )}
      <div className="flex flex-wrap gap-2 sm:flex-nowrap">
        <div className="w-full sm:w-auto sm:flex-1"><SearchBox value={search} onChange={setSearch} placeholder="Search name, agent ID, location or phone" /></div>
        <Select label="Status" value={status} onChange={setStatus} options={[{ value: "", label: "All statuses" }, ...[...new Set(agents.map((a) => a.status))].map((s) => ({ value: s, label: statusLabel(s) }))]} />
      </div>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <>
          <p className="text-xs text-ab-faint">{shown.length} of {agents.length} agents</p>
          <DataTable rows={shown} columns={columns} rowKey={(a) => a.agent_id} onOpen={(a) => open(a.agent_id)} empty="No agents match these filters." initialSort={{ key: "value", dir: "desc" }} />
        </>
      )}
      {selected && <AgentDrawer agent={selected} onClose={close} />}
    </div>
  )
}

function AgentDrawer({ agent, onClose }: { agent: Agent; onClose: () => void }) {
  const { api, user } = useStaffAuth()
  const loadActivity = useCallback(() => api<Activity>(`/agents/${encodeURIComponent(agent.agent_id)}/activity`), [api, agent.agent_id])
  const loadReviews = useCallback(() => api<Reviews>(`/agents/${encodeURIComponent(agent.agent_id)}/reviews`), [api, agent.agent_id])
  const activity = useApiData(loadActivity)
  const reviews = useApiData(loadReviews)
  const phone = agent.phone_number?.replace(/[^\d+]/g, "")
  const hasPoint = agent.latitude != null && agent.longitude != null
  const maxBar = Math.max(1, ...Object.values(reviews.data?.distribution ?? {}))

  return (
    <Drawer
      title={agent.full_name}
      subtitle={<span className="flex flex-wrap items-center gap-2"><Badge value={agent.status} /> {agent.agent_id} · {text(agent.agent_location)}</span>}
      onClose={onClose}
      footer={phone && (
        <a href={`tel:${phone}`} className="inline-flex min-h-10 items-center gap-1.5 rounded-xl bg-ab-accent px-3.5 text-sm font-semibold text-ab-ink hover:bg-ab-accent-hover">
          <Phone className="h-4 w-4" /> Call {agent.phone_number}
        </a>
      )}
    >
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {([
          ["Assignments", agent.assignments_count],
          ["Transactions", agent.transactions_count],
          ["Completed sales", agent.completed_sales],
          ["Performance", agent.performance_score ? `${Number(agent.performance_score).toFixed(1)}%` : "—"],
          ["Sales value", peso(agent.total_sales)],
          ["Commission", peso(agent.total_commission)],
          ["System rating", agent.star_rating ? `${Number(agent.star_rating).toFixed(1)} ★` : "—"],
          ["Client rating", agent.client_rating != null ? `${agent.client_rating.toFixed(1)} ★ (${agent.review_count})` : "No reviews"],
        ] as const).map(([label, value]) => (
          <div key={label} className="rounded-xl border border-ab-border bg-ab-card p-3">
            <p className="text-[11px] text-ab-faint">{label}</p>
            <p className="mt-0.5 font-bold tabular-nums">{value}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-ab-faint">Assignments, sales value, commission, performance and system rating are the figures stored on the agent record (synced from Supabase). Client rating comes only from verified client reviews.</p>

      {isManagement(user?.role) && (
        <SubjectInsights path={`/intelligence/agents/${encodeURIComponent(agent.agent_id)}`} empty="Nothing needs attention for this agent right now." />
      )}

      <Section title="Contact & location">
        <Facts items={[
          ["Phone number", agent.phone_number],
          ["Location", agent.agent_location],
          ["Coordinates", hasPoint ? (
            <a href={`https://www.openstreetmap.org/?mlat=${agent.latitude}&mlon=${agent.longitude}#map=15/${agent.latitude}/${agent.longitude}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:underline">
              {Number(agent.latitude).toFixed(5)}, {Number(agent.longitude).toFixed(5)} <ExternalLink className="h-3 w-3" />
            </a>
          ) : null],
          ["Last synced", agent.last_synced_at ? dateTime(agent.last_synced_at) : null],
        ]} />
      </Section>

      <Section title="Recorded in ALTY">
        <LoadState loading={activity.loading} error={activity.error} onRetry={activity.reload} />
        {activity.data && (
          <>
            <p className="text-sm text-ab-muted">
              {activity.data.recorded.clients} clients · {activity.data.recorded.properties} properties · {activity.data.recorded.transactions} transactions
              ({activity.data.recorded.active_reservations} active reservations, {activity.data.recorded.completed_sales} completed sales, {peso(activity.data.recorded.sales_value)})
            </p>
            {activity.data.clients.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {activity.data.clients.map((c) => (
                  <Link key={c.client_id} to={`/manage/clients?id=${c.client_id}`} className="rounded-full border border-ab-border bg-ab-card-2 px-2.5 py-1 text-xs hover:border-ab-accent">
                    {c.full_name} · {statusLabel(c.status)}
                  </Link>
                ))}
              </div>
            )}
            <ul className="mt-3 space-y-2">
              {activity.data.transactions.map((t) => (
                <li key={t.transaction_id} className="rounded-xl border border-ab-border p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <Link to={`/manage/transactions?id=${t.transaction_id}`} className="font-semibold hover:underline">{statusLabel(t.transaction_type)} · {peso(t.amount)}</Link>
                    <Badge value={t.status} />
                  </div>
                  <p className="mt-1 text-xs text-ab-muted">
                    {date(t.transaction_date)} · {text(t.client_name)} · <Link to={`/manage/properties?id=${t.property_id}`} className="hover:underline">{text(t.property_title)}</Link>
                  </p>
                </li>
              ))}
            </ul>
          </>
        )}
      </Section>

      <Section title="Client reviews">
        <LoadState loading={reviews.loading} error={reviews.error} onRetry={reviews.reload} />
        {reviews.data && (
          reviews.data.review_count === 0 ? <p className="text-sm italic text-ab-faint">No client reviews yet.</p> : (
            <>
              <ul className="space-y-1">
                {Object.entries(reviews.data.distribution).map(([stars, n]) => (
                  <li key={stars} className="flex items-center gap-2 text-xs">
                    <span className="w-6 text-ab-muted">{stars}★</span>
                    <span className="h-2 flex-1 overflow-hidden rounded-full bg-ab-card-2"><span className="block h-full rounded-full bg-ab-warning" style={{ width: `${(n / maxBar) * 100}%` }} /></span>
                    <span className="w-6 text-right tabular-nums text-ab-muted">{n}</span>
                  </li>
                ))}
              </ul>
              <ul className="mt-3 space-y-2">
                {reviews.data.reviews.map((r) => (
                  <li key={r.id} className="rounded-xl border border-ab-border p-3 text-sm">
                    <p className="font-semibold">{"★".repeat(r.rating)}<span className="text-ab-faint">{"★".repeat(5 - r.rating)}</span> <span className="ml-1 font-normal text-ab-muted">{r.reviewer} · {date(r.created_at)}</span></p>
                    {r.review && <p className="mt-1 text-ab-muted">{r.review}</p>}
                    {r.property_title && <p className="mt-1 text-xs text-ab-faint">{r.property_title}</p>}
                  </li>
                ))}
              </ul>
            </>
          )
        )}
      </Section>
    </Drawer>
  )
}
