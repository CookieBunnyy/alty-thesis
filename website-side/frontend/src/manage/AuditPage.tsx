import { useCallback, useEffect, useState } from "react"
import { ChevronLeft, ChevronRight, Download } from "lucide-react"
import { Link } from "@/components/Link"
import { dateTime, statusLabel } from "./format"
import { Badge, Button, DataTable, Drawer, Facts, LoadState, PageHeader, SearchBox, Section, Select, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"
import { t } from "./i18n"

type Event = { id: number; timestamp: string; actor: string; actor_id: number | null; action: string; entity_type: string | null; entity_id: string | null; result: string; details: Record<string, unknown> }
type Page = { total: number; items: Event[] }

const PAGE_SIZE = 50
const ENTITY_PAGES: Record<string, string> = { property_listings: "/manage/properties", clients: "/manage/clients", transactions: "/manage/transactions", agents: "/manage/agents", documents: "/manage/documents" }

/** Who did what, when (Administrator only, like the desktop). Filtering and
 *  paging happen on the server, over the whole log. */
export function AuditPage() {
  const { api } = useStaffAuth()
  const [search, setSearch] = useState("")
  const [query, setQuery] = useState("")
  const [action, setAction] = useState("")
  const [result, setResult] = useState("")
  const [since, setSince] = useState("")
  const [until, setUntil] = useState("")
  const [offset, setOffset] = useState(0)
  const [open, setOpen] = useState<Event | null>(null)
  const [exporting, setExporting] = useState(false)

  // Search after typing pauses, not on every key.
  useEffect(() => {
    const timer = window.setTimeout(() => { setQuery(search.trim()); setOffset(0) }, 350)
    return () => window.clearTimeout(timer)
  }, [search])

  const params = useCallback((limit: number, from: number) => {
    const p = new URLSearchParams({ limit: String(limit), offset: String(from) })
    if (query) p.set("search", query)
    if (action) p.set("action", action)
    if (result) p.set("result", result)
    if (since) p.set("since", `${since}T00:00:00`)
    if (until) p.set("until", `${until}T23:59:59`)
    return p.toString()
  }, [query, action, result, since, until])

  const load = useCallback(() => Promise.all([api<Page>(`/audit?${params(PAGE_SIZE, offset)}`), api<string[]>("/audit/actions")]), [api, params, offset])
  const { data, error, loading, reload } = useApiData(load)
  const [page, actions] = data ?? [{ total: 0, items: [] }, []]

  const exportCsv = async () => {
    setExporting(true)
    try {
      const all = await api<Page>(`/audit?${params(1000, 0)}`)
      const quote = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`
      const lines = [["Time", "Actor", "Action", "Entity", "Entity ID", "Result", "Details"].map((h) => t(h)).join(","),
        ...all.items.map((e) => [e.timestamp, e.actor, e.action, e.entity_type, e.entity_id, e.result, JSON.stringify(e.details)].map(quote).join(","))]
      const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }))
      const link = Object.assign(document.createElement("a"), { href: url, download: `alty-audit-${new Date().toLocaleDateString("en-CA")}.csv` })
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } finally {
      setExporting(false)
    }
  }

  const columns: Column<Event>[] = [
    { key: "time", label: "Time", render: (e) => <span className="whitespace-nowrap">{dateTime(e.timestamp)}</span> },
    { key: "actor", label: "Actor", render: (e) => <span className="font-semibold">{e.actor}</span> },
    { key: "action", label: "Action", render: (e) => statusLabel(e.action) },
    { key: "entity", label: "Record", render: (e) => (e.entity_type ? `${statusLabel(e.entity_type)}${e.entity_id ? ` · ${e.entity_id.length > 12 ? e.entity_id.slice(0, 8) : e.entity_id}` : ""}` : "—"), hideOnPhone: true },
    { key: "result", label: "Result", render: (e) => <Badge value={e.result} /> },
  ]
  const reset = () => { setSearch(""); setAction(""); setResult(""); setSince(""); setUntil(""); setOffset(0) }

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        title="Audit Logs"
        subtitle="Every sign-in, record change, document action and sync, from the desktop app and the website. Entries can't be edited or deleted."
        actions={<Button onClick={exportCsv} disabled={exporting || !page.total}><Download className="h-4 w-4" /> {exporting ? t("Exporting…") : t("Export CSV")}</Button>}
      />
      <div className="flex flex-wrap items-end gap-2">
        <div className="w-full md:w-auto md:flex-1"><SearchBox value={search} onChange={setSearch} placeholder="Search action, actor or record ID" /></div>
        <Select label="Action" value={action} onChange={(v) => { setAction(v); setOffset(0) }} options={[{ value: "", label: "All actions" }, ...actions.map((a) => ({ value: a, label: statusLabel(a) }))]} />
        <Select label="Result" value={result} onChange={(v) => { setResult(v); setOffset(0) }} options={[{ value: "", label: "Any result" }, { value: "SUCCESS", label: "Success" }, { value: "FAILED", label: "Failed" }]} />
        <label className="text-xs text-ab-faint">{t("From")}<input type="date" value={since} onChange={(e) => { setSince(e.target.value); setOffset(0) }} className="ml-1 min-h-10 rounded-xl border border-ab-border bg-ab-input px-2 text-sm text-ab-text" /></label>
        <label className="text-xs text-ab-faint">{t("To")}<input type="date" value={until} onChange={(e) => { setUntil(e.target.value); setOffset(0) }} className="ml-1 min-h-10 rounded-xl border border-ab-border bg-ab-input px-2 text-sm text-ab-text" /></label>
        {(search || action || result || since || until) && <Button onClick={reset}>{t("Clear")}</Button>}
      </div>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <>
          <DataTable rows={page.items} columns={columns} rowKey={(e) => String(e.id)} onOpen={setOpen} empty="No audit entries match these filters." />
          <div className="flex items-center justify-between text-sm text-ab-muted">
            <span>{page.total ? t("{from}–{to} of {total}", { from: offset + 1, to: Math.min(offset + PAGE_SIZE, page.total), total: page.total }) : t("0 entries")}</span>
            <span className="flex gap-2">
              <Button onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} disabled={offset === 0 || loading}><ChevronLeft className="h-4 w-4" /> {t("Newer")}</Button>
              <Button onClick={() => setOffset(offset + PAGE_SIZE)} disabled={offset + PAGE_SIZE >= page.total || loading}>{t("Older")} <ChevronRight className="h-4 w-4" /></Button>
            </span>
          </div>
        </>
      )}
      {open && (
        <Drawer title={statusLabel(open.action)} subtitle={<span className="flex items-center gap-2"><Badge value={open.result} /> {dateTime(open.timestamp)}</span>} onClose={() => setOpen(null)}>
          <Section title="Entry">
            <Facts items={[
              ["Actor", open.actor],
              ["Record type", open.entity_type ? statusLabel(open.entity_type) : null],
              ["Record ID", open.entity_id && open.entity_type && ENTITY_PAGES[open.entity_type] && open.action !== "PROPERTY_DELETED" && open.action !== "CLIENT_DELETED" && open.action !== "DOCUMENT_DELETED"
                ? <Link to={`${ENTITY_PAGES[open.entity_type]}?id=${encodeURIComponent(open.entity_id)}`} className="break-all font-mono text-xs hover:underline">{open.entity_id}</Link>
                : open.entity_id ? <span className="break-all font-mono text-xs">{open.entity_id}</span> : null],
              ["Entry #", open.id],
            ]} />
          </Section>
          <Section title="Details">
            {Object.keys(open.details ?? {}).length ? (
              <pre className="max-h-[50vh] overflow-auto whitespace-pre-wrap break-words rounded-xl bg-ab-card-2 p-3 text-xs">{JSON.stringify(open.details, null, 2)}</pre>
            ) : <p className="text-sm italic text-ab-faint">{t("No extra details recorded.")}</p>}
          </Section>
        </Drawer>
      )}
    </div>
  )
}
