import { useCallback, useMemo, useState } from "react"
import { ExternalLink, Phone, Star } from "lucide-react"
import { Link } from "@/components/Link"
import { contains, date, dateTime, isManagement, peso, pesoShort, statusLabel, text, transactionDate } from "./format"
import { SubjectInsights } from "./Insights"
import { SyncButton } from "./SyncButton"
import { Badge, DataTable, Drawer, Facts, LoadState, PageHeader, SearchBox, Section, Select, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData, useOpenRecord } from "./useApiData"
import { locale, t } from "./i18n"
import { CancelReason } from "./cancellation"
import { callLabels } from "./callLabels"
import { CallButton } from "@/components/CallButton"
import { useToast } from "./toastContext"
import { AgentAvatar, PhotoControls } from "./avatars"
import { photoBody } from "./photoBody"

type Agent = {
  agent_id: string; full_name: string; phone_number: string | null; agent_location: string | null
  latitude: string | null; longitude: string | null; star_rating: string | null
  assignments_count: number; transactions_count: number; completed_sales: number
  total_sales: string | null; total_commission: string | null; performance_score: string | null
  client_rating: number | null; review_count: number; status: string; sync_status: string
  // counted from the clients and transactions recorded in ALTY
  assigned_clients: number; recorded_transactions: number; open_reservations: number
  recorded_completed_sales: number; recorded_sales_value: number
  recorded_deals: number; performance_rate: number | null; photo_version: number | null
  last_synced_at: string | null; created_at: string | null; updated_at: string | null
}
type Activity = {
  recorded: { clients: number; transactions: number; active_reservations: number; completed_sales: number; sales_value: number; properties: number }
  clients: { client_id: string; full_name: string; status: string; property_id: number | null }[]
  transactions: { transaction_id: string; client_name: string | null; property_id: number; property_title: string | null; transaction_type: string; transaction_date: string; amount: number; status: string; cancellation_reason?: string | null }[]
}
type Reviews = {
  client_rating: number | null; review_count: number; distribution: Record<string, number>
  reviews: { id: number; rating: number; review: string | null; reviewer: string; property_title: string | null; created_at: string }[]
}

function Stars({ value }: { value: number | null }) {
  if (value == null) return <span className="text-ab-faint">{t("No reviews")}</span>
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
  const { data, error, loading, reload } = useApiData(load, "agents")
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
          <AgentAvatar agentId={a.agent_id} name={a.full_name} version={a.photo_version} />
          <span className="min-w-0">
            <span className="block truncate font-semibold">{a.full_name}</span>
            <span className="block truncate text-xs text-ab-faint">{a.agent_id} · {text(a.agent_location)}</span>
          </span>
        </span>
      ),
    },
    { key: "status", label: "Status", sort: (a) => a.status, render: (a) => <Badge value={a.status} /> },
    { key: "client", label: "Client rating", sort: (a) => a.client_rating ?? -1, render: (a) => <span>{<Stars value={a.client_rating} />}{a.review_count ? <span className="ml-1 text-xs text-ab-faint">({a.review_count})</span> : null}</span> },
    { key: "clients", label: "Assigned clients", align: "right", sort: (a) => a.assigned_clients, render: (a) => a.assigned_clients, hideOnPhone: true },
    { key: "open", label: "Open reservations", align: "right", sort: (a) => a.open_reservations, render: (a) => a.open_reservations },
    { key: "transactions", label: "Transactions", align: "right", sort: (a) => a.recorded_transactions, render: (a) => a.recorded_transactions, hideOnPhone: true },
    { key: "sales", label: "Completed sales", align: "right", sort: (a) => a.recorded_completed_sales, render: (a) => a.recorded_completed_sales },
    { key: "value", label: "Sales value", align: "right", sort: (a) => a.recorded_sales_value, render: (a) => (a.recorded_sales_value ? pesoShort(a.recorded_sales_value) : "—") },
    {
      key: "performance", label: "Performance", align: "right", sort: (a) => a.performance_rate ?? -1,
      render: (a) => <Performance rate={a.performance_rate} deals={a.recorded_deals} />,
    },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Your agents and the work recorded for each"
        subtitle="Agents and the clients, reservations and sales recorded for each one in ALTY, with verified client reviews."
        actions={isManagement(user?.role) && <SyncButton path="/agents/sync" what="Agents" onDone={reload} />}
      />
      {data && (
        <Tiles items={[
          { label: "Agents", value: agents.length, onClick: () => setStatus(""), active: !status },
          { label: "Active", value: active, onClick: () => setStatus(status === "ACTIVE" ? "" : "ACTIVE"), active: status === "ACTIVE" },
          { label: "Open reservations", value: agents.reduce((s, a) => s + a.open_reservations, 0), detail: "Waiting to become sales" },
          { label: "Completed sales", value: agents.reduce((s, a) => s + a.recorded_completed_sales, 0), detail: "Recorded in ALTY" },
          { label: "Sales value", value: pesoShort(agents.reduce((s, a) => s + a.recorded_sales_value, 0)), detail: "Recorded in ALTY" },
          { label: "Client-reviewed agents", value: reviewed.length, detail: reviewed.length ? t("of {n}", { n: agents.length }) : t("No client reviews yet") },
        ]} />
      )}
      <div className="flex flex-wrap gap-2 sm:flex-nowrap">
        <div className="w-full sm:w-auto sm:flex-1"><SearchBox value={search} onChange={setSearch} placeholder="Search name, agent ID, location or phone" /></div>
        <Select label="Status" value={status} onChange={setStatus} options={[{ value: "", label: "All statuses" }, ...[...new Set(agents.map((a) => a.status))].map((s) => ({ value: s, label: statusLabel(s) }))]} />
      </div>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <>
          <p className="text-xs text-ab-faint">{t("{n} of {total} agents", { n: shown.length, total: agents.length })}</p>
          <DataTable rows={shown} columns={columns} rowKey={(a) => a.agent_id} onOpen={(a) => open(a.agent_id)} empty="No agents match these filters." initialSort={{ key: "value", dir: "desc" }} />
        </>
      )}
      {selected && <AgentDrawer agent={selected} onClose={close} onChanged={reload} />}
    </div>
  )
}

/** Completed sales ÷ recorded deals; "—" when the agent has no deals yet. */
function Performance({ rate, deals }: { rate: number | null; deals: number }) {
  if (rate == null) return <span className="text-ab-faint">—</span>
  return (
    <span title={t("{sales}% of {deals} recorded deals became completed sales", { sales: rate.toFixed(1), deals })} className="tabular-nums">
      {rate.toFixed(1)}%
    </span>
  )
}

type AgentOutlook = {
  status: string; observations: number; nonzero_months: number; minimum_required: number
  recent_sales: number; expected_sales: number | null; trend_per_month: number | null
  forecast: { month: string; value: number; lower: number; upper: number }[]
}

/** Expected completed sales for the next 3 months, from the agent's own history. */
function AgentForecast({ agentId }: { agentId: string }) {
  const { api } = useStaffAuth()
  const load = useCallback(() => api<AgentOutlook>(`/intelligence/agents/${encodeURIComponent(agentId)}/forecast`), [api, agentId])
  const { data, error, loading, reload } = useApiData(load)
  return (
    <Section title="Performance forecast">
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (data.status === "estimated" ? (
        <>
          <p className="text-sm">
            {t("Expected completed sales in the next 3 months:")} <span className="text-lg font-extrabold tabular-nums">{data.expected_sales?.toFixed(1)}</span>
            <span className="ml-2 text-xs text-ab-faint">{t("({n} in the last 3 months)", { n: data.recent_sales })}</span>
          </p>
          <ul className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
            {data.forecast.map((point) => (
              <li key={point.month} className="rounded-xl border border-ab-border p-2">
                <span className="block text-ab-faint">{new Date(`${point.month}-01T00:00:00`).toLocaleDateString(locale(), { month: "short", year: "numeric" })}</span>
                <span className="block text-base font-bold tabular-nums">{point.value.toFixed(1)}</span>
                <span className="block text-ab-faint">{point.lower.toFixed(1)}–{point.upper.toFixed(1)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-ab-faint">
            {t("Linear trend over this agent's {n} complete months; the small numbers are the likely range.", { n: data.observations })}
          </p>
        </>
      ) : (
        <p className="text-sm text-ab-muted">
          {t("Not enough history to forecast this agent yet: needs {min} complete months with sales in 3 or more. Recorded: {n} month(s), {s} with sales.", {
            min: data.minimum_required, n: data.observations, s: data.nonzero_months,
          })}
        </p>
      ))}
    </Section>
  )
}

function AgentDrawer({ agent, onClose, onChanged }: { agent: Agent; onClose: () => void; onChanged: () => Promise<void> }) {
  const { api, user } = useStaffAuth()
  const toast = useToast()
  const canManage = isManagement(user?.role)
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
        <CallButton phone={agent.phone_number ?? phone} name={agent.full_name} labels={callLabels()}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-xl bg-ab-accent px-3.5 text-sm font-semibold text-ab-ink hover:bg-ab-accent-hover">
          <Phone className="h-4 w-4" /> {t("Call {phone}", { phone: agent.phone_number ?? "" })}
        </CallButton>
      )}
    >
      <div className="flex flex-wrap items-center gap-4 rounded-2xl border border-ab-border bg-ab-card p-4">
        <AgentAvatar agentId={agent.agent_id} name={agent.full_name} version={agent.photo_version} size="lg" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-lg font-extrabold">{agent.full_name}</p>
          <p className="text-sm text-ab-muted">
            {t("Performance")}: <span className="font-bold text-ab-text"><Performance rate={agent.performance_rate} deals={agent.recorded_deals} /></span>
            <span className="text-xs text-ab-faint"> · {t("{n} recorded deal(s)", { n: agent.recorded_deals })}</span>
          </p>
          {canManage && (
            <div className="mt-2">
              <PhotoControls
                hasPhoto={Boolean(agent.photo_version)}
                onUpload={async (file) => {
                  try {
                    await api(`/agents/${encodeURIComponent(agent.agent_id)}/photo`, { method: "PUT", body: photoBody(file) })
                    toast(t("Photo updated. It also shows on the website's agent pages."))
                    await onChanged()
                  } catch (uploadError) { toast(t((uploadError as Error).message), "error") }
                }}
                onRemove={async () => {
                  try {
                    await api(`/agents/${encodeURIComponent(agent.agent_id)}/photo`, { method: "DELETE" })
                    toast(t("Photo removed."))
                    await onChanged()
                  } catch (removeError) { toast(t((removeError as Error).message), "error") }
                }}
              />
            </div>
          )}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {([
          ["Assigned clients", agent.assigned_clients],
          ["Open reservations", agent.open_reservations],
          ["Transactions", agent.recorded_transactions],
          ["Completed sales", agent.recorded_completed_sales],
          ["Sales value", agent.recorded_sales_value ? peso(agent.recorded_sales_value) : "—"],
          ["Client rating", agent.client_rating != null ? `${agent.client_rating.toFixed(1)} ★ (${agent.review_count})` : t("No reviews")],
        ] as const).map(([label, value]) => (
          <div key={label} className="rounded-xl border border-ab-border bg-ab-card p-3">
            <p className="text-[11px] text-ab-faint">{t(label)}</p>
            <p className="mt-0.5 font-bold tabular-nums">{value}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-ab-faint">{t("Counted from the clients, reservations and sales recorded in ALTY; cancelled transactions are left out. Client rating comes only from verified client reviews. Performance is the share of recorded deals (one client and one property) that became completed sales.")}</p>

      {canManage && <AgentForecast agentId={agent.agent_id} />}
      {canManage && (
        <SubjectInsights path={`/intelligence/agents/${encodeURIComponent(agent.agent_id)}`} empty={t("Nothing needs attention for this agent right now.")} />
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
              {t("{c} clients · {p} properties · {n} transactions ({r} active reservations, {s} completed sales, {v})", {
                c: activity.data.recorded.clients, p: activity.data.recorded.properties, n: activity.data.recorded.transactions,
                r: activity.data.recorded.active_reservations, s: activity.data.recorded.completed_sales, v: peso(activity.data.recorded.sales_value),
              })}
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
              {activity.data.transactions.map((tx) => (
                <li key={tx.transaction_id} className="rounded-xl border border-ab-border p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <Link to={`/manage/transactions?id=${tx.transaction_id}`} className="font-semibold hover:underline">{statusLabel(tx.transaction_type)} · {peso(tx.amount)}</Link>
                    <Badge value={tx.status} />
                  </div>
                  <p className="mt-1 text-xs text-ab-muted">
                    {transactionDate(tx.transaction_date)} · {text(tx.client_name)} · <Link to={`/manage/properties?id=${tx.property_id}`} className="hover:underline">{text(tx.property_title)}</Link>
                  </p>
                  <CancelReason status={tx.status} reason={tx.cancellation_reason} />
                </li>
              ))}
            </ul>
          </>
        )}
      </Section>

      <Section title="Client reviews">
        <LoadState loading={reviews.loading} error={reviews.error} onRetry={reviews.reload} />
        {reviews.data && (
          reviews.data.review_count === 0 ? <p className="text-sm italic text-ab-faint">{t("No client reviews yet.")}</p> : (
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
