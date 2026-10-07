import { useCallback, useMemo, useState, type FormEvent } from "react"
import { KeyRound, LoaderCircle, Pencil, UserPlus, X } from "lucide-react"
import { contains, dateTime } from "./format"
import { Badge, Button, DataTable, LoadState, PageHeader, SearchBox, Select, Tiles, type Column } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData } from "./useApiData"
import { t } from "./i18n"

type StaffUser = { id: number; username: string; full_name: string; role: string; is_active: boolean; last_login_at: string | null; created_at: string; agent_id: string | null; agent_name: string | null }
type AgentOption = { agent_id: string; full_name: string; status: string }
type Role = { name: string; description?: string | null; permissions?: string[] } | string

const PAGE_NAMES: Record<string, string> = {
  dashboard: "Dashboard", properties: "Properties", partners: "Partners", clients: "Buyers & Sellers", transactions: "Transactions",
  documents: "Documents", media: "Digital Preview", agents: "Agents", workforce: "Workforce", analytics: "Analytics",
  forecasting: "Forecasting", dss: "Recommendations", users: "Users", audit: "Audit Logs", settings: "Settings",
}

const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"

/** Staff accounts (same users and roles as the desktop). Management roles can
 *  view; only the Administrator can add, edit or reset passwords. */
export function UsersPage() {
  const { api, user: me, signOut } = useStaffAuth()
  const toast = useToast()
  const isAdmin = me?.role === "Administrator"
  const [search, setSearch] = useState("")
  const [role, setRole] = useState("")
  const [editing, setEditing] = useState<StaffUser | "new" | null>(null)
  const [resetting, setResetting] = useState<StaffUser | null>(null)
  const [now] = useState(() => Date.now()) // "signed in within 30 days" is measured from page load
  const load = useCallback(() => Promise.all([api<StaffUser[]>("/users"), api<Role[]>("/users/roles"), api<AgentOption[]>("/agents")]), [api])
  const { data, error, loading, reload } = useApiData(load, "users")
  const [users, rawRoles, agents] = data ?? [[], [], []]
  const roles = useMemo(() => rawRoles.map((r) => (typeof r === "string" ? r : r.name)).filter((r) => r !== "Client"), [rawRoles])
  const shown = users.filter((u) => (!role || u.role === role) && contains([u.full_name, u.username, u.role], search))

  const columns: Column<StaffUser>[] = [
    {
      key: "name", label: "User", sort: (u) => u.full_name,
      render: (u) => (
        <span className="min-w-0">
          <span className="block truncate font-semibold">{u.full_name}{u.id === me?.id && <span className="ml-1.5 text-xs font-normal text-ab-faint">({t("you")})</span>}</span>
          <span className="block truncate text-xs text-ab-faint">@{u.username}</span>
        </span>
      ),
    },
    {
      key: "role", label: "Role", sort: (u) => u.role,
      render: (u) => (
        <span>
          {t(u.role)}
          {u.agent_id && <span className="block text-xs text-ab-faint">{t("Agent record:")} {u.agent_name ?? u.agent_id}</span>}
        </span>
      ),
    },
    { key: "status", label: "Status", sort: (u) => String(u.is_active), render: (u) => <Badge value={u.is_active ? "ACTIVE" : "INACTIVE"} /> },
    { key: "login", label: "Last sign-in", sort: (u) => u.last_login_at ?? "", render: (u) => (u.last_login_at ? dateTime(u.last_login_at) : t("Never")) },
    { key: "created", label: "Created", sort: (u) => u.created_at, render: (u) => dateTime(u.created_at), hideOnPhone: true },
    ...(isAdmin ? [{
      key: "actions", label: "", render: (u: StaffUser) => (
        <span className="flex justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
          <button type="button" onClick={() => setEditing(u)} className="rounded-lg border border-ab-border p-1.5 hover:bg-ab-hover" aria-label={t("Edit {name}", { name: u.full_name })} title={t("Edit")}><Pencil className="h-3.5 w-3.5" /></button>
          <button type="button" onClick={() => setResetting(u)} className="rounded-lg border border-ab-border p-1.5 hover:bg-ab-hover" aria-label={t("Reset password for {name}", { name: u.full_name })} title={t("Reset password")}><KeyRound className="h-3.5 w-3.5" /></button>
        </span>
      ),
    } satisfies Column<StaffUser>] : []),
  ]

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageHeader
        title="Who can sign in, and what they can open"
        subtitle="Staff accounts for the desktop app and the web Management System — one account works in both. Each role opens only its permitted pages."
        actions={isAdmin && <Button variant="primary" onClick={() => setEditing("new")}><UserPlus className="h-4 w-4" /> {t("New user")}</Button>}
      />
      {data && (
        <Tiles items={[
          { label: "Staff accounts", value: users.length, onClick: () => setRole(""), active: !role },
          { label: "Active", value: users.filter((u) => u.is_active).length },
          { label: "Inactive", value: users.filter((u) => !u.is_active).length },
          { label: "Signed in (30 days)", value: users.filter((u) => u.last_login_at && now - new Date(u.last_login_at).getTime() < 30 * 86400000).length },
        ]} />
      )}
      <div className="flex flex-wrap gap-2 sm:flex-nowrap">
        <div className="w-full sm:w-auto sm:flex-1"><SearchBox value={search} onChange={setSearch} placeholder="Search name, username or role" /></div>
        <Select label="Role" value={role} onChange={setRole} options={[{ value: "", label: "All roles" }, ...roles.map((r) => ({ value: r, label: r }))]} />
      </div>
      {!isAdmin && <p className="text-xs text-ab-faint">{t("Only the Administrator can add users, change roles or reset passwords.")}</p>}
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && <DataTable rows={shown} columns={columns} rowKey={(u) => String(u.id)} empty="No users match these filters." initialSort={{ key: "name", dir: "asc" }} />}

      {data && (
        <section className="rounded-2xl border border-ab-border bg-ab-card p-4">
          <h2 className="mb-3 text-xs font-bold uppercase tracking-[0.14em] text-ab-faint">{t("Roles & permissions")}</h2>
          <ul className="grid gap-3 md:grid-cols-2">
            {rawRoles.filter((r): r is Exclude<Role, string> => typeof r !== "string" && r.name !== "Client").map((r) => (
              <li key={r.name} className="rounded-xl border border-ab-border p-3 text-sm">
                <p className="font-semibold">{t(r.name)} <span className="font-normal text-ab-faint">· {t("{n} user(s)", { n: users.filter((u) => u.role === r.name).length })}</span></p>
                {r.description && <p className="text-xs text-ab-muted">{t(r.description)}</p>}
                <p className="mt-1.5 flex flex-wrap gap-1">
                  {(r.permissions ?? []).map((p) => <span key={p} className="rounded-full bg-ab-card-2 px-2 py-0.5 text-[11px] text-ab-muted">{t(PAGE_NAMES[p] ?? p)}</span>)}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {editing && (
        <UserForm
          user={editing === "new" ? null : editing}
          roles={roles}
          agents={agents}
          takenAgents={new Map(users.filter((u) => u.agent_id && (editing === "new" || u.id !== editing.id)).map((u) => [u.agent_id!, u.username]))}
          onClose={() => setEditing(null)}
          onSaved={(saved, changedOwnAccess) => {
            setEditing(null)
            toast(t(editing === "new" ? "Created {name}." : "Updated {name}.", { name: saved.full_name }))
            // Your own role or status changed: sign in again so permissions are reloaded.
            if (changedOwnAccess) signOut()
            else void reload()
          }}
        />
      )}
      {resetting && <ResetPassword user={resetting} onClose={() => setResetting(null)} onDone={() => { setResetting(null); toast(t("Password reset for {name}.", { name: resetting.full_name })) }} />}
    </div>
  )
}

function UserForm({ user, roles, agents, takenAgents, onClose, onSaved }: {
  user: StaffUser | null; roles: string[]; agents: AgentOption[]; takenAgents: Map<string, string>
  onClose: () => void; onSaved: (u: StaffUser, changedOwnAccess: boolean) => void
}) {
  const { api, user: me } = useStaffAuth()
  const [form, setForm] = useState({ username: "", full_name: user?.full_name ?? "", role: user?.role ?? roles.find((r) => r === "Employee") ?? roles[0] ?? "", is_active: user?.is_active ?? true, password: "", confirm: "", agent_id: user?.agent_id ?? "" })
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }))

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError("")
    if (!form.full_name.trim()) return setError(t("Enter the full name."))
    if (!user) {
      if (form.username.trim().length < 3) return setError(t("Username must be at least 3 characters."))
      if (form.password.length < 8) return setError(t("Password must be at least 8 characters."))
      if (form.password !== form.confirm) return setError(t("The passwords don't match."))
    }
    setBusy(true)
    try {
      const saved = user
        ? await api<StaffUser>(`/users/${user.id}`, { method: "PUT", body: JSON.stringify({ full_name: form.full_name.trim(), role: form.role, is_active: form.is_active, agent_id: form.agent_id || null }) })
        : await api<StaffUser>("/users", { method: "POST", body: JSON.stringify({ username: form.username.trim(), full_name: form.full_name.trim(), role: form.role, is_active: form.is_active, password: form.password, agent_id: form.agent_id || null }) })
      onSaved(saved, Boolean(user && user.id === me?.id && (user.role !== saved.role || !saved.is_active)))
    } catch (saveError) {
      setError((saveError as Error).message)
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={user ? t("Edit user") : t("New user")}>
      <button type="button" aria-label={t("Cancel")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={submit} noValidate className="ab-pop relative w-full max-w-md rounded-t-2xl border border-ab-border bg-ab-card shadow-2xl sm:rounded-2xl">
        <header className="flex items-center justify-between border-b border-ab-border px-5 py-4">
          <h2 className="text-lg font-bold">{user ? t("Edit {name}", { name: user.full_name }) : t("New user")}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close")} className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><X className="h-4 w-4" /></button>
        </header>
        <div className="space-y-3 p-5">
          {user ? <p className="text-sm text-ab-muted">{t("Username:")} <span className="font-semibold text-ab-text">@{user.username}</span></p> : (
            <label className="block text-sm font-medium">{t("Username")}<input className={field} autoComplete="off" value={form.username} onChange={(e) => set("username", e.target.value)} /></label>
          )}
          <label className="block text-sm font-medium">{t("Full name")}<input className={field} value={form.full_name} onChange={(e) => set("full_name", e.target.value)} /></label>
          <label className="block text-sm font-medium">{t("Role")}
            <select className={field} value={form.role} onChange={(e) => set("role", e.target.value)}>
              {roles.map((r) => <option key={r} value={r}>{t(r)}</option>)}
            </select>
          </label>
          <label className="block text-sm font-medium">{t("Linked agent record")}
            <select className={field} value={form.agent_id} onChange={(e) => set("agent_id", e.target.value)}>
              <option value="">{t("None (not an agent)")}</option>
              {agents.map((a) => (
                <option key={a.agent_id} value={a.agent_id} disabled={takenAgents.has(a.agent_id)}>
                  {a.full_name} ({a.agent_id}){takenAgents.has(a.agent_id) ? ` — ${t("linked to @{user}", { user: takenAgents.get(a.agent_id) })}` : ""}
                </option>
              ))}
            </select>
            <span className="mt-1 block text-xs font-normal text-ab-faint">{t("For agents: their “My Work” page shows this agent record's clients, transactions and reviews.")}</span>
          </label>
          {!user && (
            <>
              <label className="block text-sm font-medium">{t("Password")}<input type="password" autoComplete="new-password" className={field} value={form.password} onChange={(e) => set("password", e.target.value)} /></label>
              <label className="block text-sm font-medium">{t("Confirm password")}<input type="password" autoComplete="new-password" className={field} value={form.confirm} onChange={(e) => set("confirm", e.target.value)} /></label>
              <p className="text-xs text-ab-faint">{t("At least 8 characters. Share it with the person privately; they can sign in to the desktop app or the website.")}</p>
            </>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} className="h-4 w-4 accent-[var(--color-ab-accent)]" />
            {t("Active (can sign in)")}
          </label>
          {user?.id === me?.id && <p className="text-xs text-ab-warning">{t("This is your own account. Changing your role or deactivating it signs you out.")}</p>}
          {error && <p role="alert" className="rounded-lg border border-ab-danger/40 bg-ab-danger/10 px-3 py-2 text-sm text-ab-danger">{error}</p>}
        </div>
        <footer className="flex justify-end gap-2 border-t border-ab-border px-5 py-3">
          <Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button>
          <Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {user ? t("Save") : t("Create user")}</Button>
        </footer>
      </form>
    </div>
  )
}

function ResetPassword({ user, onClose, onDone }: { user: StaffUser; onClose: () => void; onDone: () => void }) {
  const { api } = useStaffAuth()
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (password.length < 8) return setError(t("Password must be at least 8 characters."))
    if (password !== confirm) return setError(t("The passwords don't match."))
    setBusy(true)
    try {
      await api(`/users/${user.id}/reset-password`, { method: "POST", body: JSON.stringify({ password }) })
      onDone()
    } catch (resetError) {
      setError((resetError as Error).message)
      setBusy(false)
    }
  }
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={t("Reset password")}>
      <button type="button" aria-label={t("Cancel")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={submit} noValidate className="ab-pop relative w-full max-w-sm rounded-2xl border border-ab-border bg-ab-card p-5 shadow-2xl">
        <h2 className="text-lg font-bold">{t("Reset password")}</h2>
        <p className="mt-1 text-sm text-ab-muted">{t("New password for {name} (@{user}).", { name: user.full_name, user: user.username })}</p>
        <label className="mt-4 block text-sm font-medium">{t("New password")}<input type="password" autoComplete="new-password" className={field} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        <label className="mt-3 block text-sm font-medium">{t("Confirm")}<input type="password" autoComplete="new-password" className={field} value={confirm} onChange={(e) => setConfirm(e.target.value)} /></label>
        {error && <p role="alert" className="mt-3 text-sm text-ab-danger">{error}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button>
          <Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Reset password")}</Button>
        </div>
      </form>
    </div>
  )
}

