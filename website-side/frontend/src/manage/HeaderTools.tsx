// Management header: global search and the notification bell — the same
// /search and /notifications endpoints the desktop header uses.
import { useCallback, useEffect, useRef, useState } from "react"
import { AlertTriangle, Bell, CheckCheck, CircleCheck, Info, LoaderCircle, Search, X } from "lucide-react"
import { navigate } from "@/lib/router"
import { useStaffAuth } from "./staffContext"
import { t } from "./i18n"

const PAGE_PATHS: Record<string, string> = {
  dashboard: "/manage", properties: "/manage/properties", clients: "/manage/clients", transactions: "/manage/transactions",
  agents: "/manage/agents", documents: "/manage/documents", partners: "/manage/partners", media: "/manage/media", analytics: "/manage/analytics",
  forecasting: "/manage/forecasting", dss: "/manage/insights", workforce: "/manage/workforce", users: "/manage/users",
  audit: "/manage/audit", settings: "/manage/settings",
}

/** Close a popover on outside click or Escape. */
function useDismiss(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && close()
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close()
    document.addEventListener("mousedown", onDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [open, close])
  return ref
}

type Result = { id: string; title: string; subtitle: string; page: string }
type SearchResponse = { total: number; results: Record<string, Result[]> }
const GROUP_LABELS: Record<string, string> = { properties: "Properties", clients: "Buyers & Sellers", transactions: "Transactions", agents: "Agents", documents: "Documents", partners: "Partners / Developers" }

export function GlobalSearch({ className = "hidden w-full max-w-md md:block" }: { className?: string }) {
  const { api, can } = useStaffAuth()
  const [query, setQuery] = useState("")
  const [data, setData] = useState<SearchResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(false)
  const close = useCallback(() => setOpen(false), [])
  const ref = useDismiss(open, close)

  useEffect(() => {
    const q = query.trim()
    if (q.length < 2) return
    const timer = window.setTimeout(() => {
      setBusy(true)
      api<SearchResponse>(`/search?q=${encodeURIComponent(q)}&limit=5`)
        .then((r) => { setData(r); setOpen(true) })
        .catch(() => setData(null))
        .finally(() => setBusy(false))
    }, 300)
    return () => window.clearTimeout(timer)
  }, [query, api])

  const groups = Object.entries(data?.results ?? {}).filter(([page, items]) => items.length && can(page))
  const go = (r: Result) => {
    setOpen(false)
    setQuery("")
    setData(null)
    navigate(`${PAGE_PATHS[r.page] ?? "/manage"}?id=${encodeURIComponent(r.id)}`)
  }

  return (
    <div ref={ref} className={`relative ${className}`}>
      <label className="relative block">
        <span className="sr-only">{t("Search all records")}</span>
        {busy ? <LoaderCircle className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-ab-accent" />
          : <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ab-faint" />}
        <input
          type="search"
          value={query}
          onChange={(e) => { setQuery(e.target.value); if (e.target.value.trim().length < 2) setOpen(false) }}
          onFocus={() => data && query.trim().length >= 2 && setOpen(true)}
          placeholder={t("Search properties, clients, transactions, agents, documents…")}
          className="min-h-10 w-full rounded-xl border border-ab-border bg-ab-input pl-9 pr-3 text-sm placeholder:text-ab-faint focus:border-ab-accent focus:outline-none"
        />
      </label>
      {open && data && (
        <div className="ab-pop absolute left-0 right-0 top-[calc(100%+6px)] z-50 max-h-[70vh] overflow-y-auto rounded-2xl border border-ab-border-strong bg-ab-card p-2 shadow-2xl" role="listbox" aria-label={t("Search results")}>
          {groups.length === 0 ? <p className="px-3 py-4 text-sm text-ab-muted">{t("No matches for “{query}”.", { query: query.trim() })}</p> : groups.map(([page, items]) => (
            <div key={page} className="py-1">
              <p className="px-3 pb-1 text-[10px] font-bold uppercase tracking-[0.16em] text-ab-faint">{t(GROUP_LABELS[page] ?? page)}</p>
              {items.map((r) => (
                <button key={`${page}-${r.id}`} type="button" role="option" aria-selected={false} onClick={() => go(r)} className="block w-full rounded-lg px-3 py-2 text-left hover:bg-ab-hover">
                  <span className="block truncate text-sm font-semibold">{r.title}</span>
                  <span className="block truncate text-xs text-ab-faint">{r.subtitle}</span>
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

type Notice = { key: string; category: string; severity: "danger" | "warning" | "success" | "info"; title: string; message: string; created_at: string | null; page: string | null; read: boolean }
type Notices = { items: Notice[]; unread: number }
const NOTICE_ICON = { danger: AlertTriangle, warning: AlertTriangle, success: CircleCheck, info: Info } as const
const NOTICE_TONE = { danger: "text-ab-danger", warning: "text-ab-warning", success: "text-ab-success", info: "text-ab-info" } as const

function ago(iso: string | null): string {
  if (!iso) return ""
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000))
  return minutes < 1 ? t("just now") : minutes < 60 ? t("{n}m ago", { n: minutes }) : minutes < 1440 ? t("{n}h ago", { n: Math.round(minutes / 60) }) : t("{n}d ago", { n: Math.round(minutes / 1440) })
}

export function NotificationBell() {
  const { api } = useStaffAuth()
  const [data, setData] = useState<Notices | null>(null)
  const [open, setOpen] = useState(false)
  const [unreadOnly, setUnreadOnly] = useState(false)
  const close = useCallback(() => setOpen(false), [])
  const ref = useDismiss(open, close)
  const load = useCallback(() => api<Notices>("/notifications").then(setData).catch(() => {}), [api])

  useEffect(() => {
    // Fetch now and every minute (the desktop bell refreshes on the same cadence).
    void load()
    const timer = window.setInterval(() => void load(), 60000)
    return () => window.clearInterval(timer)
  }, [load])

  const openNotice = async (n: Notice) => {
    if (!n.read) await api<Notices>("/notifications/read", { method: "POST", body: JSON.stringify({ keys: [n.key] }) }).then(setData).catch(() => {})
    setOpen(false)
    const [kind, id] = n.key.split(":")
    const base = PAGE_PATHS[n.page ?? ""] ?? "/manage"
    navigate(kind === "transaction" && id ? `${base}?id=${id}` : base)
  }
  const unread = data?.unread ?? 0
  const items = (data?.items ?? []).filter((n) => !unreadOnly || !n.read)

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-label={unread ? t("Notifications, {n} unread", { n: unread }) : t("Notifications")} aria-expanded={open}
        className="relative rounded-lg border border-ab-border-strong p-2 text-ab-muted hover:bg-ab-hover hover:text-ab-text">
        <Bell className="h-4 w-4" />
        {unread > 0 && (
          <span className="absolute -right-1.5 -top-1.5 min-w-5 rounded-full bg-ab-accent px-1 text-center text-[10px] font-extrabold leading-5 text-ab-ink">{unread > 99 ? "99+" : unread}</span>
        )}
      </button>
      {open && (
        <div className="ab-pop fixed inset-x-3 top-16 z-50 flex max-h-[75vh] flex-col rounded-2xl border border-ab-border-strong bg-ab-card shadow-2xl sm:absolute sm:inset-x-auto sm:right-0 sm:top-[calc(100%+8px)] sm:w-96" role="dialog" aria-label={t("Notifications")}>
          <div className="flex items-center justify-between gap-2 border-b border-ab-border px-4 py-3">
            <p className="font-bold">{t("Notifications")} {unread > 0 && <span className="ml-1 rounded-full bg-ab-accent px-2 text-xs text-ab-ink">{unread}</span>}</p>
            <span className="flex items-center gap-1">
              <button type="button" disabled={!unread} onClick={() => api<Notices>("/notifications/read-all", { method: "POST" }).then(setData).catch(() => {})}
                className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-ab-accent hover:bg-ab-hover disabled:text-ab-faint">
                <CheckCheck className="h-3.5 w-3.5" /> {t("Mark all read")}
              </button>
              <button type="button" onClick={close} aria-label={t("Close")} className="rounded-lg p-1.5 text-ab-muted hover:bg-ab-hover sm:hidden"><X className="h-4 w-4" /></button>
            </span>
          </div>
          <div className="flex gap-1 px-4 pt-2 text-xs">
            {[["All", false], ["Unread", true]].map(([label, value]) => (
              <button key={String(label)} type="button" aria-pressed={unreadOnly === value} onClick={() => setUnreadOnly(Boolean(value))}
                className={`rounded-lg px-2.5 py-1 font-semibold ${unreadOnly === value ? "bg-ab-hover text-ab-text" : "text-ab-muted"}`}>{t(label as string)}</button>
            ))}
          </div>
          <ul className="flex-1 space-y-1 overflow-y-auto p-2">
            {!data ? <li className="p-4 text-center"><LoaderCircle className="mx-auto h-5 w-5 animate-spin text-ab-accent" /></li>
              : items.length === 0 ? <li className="p-6 text-center text-sm text-ab-muted">{t("You're all caught up.")}</li>
              : items.map((n) => {
                const Icon = NOTICE_ICON[n.severity] ?? Info
                return (
                  <li key={n.key}>
                    <button type="button" onClick={() => void openNotice(n)} className={`flex w-full gap-3 rounded-xl p-3 text-left hover:bg-ab-hover ${n.read ? "" : "bg-ab-card-2"}`}>
                      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${NOTICE_TONE[n.severity] ?? "text-ab-info"}`} aria-hidden />
                      <span className="min-w-0 flex-1">
                        <span className="flex items-start justify-between gap-2">
                          <span className="text-sm font-semibold">{t(n.title)}</span>
                          <span className="shrink-0 text-[11px] text-ab-faint">{ago(n.created_at)}</span>
                        </span>
                        <span className="mt-0.5 block text-xs text-ab-muted">{n.message}</span>
                      </span>
                      {!n.read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-ab-accent" aria-label={t("Unread")} />}
                    </button>
                  </li>
                )
              })}
          </ul>
          <p className="border-t border-ab-border px-4 py-2 text-[11px] text-ab-faint">{t("Generated from system records · read status is shared with the desktop app")}</p>
        </div>
      )}
    </div>
  )
}
