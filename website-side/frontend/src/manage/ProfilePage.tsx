import { useState, type FormEvent } from "react"
import { LoaderCircle, LogOut, Settings } from "lucide-react"
import { Link } from "@/components/Link"
import { ThemeToggle } from "@/components/ThemeToggle"
import { useTheme } from "@/hooks/useTheme"
import { PhotoControls, StaffAvatar } from "./avatars"
import { dateTime } from "./format"
import { t } from "./i18n"
import { photoBody } from "./photoBody"
import { Button, Facts, PageHeader, Section } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"

// Page keys -> names (same as the sidebar).
const PAGE_NAMES: Record<string, string> = {
  dashboard: "Dashboard", properties: "Properties", clients: "Buyers & Sellers", transactions: "Transactions",
  agents: "Agents", partners: "Partners / Developers", analytics: "Analytics", forecasting: "Business Outlook",
  dss: "Recommendations", media: "Digital Preview", documents: "Document Repository", workforce: "Workforce",
  users: "Users & Access", audit: "Audit Logs", settings: "Settings",
}

const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2.5 text-sm focus:border-ab-accent focus:outline-none"

/** The signed-in staff member's own account: photo, details, password. */
export function ProfilePage() {
  const { user, api, reloadUser, signOut } = useStaffAuth()
  const { theme, toggleTheme } = useTheme()
  const toast = useToast()
  if (!user) return null
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageHeader title="Your account, photo and password" />

      <section className="flex flex-col items-center gap-4 rounded-2xl border border-ab-border bg-ab-card p-6 text-center sm:flex-row sm:text-left">
        <StaffAvatar userId={user.id} name={user.full_name} version={user.photo_version} size="lg" />
        <div className="min-w-0 flex-1">
          <p className="text-xl font-extrabold">{user.full_name}</p>
          <p className="text-sm text-ab-muted">{t(user.role)} · @{user.username}</p>
          <div className="mt-3 flex justify-center sm:justify-start">
            <PhotoControls
              hasPhoto={Boolean(user.photo_version)}
              onUpload={async (file) => {
                try {
                  await api("/users/me/photo", { method: "PUT", body: photoBody(file) })
                  await reloadUser()
                  toast(t("Profile picture updated."))
                } catch (uploadError) { toast(t((uploadError as Error).message), "error") }
              }}
              onRemove={async () => {
                try {
                  await api("/users/me/photo", { method: "DELETE" })
                  await reloadUser()
                  toast(t("Profile picture removed."))
                } catch (removeError) { toast(t((removeError as Error).message), "error") }
              }}
            />
          </div>
        </div>
      </section>

      <Section title="Account">
        <Facts items={[
          ["Username", `@${user.username}`],
          ["Email", user.email ?? t("Not set — ask the Administrator (needed for “Forgot password”)")],
          ["Role", t(user.role)],
          ["Linked agent record", user.agent_id ? <Link to="/manage/my-work" className="hover:underline">{user.agent_id} · {t("My Work")}</Link> : null],
          ["Last sign-in", user.last_login_at ? dateTime(user.last_login_at) : null],
        ]} />
        <p className="mt-4 text-xs font-semibold text-ab-faint">{t("Pages you can open")}</p>
        <p className="mt-1.5 flex flex-wrap gap-1.5">
          {user.permissions.map((key) => (
            <span key={key} className="rounded-full bg-ab-card-2 px-2.5 py-1 text-xs text-ab-muted">{t(PAGE_NAMES[key] ?? key)}</span>
          ))}
        </p>
      </Section>

      <ChangePassword />

      <Section title="Preferences">
        <div className="flex flex-wrap items-center gap-3">
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
          <span className="text-sm text-ab-muted">{t(theme === "dark" ? "Dark mode" : "Light mode")}</span>
          <Link to="/manage/settings" className="ml-auto inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-ab-border-strong px-3.5 text-sm font-semibold hover:bg-ab-hover">
            <Settings className="h-4 w-4" /> {t("Language and other settings")}
          </Link>
        </div>
      </Section>

      <button type="button" onClick={signOut}
        className="flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl border border-ab-danger/50 text-sm font-semibold text-ab-danger hover:bg-ab-danger/10">
        <LogOut className="h-4 w-4" /> {t("Sign out")}
      </button>
    </div>
  )
}

function ChangePassword() {
  const { api, replaceToken } = useStaffAuth()
  const toast = useToast()
  const [form, setForm] = useState({ current: "", next: "", confirm: "" })
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value }))
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError("")
    if (!form.current) return setError(t("Enter your current password."))
    if (form.next.length < 8) return setError(t("Password must be at least 8 characters."))
    if (form.next !== form.confirm) return setError(t("The passwords don't match."))
    setBusy(true)
    try {
      const session = await api<{ access_token: string }>("/auth/change-password", { method: "POST", body: JSON.stringify({ current_password: form.current, new_password: form.next }) })
      replaceToken(session.access_token) // this session continues; every other one ends
      setForm({ current: "", next: "", confirm: "" })
      toast(t("Password changed. Other devices signed in to your account were signed out."))
    } catch (changeError) {
      setError(t((changeError as Error).message))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Section title="Change password">
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-3" noValidate>
        <label className="text-sm font-medium">{t("Current password")}
          <input type="password" autoComplete="current-password" className={field} value={form.current} onChange={set("current")} />
        </label>
        <label className="text-sm font-medium">{t("New password")}
          <input type="password" autoComplete="new-password" className={field} value={form.next} onChange={set("next")} />
        </label>
        <label className="text-sm font-medium">{t("Confirm new password")}
          <input type="password" autoComplete="new-password" className={field} value={form.confirm} onChange={set("confirm")} />
        </label>
        {error && <p role="alert" className="text-sm text-ab-danger sm:col-span-3">{error}</p>}
        <div className="sm:col-span-3">
          <Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Change password")}</Button>
          <span className="ml-3 text-xs text-ab-faint">{t("At least 8 characters.")}</span>
        </div>
      </form>
    </Section>
  )
}
