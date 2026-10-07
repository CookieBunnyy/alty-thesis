import { useState, type ReactNode } from "react"
import { ChevronRight, Folder as FolderIcon, FolderOpen } from "lucide-react"
import type { FolderIndex } from "./folders"
import { t } from "./i18n"

/** Nested folder list. Counts include sub-folders; category folders start
 *  open, per-person folders (filed automatically) are folded under them. */
export function FolderTree({ index, counts, total, selected, onSelect }: {
  index: FolderIndex; counts: Map<number, number>; total: number
  selected: number | null; onSelect: (id: number | null) => void
}) {
  const [open, setOpen] = useState<Set<number>>(() => new Set((index.children.get(null) ?? []).map((f) => f.id)))
  const toggle = (id: number) => setOpen((s) => {
    const next = new Set(s)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })

  const row = (id: number | null, name: string, count: number, depth: number, hasChildren: boolean) => {
    const active = selected === id
    const expanded = id != null && open.has(id)
    const Icon = active ? FolderOpen : FolderIcon
    return (
      <div className="flex items-center" style={{ paddingLeft: depth * 14 }}>
        {hasChildren && id != null ? (
          <button type="button" onClick={() => toggle(id)} aria-expanded={expanded} aria-label={t(expanded ? "Collapse {name}" : "Expand {name}", { name })}
            className="grid h-7 w-6 shrink-0 place-items-center rounded text-ab-faint hover:text-ab-text">
            <ChevronRight className={`h-3.5 w-3.5 transition-transform ${expanded ? "rotate-90" : ""}`} />
          </button>
        ) : <span className="w-6 shrink-0" />}
        <button
          type="button"
          onClick={() => { onSelect(id); if (id != null && hasChildren && !expanded) toggle(id) }}
          aria-pressed={active}
          className={`flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-left ${active ? "bg-ab-hover font-semibold text-ab-text" : "text-ab-muted hover:bg-ab-hover hover:text-ab-text"}`}
        >
          <Icon className={`h-4 w-4 shrink-0 ${active ? "text-ab-accent" : ""}`} />
          <span className="flex-1 truncate" title={id != null ? index.path.get(id) : undefined}>{name}</span>
          <span className="text-xs tabular-nums text-ab-faint">{count}</span>
        </button>
      </div>
    )
  }

  const branch = (parent: number | null, depth: number): ReactNode =>
    (index.children.get(parent) ?? []).map((f) => {
      const kids = index.children.get(f.id) ?? []
      return (
        <li key={f.id}>
          {row(f.id, f.name, counts.get(f.id) ?? 0, depth, kids.length > 0)}
          {kids.length > 0 && open.has(f.id) && <ul>{branch(f.id, depth + 1)}</ul>}
        </li>
      )
    })

  return (
    <ul className="space-y-0.5 text-sm">
      <li>{row(null, t("All documents"), total, 0, false)}</li>
      {branch(null, 0)}
    </ul>
  )
}
