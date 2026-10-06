import { useCallback, useMemo, useState } from "react"
import { ExternalLink, MapPin, Pencil, Trash2 } from "lucide-react"
import { Link } from "@/components/Link"
import { CATEGORIES, categoryLabel, categoryOf } from "@/lib/categories"
import { canEditListings, contains, date, dateTime, isManagement, peso, statusLabel, text } from "./format"
import { SubjectInsights } from "./Insights"
import { PropertyEditForm, type Listing } from "./PropertyEditForm"
import { SyncButton } from "./SyncButton"
import { Badge, Button, Confirm, DataTable, Drawer, Facts, LoadState, PageHeader, SearchBox, Section, Select, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData, useOpenRecord } from "./useApiData"

type PartnerOption = { id: number; name: string; status: string }
type Summary = { available: number; reserved: number; sold: number; on_hold: number; unavailable: number; total: number }
type History = {
  status: string
  status_changed_at: string | null
  transactions: { transaction_id: string; client_id: string; client_name: string | null; agent_id: string; agent_name: string | null; transaction_type: string; transaction_date: string; amount: number; status: string; source: string }[]
  documents: { document_id?: string; id?: number; document_name?: string; document_type?: string; status?: string; created_at?: string }[]
}

const STATUSES = ["AVAILABLE", "RESERVED", "SOLD", "ON_HOLD", "UNAVAILABLE"]

export function PropertiesPage() {
  const { api, user } = useStaffAuth()
  const { id, open, close } = useOpenRecord()
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("")
  const [category, setCategory] = useState("")

  const load = useCallback(
    () => Promise.all([
      api<Listing[]>("/property-listings?limit=5000"),
      api<Summary>("/property-listings/status-summary"),
      api<PartnerOption[]>("/partners"),
    ]),
    [api],
  )
  const { data, setData, error, loading, reload } = useApiData(load)
  const [listings, summary, partners] = data ?? [[], null, []]

  const shown = useMemo(
    () => listings.filter((l) =>
      (!status || l.status === status) &&
      (!category || categoryOf(l.category)?.key === category) &&
      contains([l.title, l.village_name, l.category, l.layout_type, l.listing_id, l.external_listing_id], search)),
    [listings, status, category, search],
  )
  const selected = id ? listings.find((l) => String(l.listing_id) === id) ?? null : null

  const columns: Column<Listing>[] = [
    {
      key: "title", label: "Property", sort: (l) => l.title ?? "",
      render: (l) => (
        <span className="flex items-center gap-3">
          {l.photos?.[0] ? (
            <img src={l.photos[0]} alt="" loading="lazy" className="h-10 w-14 shrink-0 rounded-lg object-cover" />
          ) : (
            <span className="h-10 w-14 shrink-0 rounded-lg bg-ab-card-2" aria-hidden />
          )}
          <span className="min-w-0">
            <span className="block truncate font-semibold">{text(l.title)}</span>
            <span className="block truncate text-xs text-ab-faint">#{l.listing_id} · {text(l.village_name)}</span>
          </span>
        </span>
      ),
    },
    { key: "category", label: "Category", sort: (l) => categoryLabel(l.category), render: (l) => categoryLabel(l.category) },
    { key: "price", label: "Price", align: "right", sort: (l) => Number(l.price_total ?? 0), render: (l) => peso(l.price_total) },
    { key: "monthly", label: "Monthly", align: "right", sort: (l) => Number(l.monthly_rate ?? 0), render: (l) => peso(l.monthly_rate), hideOnPhone: true },
    { key: "rooms", label: "Bed / Bath", sort: (l) => l.num_bedrooms ?? 0, render: (l) => `${l.num_bedrooms ?? "—"} / ${l.num_bathrooms ?? "—"}`, hideOnPhone: true },
    { key: "status", label: "Status", sort: (l) => l.status, render: (l) => <Badge value={l.status} /> },
    { key: "sync", label: "Sync", sort: (l) => l.sync_status, render: (l) => <Badge value={l.sync_status} />, hideOnPhone: true },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Properties"
        subtitle="Listings from Supabase and from processed documents. Reserved and sold statuses come from reservation and sale documents."
        actions={isManagement(user?.role) && <SyncButton path="/property-listings/sync" what="Listings" onDone={reload} />}
      />
      {summary && (
        <Tiles
          items={[
            { label: "All listings", value: summary.total, onClick: () => setStatus(""), active: !status },
            ...(["available", "reserved", "sold", "on_hold", "unavailable"] as const).map((key) => ({
              label: statusLabel(key), value: summary[key], onClick: () => setStatus(status === key.toUpperCase() ? "" : key.toUpperCase()), active: status === key.toUpperCase(),
            })),
          ].slice(0, 6)}
        />
      )}
      <div className="flex flex-wrap gap-2 sm:flex-nowrap">
        <div className="w-full sm:w-auto sm:flex-1"><SearchBox value={search} onChange={setSearch} placeholder="Search title, village, category or ID" /></div>
        <Select label="Status" value={status} onChange={setStatus} options={[{ value: "", label: "All statuses" }, ...STATUSES.map((s) => ({ value: s, label: statusLabel(s) }))]} />
        <Select label="Category" value={category} onChange={setCategory} options={[{ value: "", label: "All categories" }, ...CATEGORIES.map((c) => ({ value: c.key, label: c.label }))]} />
      </div>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <>
          <p className="text-xs text-ab-faint">{shown.length} of {listings.length} listings</p>
          <DataTable rows={shown} columns={columns} rowKey={(l) => String(l.listing_id)} onOpen={(l) => open(String(l.listing_id))}
            empty="No listings match these filters." initialSort={{ key: "title", dir: "asc" }} />
        </>
      )}
      {selected && (
        <PropertyDrawer
          listing={selected}
          onClose={close}
          partners={partners}
          onSaved={(updated) => setData([listings.map((l) => (l.listing_id === updated.listing_id ? updated : l)), summary!, partners])}
          onDeleted={() => { close(); void reload() }}
        />
      )}
    </div>
  )
}

function PropertyDrawer({ listing, partners, onClose, onSaved, onDeleted }: {
  listing: Listing; partners: PartnerOption[]; onClose: () => void; onSaved: (l: Listing) => void; onDeleted: () => void
}) {
  const developer = partners.find((p) => p.id === listing.partner_id)
  const { api, user } = useStaffAuth()
  const toast = useToast()
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [photo, setPhoto] = useState(0)
  const loadHistory = useCallback(() => api<History>(`/property-listings/${listing.listing_id}/history`), [api, listing.listing_id])
  const history = useApiData(loadHistory)

  const remove = async () => {
    setDeleting(true)
    try {
      await api(`/property-listings/${listing.listing_id}`, { method: "DELETE" })
      toast(`Deleted "${listing.title}".`)
      onDeleted()
    } catch (error) {
      toast((error as Error).message, "error")
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  const amenities = Array.isArray(listing.amenity_list) ? listing.amenity_list : listing.amenity_list ? Object.keys(listing.amenity_list) : []
  const nearby = listing.nearby_establishments && typeof listing.nearby_establishments === "object" && !Array.isArray(listing.nearby_establishments)
    ? Object.entries(listing.nearby_establishments as Record<string, { name?: string; distance_km?: number }[]>)
    : []
  const photos = listing.photos ?? []
  const features = ([["Balcony", listing.has_balcony], ["Kitchen", listing.has_kitchen], ["Backyard", listing.has_backyard], ["Garage", listing.has_garage]] as const)
  const relatedClients = [...new Map((history.data?.transactions ?? []).map((t) => [t.client_id, t.client_name])).entries()]
  const relatedAgents = [...new Map((history.data?.transactions ?? []).map((t) => [t.agent_id, t.agent_name])).entries()]

  return (
    <Drawer
      title={listing.title ?? `Property #${listing.listing_id}`}
      subtitle={<span className="flex flex-wrap items-center gap-2"><Badge value={listing.status} /> {categoryLabel(listing.category)} · #{listing.listing_id}</span>}
      onClose={onClose}
      footer={
        <>
          {isManagement(user?.role) && <Button variant="danger" onClick={() => setConfirmDelete(true)}><Trash2 className="h-4 w-4" /> Delete</Button>}
          <Link to={`/map?property=${listing.listing_id}`} target="_blank" className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-ab-border-strong px-3.5 text-sm font-semibold hover:bg-ab-hover">
            <MapPin className="h-4 w-4" /> Public map <ExternalLink className="h-3 w-3" />
          </Link>
          {canEditListings(user?.role) && <Button variant="primary" onClick={() => setEditing(true)}><Pencil className="h-4 w-4" /> Edit</Button>}
        </>
      }
    >
      {photos.length > 0 && (
        <div>
          <img src={photos[Math.min(photo, photos.length - 1)]} alt={`Photo ${photo + 1} of ${listing.title}`} className="aspect-video w-full rounded-2xl object-cover" />
          {photos.length > 1 && (
            <div className="mt-2 flex gap-2 overflow-x-auto">
              {photos.map((src, i) => (
                <button key={src} type="button" onClick={() => setPhoto(i)} aria-label={`Photo ${i + 1}`}
                  className={`h-14 w-20 shrink-0 overflow-hidden rounded-lg border-2 ${i === photo ? "border-ab-accent" : "border-transparent"}`}>
                  <img src={src} alt="" loading="lazy" className="h-full w-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-3 gap-2">
        {([["Total price", listing.price_total], ["Down payment", listing.initial_dp], ["Monthly", listing.monthly_rate]] as const).map(([label, value]) => (
          <div key={label} className="rounded-xl border border-ab-border bg-ab-card p-3">
            <p className="text-[11px] text-ab-faint">{label}</p>
            <p className="mt-0.5 font-bold tabular-nums text-ab-text">{value ? peso(value) : "—"}</p>
          </div>
        ))}
      </div>

      {isManagement(user?.role) && (
        <SubjectInsights path={`/intelligence/properties/${listing.listing_id}`} empty="Nothing needs attention for this property right now." />
      )}

      <Section title="Details">
        <Facts items={[
          ["Developer / partner", developer ? <Link to={`/manage/partners?id=${developer.id}`} className="hover:underline">{developer.name}</Link> : null],
          ["Village / project", listing.village_name],
          ["Layout", listing.layout_type],
          ["Bedrooms", listing.num_bedrooms],
          ["Bathrooms", listing.num_bathrooms],
          ["Garage", listing.has_garage ? `${listing.garage_spaces || "Yes"}${listing.garage_spaces ? " space(s)" : ""}` : null],
          ["Coordinates", listing.lat != null && listing.lng != null ? `${Number(listing.lat).toFixed(5)}, ${Number(listing.lng).toFixed(5)}` : null],
        ]} />
        <div className="mt-3 flex flex-wrap gap-1.5">
          {features.map(([name, on]) => (
            <span key={name} className={`rounded-full px-2.5 py-1 text-xs font-semibold ${on ? "bg-ab-accent-soft text-ab-accent" : "border border-dashed border-ab-border text-ab-faint"}`}>
              {on ? "✓ " : ""}{name}
            </span>
          ))}
        </div>
        {listing.details && <p className="mt-3 whitespace-pre-line text-sm text-ab-muted">{listing.details}</p>}
      </Section>

      <Section title="Amenities & nearby">
        {amenities.length ? (
          <div className="flex flex-wrap gap-1.5">{amenities.map((a) => <span key={String(a)} className="rounded-full border border-ab-border bg-ab-card-2 px-2.5 py-1 text-xs">{String(a)}</span>)}</div>
        ) : <p className="text-sm italic text-ab-faint">No amenities listed</p>}
        {nearby.length > 0 && (
          <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
            {nearby.map(([group, items]) => (
              <div key={group}>
                <dt className="text-xs capitalize text-ab-faint">{group.replace(/_/g, " ")}</dt>
                {(Array.isArray(items) ? items : []).map((item) => (
                  <dd key={item.name} className="font-medium">{item.name}{item.distance_km != null && <span className="text-ab-faint"> · {item.distance_km} km</span>}</dd>
                ))}
              </div>
            ))}
          </dl>
        )}
      </Section>

      <Section title="History">
        <LoadState loading={history.loading} error={history.error} onRetry={history.reload} />
        {history.data && (
          <>
            {history.data.transactions.length === 0 ? (
              <p className="text-sm italic text-ab-faint">No transactions recorded for this property.</p>
            ) : (
              <ul className="space-y-2">
                {history.data.transactions.map((t) => (
                  <li key={t.transaction_id} className="rounded-xl border border-ab-border p-3 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <Link to={`/manage/transactions?id=${t.transaction_id}`} className="font-semibold hover:underline">{statusLabel(t.transaction_type)} · {peso(t.amount)}</Link>
                      <Badge value={t.status} />
                    </div>
                    <p className="mt-1 text-xs text-ab-muted">
                      {date(t.transaction_date)} · <Link to={`/manage/clients?id=${t.client_id}`} className="hover:underline">{text(t.client_name)}</Link>
                      {" · "}<Link to={`/manage/agents?id=${t.agent_id}`} className="hover:underline">{text(t.agent_name)}</Link> · {statusLabel(t.source)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            {(relatedClients.length > 0 || relatedAgents.length > 0) && (
              <Facts items={[
                ["Related clients", relatedClients.map(([cid, name]) => <Link key={cid} to={`/manage/clients?id=${cid}`} className="mr-2 hover:underline">{name ?? cid}</Link>)],
                ["Related agents", relatedAgents.map(([aid, name]) => <Link key={aid} to={`/manage/agents?id=${aid}`} className="mr-2 hover:underline">{name ?? aid}</Link>)],
              ]} />
            )}
            <p className="mt-3 text-xs font-semibold text-ab-faint">Documents</p>
            {history.data.documents.length === 0 ? (
              <p className="text-sm italic text-ab-faint">No documents linked to this property.</p>
            ) : (
              <ul className="mt-1 space-y-1 text-sm">
                {history.data.documents.map((d, i) => (
                  <li key={d.document_id ?? d.id ?? i} className="flex items-center justify-between gap-2">
                    <span className="truncate">{text(d.document_name)} <span className="text-xs text-ab-faint">{text(d.document_type)} · {date(d.created_at)}</span></span>
                    {d.status && <Badge value={d.status} />}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Section>

      <Section title="Record">
        <Facts items={[
          ["Listing ID", listing.listing_id],
          ["External ID", listing.external_listing_id],
          ["Sync status", statusLabel(listing.sync_status)],
          ["Last synced", listing.last_synced_at ? dateTime(listing.last_synced_at) : null],
          ["Status changed", history.data?.status_changed_at ? dateTime(history.data.status_changed_at) : null],
          ["Updated", listing.updated_at ? dateTime(listing.updated_at) : null],
        ]} />
      </Section>

      {editing && (
        <PropertyEditForm
          listing={listing}
          partners={partners}
          onClose={() => setEditing(false)}
          onSaved={(updated) => { onSaved(updated); setEditing(false); toast("Property saved.") }}
        />
      )}
      {confirmDelete && (
        <Confirm
          title="Delete property?"
          message={<>“{listing.title}” will be removed here and from the central database (Supabase). This can't be undone. Properties with recorded transactions can't be deleted.</>}
          confirmLabel="Delete"
          busy={deleting}
          onConfirm={remove}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </Drawer>
  )
}
