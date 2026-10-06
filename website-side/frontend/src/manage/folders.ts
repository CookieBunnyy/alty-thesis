import type { Folder } from "./UploadDocument"

export type FolderIndex = {
  /** "Buyers / Michael Santos" for each active folder. */
  path: Map<number, string>
  /** Active child folders by parent (null = top level), in server order. */
  children: Map<number | null, Folder[]>
  /** A folder and everything inside it. */
  within: (id: number) => Set<number>
  /** Select options, sorted by path. */
  options: { value: string; label: string }[]
}

export function indexFolders(folders: Folder[]): FolderIndex {
  const active = folders.filter((f) => !f.is_archived)
  const byId = new Map(active.map((f) => [f.id, f]))
  const children = new Map<number | null, Folder[]>()
  for (const f of active) {
    const parent = f.parent_id != null && byId.has(f.parent_id) ? f.parent_id : null
    children.set(parent, [...(children.get(parent) ?? []), f])
  }
  const path = new Map<number, string>()
  const walk = (parent: number | null, prefix: string) => {
    for (const f of children.get(parent) ?? []) {
      if (path.has(f.id)) continue
      const own = prefix ? `${prefix} / ${f.name}` : f.name
      path.set(f.id, own)
      walk(f.id, own)
    }
  }
  walk(null, "")
  const within = (id: number) => {
    const found = new Set([id])
    const stack = [id]
    while (stack.length) {
      for (const c of children.get(stack.pop()!) ?? []) {
        if (!found.has(c.id)) { found.add(c.id); stack.push(c.id) }
      }
    }
    return found
  }
  const options = [...path].sort((a, b) => a[1].localeCompare(b[1])).map(([id, label]) => ({ value: String(id), label }))
  return { path, children, within, options }
}
