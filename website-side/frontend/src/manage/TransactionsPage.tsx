import { useCallback, useMemo, useState } from "react"
import { Link } from "@/components/Link"
import { contains, date, dateTime, isManagement, peso, pesoShort, statusLabel, text, transactionDate } from "./format"
import { Badge, Button, DataTable, Drawer, Facts, LoadState, PageHeader, SearchBox, Section, Select, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData, useOpenRecord } from "./useApiData"
import { t } from "./i18n"
import { useToast } from "./toastContext"
import { CancellationDetails, CancelReason, CancelReservationDialog } from "./cancellation"
import { GrossSalesRecap } from "./GrossSalesRecap"
import { PaymentSchedule, ProceedToSaleDialog } from "./reservationPayments"
import { CostBreakdown } from "./costBreakdown"
import { DealsPipeline } from "./DealsPipeline"
import { locale } from "./i18n"

// Philippine-time month of a transaction ("2026-09").
const monthOf = (iso: string) => new Date(iso).toLocaleDateString("en-CA", { timeZone: "Asia/Manila" }).slice(0, 7)
const monthLabel = (key: string) => {
  const [year, month] = key.split("-").map(Number)
  return new Date(year, month - 1, 1).toLocaleDateString(locale(), { month: "long", year: "numeric" })
}

type Transaction = {
  transaction_id: string; external_transaction_id: string | null; client_id: string; client_name: string | null
  property_id: number; property_external_id: string | null; property_title: string | null; project_name?: string | null
  agent_id: string; agent_name: string | null; branch_id?: number | null; branch_name?: string | null; transaction_type: string; transaction_date: string
  amount: string; status: string; notes: string | null; source: string; source_document_id: string | null
  sync_status: string; created_at: string; updated_at: string
  cancellation_reason: string | null; cancelled_at: string | null; cancelled_by: string | null
}
type Summary = { total: number; reserved: number; completed: number; cancelled: number; amount_total: string }

export function TransactionsPage() {
  const { api, user } = useStaffAuth()
  const { id, open, close } = useOpenRecord()
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("")
  const [type, setType] = useState("")
  const [period, setPeriod] = useState("")
  const [view, setView] = useState<"board" | "records" | "pipeline">("board")
  const load = useCallback(() => Promise.all([api<Transaction[]>("/transactions?limit=2000"), api<Summary>("/transactions/summary")]), [api])
  const { data, error, loading, reload } = useApiData(load, "transactions")
  const [rows, summary] = data ?? [[], null]
  const shown = useMemo(
    () => rows.filter((t) => (!status || t.status === status) && (!type || t.transaction_type === type) &&
      (!period || (period.length === 4 ? monthOf(t.transaction_date).startsWith(period) : monthOf(t.transaction_date) === period)) &&
      contains([t.client_name, t.property_title, t.project_name, t.branch_name, t.agent_name, t.transaction_id, t.external_transaction_id, t.agent_id, t.cancellation_reason], search)),
    [rows, status, type, period, search],
  )
  const months = useMemo(() => [...new Set(rows.map((t) => monthOf(t.transaction_date)))].sort().reverse(), [rows])
  const years = [...new Set(months.map((m) => m.slice(0, 4)))]
  const periodLabel = !period ? t("all time") : period.length === 4 ? period : monthLabel(period)
  const selected = id ? rows.find((t) => t.transaction_id === id || t.external_transaction_id === id) ?? null : null
  const types = [...new Set(rows.map((t) => t.transaction_type))]

  const columns: Column<Transaction>[] = [
    { key: "date", label: "Res. date", sort: (t) => t.transaction_date, render: (t) => <span className="whitespace-nowrap">{transactionDate(t.transaction_date)}</span> },
    {
      key: "client", label: "Buyer", sort: (t) => t.client_name ?? "",
      render: (t) => (
        <span className="min-w-0">
          <span className="block truncate font-semibold">{text(t.client_name)}</span>
          <span className="block truncate font-mono text-[11px] text-ab-faint">{t.transaction_id.slice(0, 8)}</span>
        </span>
      ),
    },
    { key: "agent", label: "Agent", sort: (t) => t.agent_name ?? "", render: (t) => <span>{text(t.agent_name)}{t.branch_name && <span className="block text-[11px] text-ab-faint">{t.branch_name}</span>}</span>, hideOnPhone: true },
    { key: "property", label: "Project name", sort: (t) => t.project_name ?? t.property_title ?? "", render: (t) => <span className="line-clamp-2">{text(t.project_name ?? t.property_title)}</span> },
    { key: "amount", label: "TCP", align: "right", sort: (t) => Number(t.amount), render: (t) => peso(t.amount) },
    { key: "type", label: "Type", sort: (t) => t.transaction_type, render: (t) => statusLabel(t.transaction_type), hideOnPhone: true },
    {
      key: "status", label: "Status", sort: (t) => t.status,
      render: (t) => <span className="flex flex-col items-start gap-0.5"><Badge value={t.status} /><CancelReason status={t.status} reason={t.cancellation_reason} compact /></span>,
    },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Every reservation and sale on record"
        subtitle="Reservations and sales recorded from processed documents and from the central database. Management records the payments on a reservation and marks it sold when it proceeds to a purchase; every change is audited."
      />
      <div role="tablist" aria-label={t("Transactions view")} className="flex w-fit rounded-xl border border-ab-border bg-ab-card p-1">
        {([["board", "Sales board by team"], ["records", "Reservations & sales"], ["pipeline", "Pipeline: inquiry to closing"]] as const).map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={view === key} onClick={() => setView(key)}
            className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${view === key ? "bg-ab-accent text-ab-ink" : "text-ab-muted hover:text-ab-text"}`}>{t(label)}</button>
        ))}
      </div>
      {view === "pipeline" ? <DealsPipeline mode="company" /> : (<>
      {summary && (
        <Tiles items={[
          { label: "All transactions", value: summary.total, onClick: () => setStatus(""), active: !status },
          { label: "Reserved", value: summary.reserved, onClick: () => setStatus(status === "RESERVED" ? "" : "RESERVED"), active: status === "RESERVED" },
          { label: "Completed", value: summary.completed, onClick: () => setStatus(status === "COMPLETED" ? "" : "COMPLETED"), active: status === "COMPLETED" },
          { label: "Cancelled", value: summary.cancelled, onClick: () => setStatus(status === "CANCELLED" ? "" : "CANCELLED"), active: status === "CANCELLED" },
          { label: "Total amount", value: pesoShort(summary.amount_total), detail: "All recorded transactions" },
        ]} />
      )}
      <div className="flex flex-wrap gap-2 sm:flex-nowrap">
        <div className="w-full sm:w-auto sm:flex-1"><SearchBox value={search} onChange={setSearch} placeholder="Search client, property, agent or reference" /></div>
        <Select label="Type" value={type} onChange={setType} options={[{ value: "", label: "All types" }, ...types.map((t) => ({ value: t, label: statusLabel(t) }))]} />
        <Select label="Status" value={status} onChange={setStatus} options={[{ value: "", label: "All statuses" }, ...["RESERVED", "COMPLETED", "CANCELLED"].map((s) => ({ value: s, label: statusLabel(s) }))]} />
        <Select label="Period" value={period} onChange={setPeriod} options={[
          { value: "", label: "All time" },
          ...years.map((y) => ({ value: y, label: t("Year {y}", { y }) })),
          ...months.map((m) => ({ value: m, label: monthLabel(m) })),
        ]} />
      </div>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <>
          <GrossSalesRecap rows={shown} period={periodLabel} />
          <p className="text-xs text-ab-faint">{t("{n} of {total} transactions", { n: shown.length, total: rows.length })}</p>
          {view === "board"
            ? <SalesBoard rows={shown} onOpen={(t) => open(t.transaction_id)} />
            : <DataTable exportTitle="Transactions" rows={shown} columns={columns} rowKey={(t) => t.transaction_id} onOpen={(t) => open(t.transaction_id)} empty="No transactions match these filters." initialSort={{ key: "date", dir: "desc" }} />}
        </>
      )}
      {selected && <TransactionDrawer transaction={selected} related={rows} onClose={close} canCancel={isManagement(user?.role)} onChanged={reload} />}
      </>)}
    </div>
  )
}

/** Like the office whiteboard: one table per team / cluster with
 *  RES. DATE · BUYER · AGENT · PROJECT NAME · TCP, newest first. */
function SalesBoard({ rows, onOpen }: { rows: Transaction[]; onOpen: (t: Transaction) => void }) {
  const groups = useMemo(() => {
    const byTeam = new Map<string, Transaction[]>()
    for (const row of rows) {
      const team = row.branch_name ?? t("No team / cluster")
      byTeam.set(team, [...(byTeam.get(team) ?? []), row])
    }
    return [...byTeam.entries()]
      .map(([team, items]) => [team, [...items].sort((a, b) => b.transaction_date.localeCompare(a.transaction_date))] as const)
      .sort((a, b) => b[1].length - a[1].length)
  }, [rows])
  if (!rows.length) {
    return <div className="rounded-2xl border border-dashed border-ab-border px-4 py-14 text-center text-sm text-ab-muted">{t("No transactions match these filters.")}</div>
  }
  const tape = "inline-block -rotate-1 rounded-sm bg-[#F7E36A] px-2 py-0.5 text-[11px] font-black uppercase tracking-wide text-[#111719] shadow-sm"
  return (
    <div className="grid gap-4 2xl:grid-cols-2">
      {groups.map(([team, items]) => (
        <section key={team} aria-label={team} className="overflow-hidden rounded-2xl border border-ab-border bg-ab-card">
          <header className="flex items-center justify-between gap-2 border-b border-ab-border px-4 py-2.5">
            <span className={tape}>{team}</span>
            <span className="text-xs text-ab-muted">{t("{n} · {amount}", { n: items.length, amount: pesoShort(items.filter((x) => x.status !== "CANCELLED").reduce((sum, x) => sum + Number(x.amount), 0)) })}</span>
          </header>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="text-left">
                  {["Res. date", "Buyer", "Agent", "Project name", "TCP"].map((label) => (
                    <th key={label} scope="col" className={`px-3 py-2 ${label === "TCP" ? "text-right" : ""}`}><span className={tape}>{t(label)}</span></th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.transaction_id} onClick={() => onOpen(row)} className={`cursor-pointer border-t border-ab-border hover:bg-ab-hover ${row.status === "CANCELLED" ? "text-ab-faint line-through" : ""}`}>
                    <td className="whitespace-nowrap px-3 py-1.5 font-semibold">{date(row.transaction_date)}</td>
                    <td className="px-3 py-1.5"><button type="button" onClick={(e) => { e.stopPropagation(); onOpen(row) }} className="text-left hover:underline">{text(row.client_name)}</button></td>
                    <td className="px-3 py-1.5">{text(row.agent_name)}</td>
                    <td className="px-3 py-1.5">{text(row.project_name ?? row.property_title)}</td>
                    <td className="whitespace-nowrap px-3 py-1.5 text-right font-semibold tabular-nums">{Number(row.amount).toLocaleString("en-PH", { maximumFractionDigits: 2 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  )
}

function TransactionDrawer({ transaction: tx, related, onClose, canCancel, onChanged }: {
  transaction: Transaction; related: Transaction[]; onClose: () => void; canCancel: boolean; onChanged: () => Promise<void>
}) {
  const toast = useToast()
  const { api } = useStaffAuth()
  // The payment schedule and buying-cost estimate are off until Abellar confirms them.
  const loadFeatures = useCallback(() => api<{ payment_schedule: boolean; cost_estimate: boolean }>("/transactions/features"), [api])
  const features = useApiData(loadFeatures, "transaction-features").data
  const [cancelling, setCancelling] = useState(false)
  const [selling, setSelling] = useState(false)
  const isOpenReservation = tx.transaction_type === "RESERVED" && tx.status === "RESERVED"
  // Timeline: every transaction for the same property and client (reservation -> sale).
  const timeline = related
    .filter((r) => r.property_id === tx.property_id && r.client_id === tx.client_id)
    .sort((a, b) => a.transaction_date.localeCompare(b.transaction_date))
  return (
    <Drawer
      title={`${statusLabel(tx.transaction_type)} · ${peso(tx.amount)}`}
      subtitle={<span className="flex flex-wrap items-center gap-2"><Badge value={tx.status} /> {transactionDate(tx.transaction_date)}</span>}
      onClose={onClose}
      footer={canCancel && isOpenReservation && (
        <>
          <Button variant="danger" onClick={() => setCancelling(true)}>{t("Cancel reservation")}</Button>
          <Button variant="primary" onClick={() => setSelling(true)}>{t("Proceed to sale")}</Button>
        </>
      )}
    >
      {tx.status === "CANCELLED" && <CancellationDetails reason={tx.cancellation_reason} by={tx.cancelled_by} at={tx.cancelled_at} />}
      <Section title="Parties">
        <Facts items={[
          ["Client", <Link to={`/manage/clients?id=${tx.client_id}`} className="hover:underline">{text(tx.client_name)}</Link>],
          ["Property", <Link to={`/manage/properties?id=${tx.property_id}`} className="hover:underline">{text(tx.property_title)} (#{tx.property_id})</Link>],
          ["Agent", <Link to={`/manage/agents?id=${tx.agent_id}`} className="hover:underline">{text(tx.agent_name)} ({tx.agent_id})</Link>],
          ["Amount", peso(tx.amount)],
        ]} />
      </Section>
      {features?.cost_estimate && tx.status !== "CANCELLED" && <CostBreakdown transactionId={tx.transaction_id} />}
      {tx.transaction_type === "RESERVED" && tx.status !== "CANCELLED" && (
        features?.payment_schedule && <PaymentSchedule transactionId={tx.transaction_id} canRecord={canCancel} />
      )}
      <Section title="Timeline for this client and property">
        <ol className="relative space-y-3 border-l border-ab-border pl-4">
          {timeline.map((r) => (
            <li key={r.transaction_id} className="text-sm">
              <span className={`absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full ${r.transaction_id === tx.transaction_id ? "bg-ab-accent" : "bg-ab-border-strong"}`} aria-hidden />
              <p className={r.transaction_id === tx.transaction_id ? "font-semibold" : ""}>
                {statusLabel(r.transaction_type)} · {peso(r.amount)} <span className="ml-1"><Badge value={r.status} /></span>
              </p>
              <p className="text-xs text-ab-muted">{transactionDate(r.transaction_date)} · {statusLabel(r.source)}</p>
              <CancelReason status={r.status} reason={r.cancellation_reason} />
            </li>
          ))}
        </ol>
      </Section>
      <Section title="Record">
        <Facts items={[
          ["Transaction ID", <span className="break-all font-mono text-xs">{tx.transaction_id}</span>],
          ["External ID", tx.external_transaction_id],
          ["Source", statusLabel(tx.source)],
          ["Source document", tx.source_document_id ? <span className="break-all font-mono text-xs">{tx.source_document_id}</span> : null],
          ["Notes", tx.notes],
          ["Recorded", dateTime(tx.created_at)],
          ["Updated", dateTime(tx.updated_at)],
        ]} />
      </Section>
      {selling && (
        <ProceedToSaleDialog
          transactionId={tx.transaction_id}
          label={`${text(tx.client_name)} · ${text(tx.property_title)}`}
          price={null}
          onClose={() => setSelling(false)}
          onDone={() => { setSelling(false); toast(t("Marked as sold. The property and the client are now Sold.")); void onChanged() }}
        />
      )}
      {cancelling && (
        <CancelReservationDialog
          transactionId={tx.transaction_id}
          label={`${text(tx.client_name)} · ${text(tx.property_title)} · ${peso(tx.amount)}`}
          onClose={() => setCancelling(false)}
          onDone={() => { setCancelling(false); toast(t("Reservation cancelled. The reason is saved on the transaction.")); void onChanged() }}
        />
      )}
    </Drawer>
  )
}
