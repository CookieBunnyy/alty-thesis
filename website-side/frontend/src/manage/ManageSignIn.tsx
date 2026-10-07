import { useEffect, useState } from "react"
import { Eye, EyeOff, LoaderCircle } from "lucide-react"
import { Link } from "@/components/Link"
import { ThemeToggle } from "@/components/ThemeToggle"
import { API_URL } from "@/config"
import { useTheme } from "@/hooks/useTheme"
import { requestJson } from "@/lib/auth"
import { propertyImage } from "@/lib/media"
import { navigate, safeNext, useLocation } from "@/lib/router"
import type { HomeData } from "@/types"
import { EXPIRED_KEY, useStaffAuth } from "./staffContext"
import { t } from "./i18n"

const field =
  "mt-1.5 block w-full rounded-xl border border-ab-border bg-ab-input px-4 py-3 text-sm text-ab-text placeholder:text-ab-faint focus:border-ab-accent focus:outline-none"

/** A real listing photo for the picture panel (the public home page's
 *  featured listings); null until loaded, or when none has a photo. */
function useShowcasePhoto(width: number) {
  const [photo, setPhoto] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    requestJson<HomeData>(`${API_URL}/api/v1/public/home`)
      .then((home) => {
        const url = home.featured_properties.map((p) => propertyImage(p, width)).find(Boolean) ?? null
        if (alive) setPhoto(url)
      })
      .catch(() => {})
    return () => { alive = false }
  }, [width])
  return photo
}

const DESKTOP = "(min-width: 1024px)"

/** True on desktop-sized screens; follows window resizes. */
function useIsDesktop() {
  const [desktop, setDesktop] = useState(() => window.matchMedia(DESKTOP).matches)
  useEffect(() => {
    const query = window.matchMedia(DESKTOP)
    const update = () => setDesktop(query.matches)
    query.addEventListener("change", update)
    return () => query.removeEventListener("change", update)
  }, [])
  return desktop
}

function Wordmark({ light = false }: { light?: boolean }) {
  return (
    <span className="leading-tight">
      <span className={`block text-xl font-extrabold tracking-wide ${light ? "text-white" : "text-ab-text"}`}>ALTY</span>
      <span className={`block text-[10px] font-semibold uppercase tracking-[0.2em] ${light ? "text-white/80" : "text-ab-faint"}`}>Abellar Realty</span>
    </span>
  )
}

/** Staff sign-in for the web Management System (same accounts as the desktop).
 *  Desktop: form left, a property photo right. Phones: the photo on top and the
 *  form on a sheet below it. There is no sign-up: the Administrator adds staff. */
export function ManageSignIn() {
  const { user, signIn } = useStaffAuth()
  const { theme, toggleTheme } = useTheme()
  const { search } = useLocation()
  const next = safeNext(search.get("next"))
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [remember, setRemember] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [showForgot, setShowForgot] = useState(false)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [expired] = useState(() => {
    try { return window.sessionStorage.getItem(EXPIRED_KEY) === "1" } catch { return false }
  })
  const desktop = useIsDesktop()
  const photo = useShowcasePhoto(desktop ? 1400 : 900)

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

  const picture = (
    <>
      {photo ? (
        <img src={photo} alt="" className="absolute inset-0 h-full w-full object-cover" />
      ) : (
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,#5e7e00_0%,#2d3b10_45%,#151a0d_100%)]" aria-hidden />
      )}
      <div className="absolute inset-0 bg-gradient-to-b from-black/45 via-black/10 to-black/55" aria-hidden />
    </>
  )

  const form = (
    <form onSubmit={submit} className="w-full" noValidate>
      {expired && !error && (
        <p role="status" className="mb-4 rounded-xl border border-ab-warning/40 bg-ab-warning/10 px-3 py-2 text-sm text-ab-text">
          {t("Your session expired. Please sign in again.")}
        </p>
      )}
      <label className="block text-sm font-medium" htmlFor="staff-username">{t("Username")}</label>
      <input id="staff-username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)}
        className={field} placeholder={t("Your staff username")} autoFocus />

      <label className="mt-4 block text-sm font-medium" htmlFor="staff-password">{t("Password")}</label>
      <div className="relative">
        <input
          id="staff-password"
          type={showPassword ? "text" : "password"}
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={`${field} pr-12`}
          placeholder="••••••••"
        />
        <button type="button" onClick={() => setShowPassword((value) => !value)}
          aria-label={showPassword ? t("Hide password") : t("Show password")}
          className="absolute right-2.5 top-1/2 mt-[3px] -translate-y-1/2 rounded-lg p-1.5 text-ab-muted hover:text-ab-text">
          {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
        <label className="flex items-center gap-2 text-ab-muted">
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="h-4 w-4 accent-[var(--color-ab-accent)]" />
          {t("Stay signed in")}
        </label>
        <button type="button" onClick={() => setShowForgot((v) => !v)} aria-expanded={showForgot}
          className="font-semibold text-ab-accent hover:underline">
          {t("Forgot password?")}
        </button>
      </div>
      {showForgot && (
        <p role="note" className="mt-2 rounded-xl bg-ab-card-2 px-3 py-2 text-xs text-ab-muted">
          {t("Ask the Administrator to reset it in Users & Access. For security, staff passwords aren't reset by email.")}
        </p>
      )}

      {error && (
        <p role="alert" className="mt-4 rounded-xl border border-ab-danger/40 bg-ab-danger/10 px-3 py-2 text-sm text-ab-danger">{error}</p>
      )}

      <button type="submit" disabled={busy}
        className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-ab-accent px-4 py-3.5 font-semibold text-ab-ink transition hover:bg-ab-accent-hover disabled:opacity-70">
        {busy && <LoaderCircle className="h-4 w-4 animate-spin" />}
        {busy ? t("Signing in…") : t("Sign In")}
      </button>

      <p className="mt-6 text-center text-xs text-ab-faint">
        {t("Accounts are created by the Administrator.")}
        <br />
        {t("Looking for your client account?")} <Link to="/signin" className="font-semibold text-ab-accent hover:underline">{t("Client sign in")}</Link>
      </p>
    </form>
  )

  return (
    <div className="min-h-dvh bg-ab-bg text-ab-text">
      {/* ---- Phones and tablets: photo on top, form on a sheet ---- */}
      {!desktop && (
      <div className="flex min-h-dvh flex-col">
        <div className="relative h-[38vh] min-h-56 overflow-hidden">
          {picture}
          <div className="relative flex items-start justify-between p-5">
            <Link to="/"><Wordmark light /></Link>
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
          </div>
        </div>
        <main className="relative -mt-8 flex-1 rounded-t-[2rem] bg-ab-card px-6 pb-10 pt-8 shadow-[0_-12px_30px_rgba(0,0,0,0.12)]">
          <div className="mx-auto w-full max-w-md">
            <h1 className="text-center text-2xl font-extrabold">{t("Welcome back!")}</h1>
            <p className="mx-auto mt-1.5 max-w-xs text-center text-sm text-ab-muted">
              {t("Sign in to manage Abellar Realty's listings, clients and deals.")}
            </p>
            <div className="mt-7">{form}</div>
          </div>
        </main>
      </div>
      )}

      {/* ---- Desktop: form left, photo right ---- */}
      {desktop && (
      <div className="grid min-h-dvh grid-cols-[minmax(420px,1fr)_1.15fr] gap-6 p-6">
        <div className="flex flex-col">
          <div className="flex items-center justify-between px-4 pt-2">
            <Link to="/"><Wordmark /></Link>
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
          </div>
          <main className="flex flex-1 items-center justify-center px-6 py-10">
            <div className="w-full max-w-sm">
              <h1 className="text-center text-3xl font-extrabold">{t("Welcome back!")}</h1>
              <p className="mt-2 text-center text-sm text-ab-muted">
                {t("Sign in to manage Abellar Realty's listings, clients and deals.")}
              </p>
              <div className="mt-8">{form}</div>
            </div>
          </main>
        </div>
        <aside className="relative min-h-[560px] overflow-hidden rounded-[2.5rem] rounded-tl-[5rem] rounded-br-[5rem]" aria-hidden>
          {picture}
          <p className="absolute right-8 top-8 max-w-sm text-right text-xl font-bold leading-snug text-white drop-shadow">
            {t("Listings, clients, documents and deals — managed in one place.")}
          </p>
          <p className="absolute bottom-8 left-8 text-sm font-semibold text-white/90 drop-shadow">ALTY · Abellar Realty</p>
        </aside>
      </div>
      )}
    </div>
  )
}
