import { useEffect, useState } from "react"
import { Eye, EyeOff, LoaderCircle, ShieldCheck } from "lucide-react"
import { Link } from "@/components/Link"
import { ThemeToggle } from "@/components/ThemeToggle"
import { useTheme } from "@/hooks/useTheme"
import { navigate, safeNext, useLocation } from "@/lib/router"
import { useStaffAuth } from "./staffContext"
import { t } from "./i18n"

const field =
  "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2.5 text-sm text-ab-text placeholder:text-ab-faint focus:border-ab-accent focus:outline-none"

/** Staff sign-in for the web Management System (same accounts as the desktop). */
export function ManageSignIn() {
  const { user, signIn } = useStaffAuth()
  const { theme, toggleTheme } = useTheme()
  const { search } = useLocation()
  const next = safeNext(search.get("next"))
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [remember, setRemember] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (user) navigate(next?.startsWith("/manage") ? next : "/manage", { replace: true })
  }, [user, next])

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!username.trim() || !password) {
      setError(t("Please enter both username and password."))
      return
    }
    setError("")
    setBusy(true)
    try {
      await signIn(username.trim(), password, remember)
    } catch (submitError) {
      setError(t((submitError as Error).message))
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-dvh flex-col bg-ab-bg text-ab-text">
      <header className="flex items-center justify-between px-4 py-4 sm:px-8">
        <Link to="/" className="leading-tight">
          <span className="block text-base font-extrabold tracking-wide">ALTY</span>
          <span className="block text-[10px] font-semibold uppercase tracking-[0.18em] text-ab-faint">Abellar Realty</span>
        </Link>
        <ThemeToggle theme={theme} onToggle={toggleTheme} />
      </header>
      <main className="flex flex-1 items-center justify-center px-4 pb-16">
        <form onSubmit={submit} className="ab-pop w-full max-w-md rounded-2xl border border-ab-border bg-ab-card p-6 shadow-xl sm:p-8" noValidate>
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-ab-accent-soft text-ab-accent">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <h1 className="mt-4 text-2xl font-extrabold">{t("Management sign in")}</h1>
          <p className="mt-1 text-sm text-ab-muted">
            {t("For Abellar Realty staff. Use the same username and password as the desktop app.")}
          </p>

          <label className="mt-6 block text-sm font-medium" htmlFor="staff-username">{t("Username")}</label>
          <input id="staff-username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} className={field} autoFocus />

          <label className="mt-4 block text-sm font-medium" htmlFor="staff-password">{t("Password")}</label>
          <div className="relative">
            <input
              id="staff-password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={`${field} pr-11`}
            />
            <button
              type="button"
              onClick={() => setShowPassword((value) => !value)}
              aria-label={showPassword ? t("Hide password") : t("Show password")}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-ab-muted hover:text-ab-text"
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>

          <label className="mt-4 flex items-center gap-2 text-sm text-ab-muted">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="h-4 w-4 accent-[var(--color-ab-accent)]" />
            {t("Stay signed in on this computer")}
          </label>

          {error && (
            <p role="alert" className="mt-4 rounded-lg border border-ab-danger/40 bg-ab-danger/10 px-3 py-2 text-sm text-ab-danger">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-ab-accent px-4 py-3 font-semibold text-ab-ink transition hover:bg-ab-accent-hover disabled:opacity-70"
          >
            {busy && <LoaderCircle className="h-4 w-4 animate-spin" />}
            {busy ? t("Signing in…") : t("Sign In")}
          </button>
          <p className="mt-5 text-center text-xs text-ab-faint">
            {t("Looking for your client account?")} <Link to="/signin" className="font-semibold text-ab-accent hover:underline">{t("Client sign in")}</Link>
          </p>
        </form>
      </main>
    </div>
  )
}
