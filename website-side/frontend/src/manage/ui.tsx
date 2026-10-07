// Building blocks for the management pages: page header, summary tiles,
// search/filter bar, a sortable data table that becomes cards on phones, a
// detail drawer, confirm dialog and status badges. Labels passed to these
// components (titles, column names, filter options…) are translated here.
import { useEffect, useMemo, useState, type ReactNode } from "react"
import { AlertTriangle, ArrowDown, ArrowUp, ChevronRight, Inbox, LoaderCircle, Search, X } from "lucide-react"
import { statusLabel } from "./format"
import { t } from "./i18n"

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h2 className="text-xl font-extrabold leading-tight sm:text-2xl">{t(title)}</h2>
        {subtitle && <p className="mt-1 line-clamp-3 max-w-3xl text-xs text-ab-muted sm:line-clamp-none sm:text-sm">{t(subtitle)}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

export function Button({ children, onClick, variant = "secondary", disabled, type = "button", title }: {
  children: ReactNode; onClick?: () => void; variant?: "primary" | "secondary" | "danger"; disabled?: boolean; type?: "button" | "submit"; title?: string
}) {
  const style = {
    primary: "bg-ab-accent text-ab-ink hover:bg-ab-accent-hover border-transparent",
    secondary: "border-ab-border-strong text-ab-text hover:bg-ab-hover",
    danger: "border-ab-danger/50 text-ab-danger hover:bg-ab-danger/10",
  }[variant]
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`inline-flex min-h-10 items-center justify-center gap-1.5 rounded-xl border px-3.5 text-sm font-semibold transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 ${style}`}
    >
      {children}
    </button>
  )
}

// Static class names (Tailwind can't see computed ones): one row on wide screens.
const XL_COLUMNS: Record<number, string> = { 3: "xl:grid-cols-3", 4: "xl:grid-cols-4", 5: "xl:grid-cols-5", 6: "xl:grid-cols-6" }

export function Tiles({ items }: { items: { label: string; value: ReactNode; detail?: ReactNode; onClick?: () => void; active?: boolean }[] }) {
  return (
    <div className={`grid grid-cols-2 gap-2 sm:gap-3 md:grid-cols-3 ${XL_COLUMNS[items.length] ?? "xl:grid-cols-5"}`}>
      {items.map((item) => {
        const body = (
          <>
            <p className="text-xs font-semibold text-ab-muted">{t(item.label)}</p>
            <p className="mt-1 text-xl font-extrabold tabular-nums text-ab-text sm:mt-1.5 sm:text-2xl">{item.value}</p>
            {item.detail && <p className="mt-0.5 text-xs text-ab-faint">{typeof item.detail === "string" ? t(item.detail) : item.detail}</p>}
          </>
        )
        const cls = `rounded-2xl border bg-ab-card p-3 text-left sm:p-4 ${item.active ? "border-ab-accent" : "border-ab-border"}`
        return item.onClick ? (
          <button key={item.label} type="button" onClick={item.onClick} aria-pressed={item.active} className={`${cls} transition hover:border-ab-border-strong`}>
            {body}
          </button>
        ) : (
          <div key={item.label} className={cls}>{body}</div>
        )
      })}
    </div>
  )
}

export function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <label className="relative block min-w-0 flex-1">
      <span className="sr-only">{t(placeholder)}</span>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ab-faint" />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={t(placeholder)}
        className="min-h-10 w-full rounded-xl border border-ab-border bg-ab-input pl-9 pr-3 text-sm placeholder:text-ab-faint focus:border-ab-accent focus:outline-none"
      />
    </label>
  )
}

export function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <label className="block">
      <span className="sr-only">{t(label)}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-10 rounded-xl border border-ab-border bg-ab-input px-3 text-sm focus:border-ab-accent focus:outline-none"
      >
        {options.map((o) => <option key={o.value} value={o.value}>{t(o.label)}</option>)}
      </select>
    </label>
  )
}

const BADGE: Record<string, string> = {
  AVAILABLE: "bg-ab-success/15 text-ab-success",
  ACTIVE: "bg-ab-success/15 text-ab-success",
  COMPLETED: "bg-ab-success/15 text-ab-success",
  SYNCED: "bg-ab-success/15 text-ab-success",
  SOLD: "bg-ab-info/15 text-ab-info",
  RESERVED: "bg-ab-accent/15 text-ab-accent",
  PROSPECT: "bg-ab-warning/15 text-ab-warning",
  ON_HOLD: "bg-ab-warning/15 text-ab-warning",
  PENDING: "bg-ab-warning/15 text-ab-warning",
  CANCELLED: "bg-ab-danger/15 text-ab-danger",
  FAILED: "bg-ab-danger/15 text-ab-danger",
  UNAVAILABLE: "bg-ab-hover text-ab-muted",
  INACTIVE: "bg-ab-hover text-ab-muted",
}

export function Badge({ value }: { value: unknown }) {
  const key = String(value ?? "").toUpperCase()
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ${BADGE[key] ?? "bg-ab-hover text-ab-muted"}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {statusLabel(value)}
    </span>
  )
}

export type Column<T> = {
  key: string
  label: string
  render: (row: T) => ReactNode
  /** Value used for sorting; columns without it aren't sortable. */
  sort?: (row: T) => string | number | null | undefined
  align?: "right"
  /** Hidden in the phone card view (keep cards short). */
  hideOnPhone?: boolean
}

/** Sortable table; on phones each row becomes a card (title + label/value pairs). */
export function DataTable<T>({ rows, columns, rowKey, onOpen, empty, initialSort }: {
  rows: T[]; columns: Column<T>[]; rowKey: (row: T) => string; onOpen?: (row: T) => void; empty: string
  initialSort?: { key: string; dir: "asc" | "desc" }
}) {
  const [sort, setSort] = useState(initialSort ?? null)
  const sorted = useMemo(() => {
    const column = columns.find((c) => c.key === sort?.key)
    if (!sort || !column?.sort) return rows
    const factor = sort.dir === "asc" ? 1 : -1
    return [...rows].sort((a, b) => {
      const x = column.sort!(a)
      const y = column.sort!(b)
      if (x == null && y == null) return 0
      if (x == null) return 1
      if (y == null) return -1
      return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))) * factor
    })
  }, [rows, columns, sort])

  if (!rows.length) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-ab-border px-4 py-14 text-center text-sm text-ab-muted">
        <Inbox className="h-6 w-6 text-ab-faint" /> {t(empty)}
      </div>
    )
  }
  const [first, ...rest] = columns
  return (
    <>
      <ul className="space-y-2 md:hidden">
        {sorted.map((row) => (
          <li key={rowKey(row)}>
            {/* A card is a button only when it opens something (it may hold its own buttons otherwise). */}
            <PhoneCard onOpen={onOpen ? () => onOpen(row) : undefined}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">{first.render(row)}</div>
                {onOpen && <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-ab-faint" />}
              </div>
              <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
                {rest.filter((c) => !c.hideOnPhone).map((c) => (
                  <div key={c.key} className="min-w-0">
                    <dt className="text-ab-faint">{t(c.label)}</dt>
                    <dd className="truncate text-ab-text">{c.render(row)}</dd>
                  </div>
                ))}
              </dl>
            </PhoneCard>
          </li>
        ))}
      </ul>
      <div className="ab-table-scroll hidden rounded-2xl border border-ab-border bg-ab-card md:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-ab-border text-[11px] uppercase tracking-wide text-ab-faint">
              {columns.map((c) => {
                const active = sort?.key === c.key
                const canSort = Boolean(c.sort)
                return (
                  <th key={c.key} scope="col" aria-sort={active ? (sort!.dir === "asc" ? "ascending" : "descending") : undefined}
                    className={`whitespace-nowrap px-4 py-3 font-semibold ${c.align === "right" ? "text-right" : ""}`}>
                    {canSort ? (
                      <button
                        type="button"
                        onClick={() => setSort(active && sort!.dir === "asc" ? { key: c.key, dir: "desc" } : { key: c.key, dir: "asc" })}
                        className={`inline-flex items-center gap-1 uppercase hover:text-ab-text ${active ? "text-ab-text" : ""}`}
                      >
                        {t(c.label)}
                        {active && (sort!.dir === "asc" ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />)}
                      </button>
                    ) : t(c.label)}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr
                key={rowKey(row)}
                onClick={() => onOpen?.(row)}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onOpen && (e.preventDefault(), onOpen(row))}
                tabIndex={onOpen ? 0 : undefined}
                className={`border-b border-ab-border last:border-0 ${onOpen ? "cursor-pointer hover:bg-ab-hover focus:bg-ab-hover focus:outline-none" : ""}`}
              >
                {columns.map((c) => (
                  <td key={c.key} className={`px-4 py-3 align-middle ${c.align === "right" ? "text-right tabular-nums" : ""}`}>{c.render(row)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function PhoneCard({ onOpen, children }: { onOpen?: () => void; children: ReactNode }) {
  const cls = "w-full rounded-2xl border border-ab-border bg-ab-card p-4 text-left"
  return onOpen
    ? <button type="button" onClick={onOpen} className={`${cls} transition hover:border-ab-border-strong`}>{children}</button>
    : <div className={cls}>{children}</div>
}

export function LoadState({ loading, error, onRetry }: { loading: boolean; error: string; onRetry: () => void }) {
  if (error) {
    return (
      <p role="alert" className="flex items-center gap-2 rounded-xl border border-ab-danger/40 bg-ab-danger/10 px-4 py-3 text-sm text-ab-danger">
        <AlertTriangle className="h-4 w-4 shrink-0" /> {error}
        <button type="button" onClick={onRetry} className="ml-auto font-semibold underline">{t("Try again")}</button>
      </p>
    )
  }
  if (loading) {
    return (
      <div className="space-y-2" aria-busy="true" aria-label={t("Loading")}>
        {Array.from({ length: 6 }, (_, i) => <div key={i} className="ab-skeleton h-14 rounded-xl" />)}
      </div>
    )
  }
  return null
}

/** Side panel for one record (full screen on phones). Esc closes. */
export function Drawer({ title, subtitle, onClose, children, footer }: { title: ReactNode; subtitle?: ReactNode; onClose: () => void; children: ReactNode; footer?: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose()
    window.addEventListener("keydown", onKey)
    const overflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      window.removeEventListener("keydown", onKey)
      document.body.style.overflow = overflow
    }
  }, [onClose])
  return (
    <div className="fixed inset-0 z-[60]" role="dialog" aria-modal="true">
      <button type="button" aria-label={t("Close")} className="absolute inset-0 bg-black/50 backdrop-blur-[2px]" onClick={onClose} />
      <section className="ab-drawer absolute inset-y-0 right-0 flex w-full max-w-2xl flex-col border-l border-ab-border bg-ab-bg shadow-2xl">
        <header className="flex items-start justify-between gap-3 border-b border-ab-border bg-ab-sidebar px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-bold">{title}</h2>
            {subtitle && <div className="mt-0.5 text-sm text-ab-muted">{subtitle}</div>}
          </div>
          <button type="button" onClick={onClose} aria-label={t("Close")} className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover">
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="flex-1 space-y-4 overflow-y-auto p-5">{children}</div>
        {footer && <footer className="flex flex-wrap justify-end gap-2 border-t border-ab-border bg-ab-sidebar px-5 py-3">{footer}</footer>}
      </section>
    </div>
  )
}

export function Section({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="rounded-2xl border border-ab-border bg-ab-card p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-xs font-bold uppercase tracking-[0.14em] text-ab-faint">{t(title)}</h3>
        {action}
      </div>
      {children}
    </section>
  )
}

/** Label/value grid; empty values read "Not provided". */
export function Facts({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-4 gap-y-2.5 text-sm sm:grid-cols-2">
      {items.map(([label, value]) => (
        <div key={label} className="min-w-0">
          <dt className="text-xs text-ab-faint">{t(label)}</dt>
          <dd className={`break-words ${value === null || value === undefined || value === "" || value === "—" ? "italic text-ab-faint" : "font-medium"}`}>
            {value === null || value === undefined || value === "" || value === "—" ? t("Not provided") : value}
          </dd>
        </div>
      ))}
    </dl>
  )
}

/** Confirmation dialog. With ``typeToConfirm`` (used for every delete), the
 *  person must type that word exactly before the action is enabled. */
export function Confirm({ title, message, confirmLabel, onConfirm, onCancel, busy, typeToConfirm }: {
  title: string; message: ReactNode; confirmLabel: string; onConfirm: () => void; onCancel: () => void; busy?: boolean
  typeToConfirm?: string
}) {
  const [typed, setTyped] = useState("")
  const ready = !typeToConfirm || typed === typeToConfirm
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onCancel()
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [busy, onCancel])
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" role="alertdialog" aria-modal="true" aria-label={t(title)}>
      <button type="button" aria-label={t("Cancel")} className="absolute inset-0 bg-black/55" onClick={onCancel} />
      <form
        className="ab-pop relative w-full max-w-md rounded-2xl border border-ab-border bg-ab-card p-6 shadow-2xl"
        onSubmit={(e) => { e.preventDefault(); if (ready && !busy) onConfirm() }}
      >
        <h2 className="text-lg font-bold">{t(title)}</h2>
        <div className="mt-2 text-sm text-ab-muted">{typeof message === "string" ? t(message) : message}</div>
        {typeToConfirm && (
          <label className="mt-4 block text-sm font-medium">
            {t("Type {word} to confirm", { word: typeToConfirm })}
            <input
              autoFocus
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              placeholder={typeToConfirm}
              aria-invalid={typed !== "" && !ready}
              className="mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm placeholder:text-ab-faint focus:border-ab-danger focus:outline-none"
            />
          </label>
        )}
        <div className="mt-6 flex justify-end gap-2">
          <Button onClick={onCancel} disabled={busy}>{t("Cancel")}</Button>
          <Button type="submit" variant="danger" disabled={busy || !ready}>
            {busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t(confirmLabel)}
          </Button>
        </div>
      </form>
    </div>
  )
}
