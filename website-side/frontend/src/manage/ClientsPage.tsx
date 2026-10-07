import { useCallback, useMemo, useState } from "react"
import { Mail, MapPin, Phone, Trash2 } from "lucide-react"
import { Link } from "@/components/Link"
import { contains, date, dateTime, isManagement, peso, statusLabel, text, transactionDate } from "./format"
import { SyncButton } from "./SyncButton"
import { Badge, Button, Confirm, DataTable, Drawer, Facts, LoadState, PageHeader, SearchBox, Section, Select, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData, useOpenRecord } from "./useApiData"
import { t } from "./i18n"

type Client = {
  client_id: string; external_client_id: string | null; full_name: string; location: string | null
  phone_number: string | null; email: string | null; occupation: string | null; civil_status: string | null
  preferred_contact: string | null; purpose_of_purchase: string | null
  agent_id: string | null; agent_name: string | null
  property_id: number | null; property_title: string | null; property_location: string | null; property_price: number | null
  transaction_type: string | null; transaction_date: string | null; status: string; source: string; sync_status: string
  created_at: string | null; updated_at: string | null; transaction_id: string | null; amount: number | null; transaction_count: number
}
type Summary = { total: number; prospect: number; reserved: number; sold: number; cancelled: number }
type Profile = {
  transactions: { transaction_id: string; property_id: number; property_title: string | null; agent_id: string; agent_name: string | null; transaction_type: string; transaction_date: string; amount: number; status: string; source: string; source_document_id: string | null }[]
  documents: { document_id: string; document_name: string; document_type: string; status: string; version: number; created_at: string }[]
}

export function ClientsPage() {
  const { api, user } = useStaffAuth()
  const { id, open, close } = useOpenRecord()
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("")
  const load = useCallback(() => Promise.all([api<Client[]>("/clients?limit=2000"), api<Summary>("/clients/summary")]), [api])
  const { data, error, loading, reload } = useApiData(load, "clients")
  const [clients, summary] = data ?? [[], null]
  const shown = useMemo(
    () => clients.filter((c) => (!status || c.status === status) &&
      contains([c.full_name, c.email, c.phone_number, c.location, c.property_title, c.agent_name, c.client_id, c.external_client_id], search)),
    [clients, status, search],
  )
  const selected = id ? clients.find((c) => c.client_id === id || c.external_client_id === id) ?? null : null

  const columns: Column<Client>[] = [
    {
      key: "name", label: "Client", sort: (c) => c.full_name,
      render: (c) => (
        <span className="min-w-0">
          <span className="block truncate font-semibold">{c.full_name}</span>
          <span className="block truncate text-xs text-ab-faint">{text(c.phone_number ?? c.email)} · {text(c.location)}</span>
        </span>
      ),
    },
    { key: "property", label: "Property", sort: (c) => c.property_title ?? "", render: (c) => <span className="line-clamp-2">{text(c.property_title)}</span> },
    { key: "agent", label: "Agent", sort: (c) => c.agent_name ?? "", render: (c) => text(c.agent_name), hideOnPhone: true },
    { key: "date", label: "Latest", sort: (c) => c.transaction_date ?? "", render: (c) => (c.transaction_type ? `${statusLabel(c.transaction_type)} · ${transactionDate(c.transaction_date)}` : "—") },
    { key: "count", label: "Transactions", align: "right", sort: (c) => c.transaction_count, render: (c) => c.transaction_count, hideOnPhone: true },
    { key: "status", label: "Status", sort: (c) => c.status, render: (c) => <Badge value={c.status} /> },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Buyers & Sellers"
        subtitle="Clients are created automatically from buyer, reservation and sale documents and from website client accounts — there's no manual “Add client”."
        actions={isManagement(user?.role) && <SyncButton path="/clients/sync" what="Clients" onDone={reload} />}
      />
      {summary && (
        <Tiles items={[
          { label: "All clients", value: summary.total, onClick: () => setStatus(""), active: !status },
          ...(["prospect", "reserved", "sold", "cancelled"] as const).map((key) => ({
            label: statusLabel(key), value: summary[key], onClick: () => setStatus(status === key.toUpperCase() ? "" : key.toUpperCase()), active: status === key.toUpperCase(),
          })),
        ]} />
      )}
      <div className="flex flex-wrap gap-2 sm:flex-nowrap">
        <div className="w-full sm:w-auto sm:flex-1"><SearchBox value={search} onChange={setSearch} placeholder="Search name, phone, email, property or agent" /></div>
        <Select label="Status" value={status} onChange={setStatus} options={[{ value: "", label: "All statuses" }, ...["PROSPECT", "RESERVED", "SOLD", "CANCELLED"].map((s) => ({ value: s, label: statusLabel(s) }))]} />
      </div>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <>
          <p className="text-xs text-ab-faint">{t("{n} of {total} clients", { n: shown.length, total: clients.length })}</p>
          <DataTable rows={shown} columns={columns} rowKey={(c) => c.client_id} onOpen={(c) => open(c.client_id)} empty="No clients match these filters." initialSort={{ key: "date", dir: "desc" }} />
        </>
      )}
      {selected && <ClientDrawer client={selected} onClose={close} onDeleted={() => { close(); void reload() }} />}
    </div>
  )
}

function ClientDrawer({ client, onClose, onDeleted }: { client: Client; onClose: () => void; onDeleted: () => void }) {
  const { api, user } = useStaffAuth()
  const toast = useToast()
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const loadProfile = useCallback(() => api<Profile>(`/clients/${encodeURIComponent(client.client_id)}/profile`), [api, client.client_id])
  const profile = useApiData(loadProfile)
  const hasCompletedSale = (profile.data?.transactions ?? []).some((tx) => tx.transaction_type === "SOLD" && tx.status === "COMPLETED")

  const remove = async () => {
    setBusy(true)
    try {
      await api(`/clients/${encodeURIComponent(client.client_id)}`, { method: "DELETE" })
      toast(t("Deleted client {name}.", { name: client.full_name }))
      onDeleted()
    } catch (error) {
      toast((error as Error).message, "error")
      setBusy(false)
      setConfirm(false)
    }
  }

  return (
    <Drawer
      title={client.full_name}
      subtitle={<span className="flex flex-wrap items-center gap-2"><Badge value={client.status} /> {t("Source:")} {statusLabel(client.source)}</span>}
      onClose={onClose}
      footer={isManagement(user?.role) && (
        <Button variant="danger" onClick={() => setConfirm(true)} disabled={hasCompletedSale}
          title={hasCompletedSale ? t("Clients with a completed sale keep their history and can't be deleted") : t("Remove a client created in error")}>
          <Trash2 className="h-4 w-4" /> {t("Delete client")}
        </Button>
      )}
    >
      <div className="flex flex-wrap gap-2 text-sm">
        {client.phone_number && <a href={`tel:${client.phone_number.replace(/[^\d+]/g, "")}`} className="inline-flex items-center gap-1.5 rounded-full border border-ab-border bg-ab-card px-3 py-1 hover:border-ab-accent"><Phone className="h-3.5 w-3.5 text-ab-accent" />{client.phone_number}</a>}
        {client.email && <a href={`mailto:${client.email}`} className="inline-flex items-center gap-1.5 rounded-full border border-ab-border bg-ab-card px-3 py-1 hover:border-ab-accent"><Mail className="h-3.5 w-3.5 text-ab-accent" />{client.email}</a>}
        {client.location && <span className="inline-flex items-center gap-1.5 rounded-full border border-ab-border bg-ab-card px-3 py-1"><MapPin className="h-3.5 w-3.5 text-ab-accent" />{client.location}</span>}
      </div>

      <Section title="Property & agent">
        <Facts items={[
          ["Property", client.property_id ? <Link to={`/manage/properties?id=${client.property_id}`} className="hover:underline">{text(client.property_title)}</Link> : null],
          ["Location", client.property_location],
          ["Price", client.property_price ? peso(client.property_price) : null],
          ["Agent", client.agent_id ? <Link to={`/manage/agents?id=${client.agent_id}`} className="hover:underline">{text(client.agent_name)} ({client.agent_id})</Link> : null],
          ["Latest transaction", client.transaction_type ? `${statusLabel(client.transaction_type)} · ${transactionDate(client.transaction_date)}` : null],
          ["Amount", client.amount ? peso(client.amount) : null],
        ]} />
      </Section>

      <Section title="Personal details">
        <Facts items={[
          ["Occupation", client.occupation],
          ["Civil status", client.civil_status],
          ["Preferred contact", client.preferred_contact],
          ["Purpose of purchase", client.purpose_of_purchase],
          ["Client ID", <span className="break-all font-mono text-xs">{client.client_id}</span>],
          ["External ID", client.external_client_id],
          ["Created", client.created_at ? dateTime(client.created_at) : null],
          ["Sync status", statusLabel(client.sync_status)],
        ]} />
      </Section>

      <Section title={`${t("Transaction history")}${profile.data ? ` (${profile.data.transactions.length})` : ""}`}>
        <LoadState loading={profile.loading} error={profile.error} onRetry={profile.reload} />
        {profile.data && (profile.data.transactions.length === 0 ? <p className="text-sm italic text-ab-faint">{t("No transactions recorded.")}</p> : (
          <ol className="relative space-y-3 border-l border-ab-border pl-4">
            {profile.data.transactions.map((tx) => (
              <li key={tx.transaction_id} className="text-sm">
                <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-ab-accent" aria-hidden />
                <div className="flex items-center justify-between gap-2">
                  <Link to={`/manage/transactions?id=${tx.transaction_id}`} className="font-semibold hover:underline">{statusLabel(tx.transaction_type)} · {peso(tx.amount)}</Link>
                  <Badge value={tx.status} />
                </div>
                <p className="text-xs text-ab-muted">
                  {transactionDate(tx.transaction_date)} · <Link to={`/manage/properties?id=${tx.property_id}`} className="hover:underline">{text(tx.property_title)}</Link> ·{" "}
                  <Link to={`/manage/agents?id=${tx.agent_id}`} className="hover:underline">{text(tx.agent_name)}</Link> · {statusLabel(tx.source)}
                </p>
              </li>
            ))}
          </ol>
        ))}
      </Section>

      <Section title="Related documents">
        {profile.data && (profile.data.documents.length === 0 ? <p className="text-sm italic text-ab-faint">{t("No documents linked to this client.")}</p> : (
          <ul className="space-y-1.5 text-sm">
            {profile.data.documents.map((d) => (
              <li key={`${d.document_id}-${d.version}`} className="flex items-center justify-between gap-2">
                <span className="min-w-0 truncate">{d.document_name} <span className="text-xs text-ab-faint">{statusLabel(d.document_type)} · v{d.version} · {date(d.created_at)}</span></span>
                <Badge value={d.status} />
              </li>
            ))}
          </ul>
        ))}
      </Section>

      {confirm && (
        <Confirm typeToConfirm="Delete"
          title="Delete client?"
          message={
            t("Remove {name}, created in error? This also deletes their {n} recorded transaction(s), and any property they had reserved goes back to Available. This can't be undone.", { name: client.full_name, n: profile.data ? profile.data.transactions.length : "" })
          }
          confirmLabel="Delete"
          busy={busy}
          onConfirm={remove}
          onCancel={() => setConfirm(false)}
        />
      )}
    </Drawer>
  )
}
