import { useCallback, useMemo, useState } from "react"
import { Link } from "@/components/Link"
import { contains, dateTime, isManagement, peso, pesoShort, statusLabel, text, transactionDate } from "./format"
import { SyncButton } from "./SyncButton"
import { Badge, Button, DataTable, Drawer, Facts, LoadState, PageHeader, SearchBox, Section, Select, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData, useOpenRecord } from "./useApiData"
import { t } from "./i18n"
import { useToast } from "./toastContext"
import { CancellationDetails, CancelReason, CancelReservationDialog } from "./cancellation"

type Transaction = {
  transaction_id: string; external_transaction_id: string | null; client_id: string; client_name: string | null
  property_id: number; property_external_id: string | null; property_title: string | null
  agent_id: string; agent_name: string | null; transaction_type: string; transaction_date: string
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
  const load = useCallback(() => Promise.all([api<Transaction[]>("/transactions?limit=2000"), api<Summary>("/transactions/summary")]), [api])
  const { data, error, loading, reload } = useApiData(load, "transactions")
  const [rows, summary] = data ?? [[], null]
  const shown = useMemo(
    () => rows.filter((t) => (!status || t.status === status) && (!type || t.transaction_type === type) &&
      contains([t.client_name, t.property_title, t.agent_name, t.transaction_id, t.external_transaction_id, t.agent_id, t.cancellation_reason], search)),
    [rows, status, type, search],
  )
  const selected = id ? rows.find((t) => t.transaction_id === id || t.external_transaction_id === id) ?? null : null
  const types = [...new Set(rows.map((t) => t.transaction_type))]

  const columns: Column<Transaction>[] = [
    { key: "date", label: "When", sort: (t) => t.transaction_date, render: (t) => <span className="whitespace-nowrap">{transactionDate(t.transaction_date)}</span> },
    {
      key: "client", label: "Client", sort: (t) => t.client_name ?? "",
      render: (t) => (
        <span className="min-w-0">
          <span className="block truncate font-semibold">{text(t.client_name)}</span>
          <span className="block truncate font-mono text-[11px] text-ab-faint">{t.transaction_id.slice(0, 8)}</span>
        </span>
      ),
    },
    { key: "property", label: "Property", sort: (t) => t.property_title ?? "", render: (t) => <span className="line-clamp-2">{text(t.property_title)}</span> },
    { key: "agent", label: "Agent", sort: (t) => t.agent_name ?? "", render: (t) => text(t.agent_name), hideOnPhone: true },
    { key: "type", label: "Type", sort: (t) => t.transaction_type, render: (t) => statusLabel(t.transaction_type) },
    { key: "amount", label: "Amount", align: "right", sort: (t) => Number(t.amount), render: (t) => peso(t.amount) },
    {
      key: "status", label: "Status", sort: (t) => t.status,
      render: (t) => <span className="flex flex-col items-start gap-0.5"><Badge value={t.status} /><CancelReason status={t.status} reason={t.cancellation_reason} compact /></span>,
    },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Every reservation and sale on record"
        subtitle="Reservations and sales recorded from processed documents and from the central database. Transactions are never created by hand, so the history stays tied to its documents."
        actions={isManagement(user?.role) && <SyncButton path="/transactions/sync" what="Transactions" onDone={reload} />}
      />
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
      </div>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <>
          <p className="text-xs text-ab-faint">{t("{n} of {total} transactions", { n: shown.length, total: rows.length })}</p>
          <DataTable rows={shown} columns={columns} rowKey={(t) => t.transaction_id} onOpen={(t) => open(t.transaction_id)} empty="No transactions match these filters." initialSort={{ key: "date", dir: "desc" }} />
        </>
      )}
      {selected && <TransactionDrawer transaction={selected} related={rows} onClose={close} canCancel={isManagement(user?.role)} onChanged={reload} />}
    </div>
  )
}

function TransactionDrawer({ transaction: tx, related, onClose, canCancel, onChanged }: {
  transaction: Transaction; related: Transaction[]; onClose: () => void; canCancel: boolean; onChanged: () => Promise<void>
}) {
  const toast = useToast()
  const [cancelling, setCancelling] = useState(false)
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
        <Button variant="danger" onClick={() => setCancelling(true)}>{t("Cancel reservation")}</Button>
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
          ["Sync status", statusLabel(tx.sync_status)],
          ["Recorded", dateTime(tx.created_at)],
          ["Updated", dateTime(tx.updated_at)],
        ]} />
      </Section>
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
