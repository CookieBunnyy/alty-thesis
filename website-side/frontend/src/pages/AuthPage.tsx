import { useEffect, useState } from "react"
import { Eye, EyeOff, LoaderCircle } from "lucide-react"
import { useAuth, type ApiError } from "@/lib/auth"
import { Turnstile } from "@/components/Turnstile"
import { formatWait, useCountdown, useSecurityConfig } from "@/manage/authRequests"
import { EXPIRED_KEY } from "@/manage/staffContext"
import { staffSignIn } from "@/manage/staffToken"
import { Link } from "@/components/Link"
import { navigate, safeNext, useLocation } from "@/lib/router"
import { SiteHeader } from "@/components/SiteHeader"
import { FeatureBackdrop } from "@/components/HomeHero"

const field =
  "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2.5 text-sm text-ab-text placeholder:text-ab-faint focus:border-ab-accent focus:outline-none"

/** The one Sign In page, for buyers and Abellar staff, and buyers' Sign Up.
 *  An email signs a buyer in (back to `?next=` or their account); a username
 *  signs staff in to the Management System (with the security check and the
 *  cooldown the staff sign-in uses). */
export function AuthPage({ mode }: { mode: "signin" | "signup" }) {
  const { search } = useLocation()
  const { client, signIn, signUp } = useAuth()
  const next = safeNext(search.get("next"))
  const [form, setForm] = useState({ full_name: "", email: "", phone_number: "", location: "", password: "", confirm: "" })
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const isSignUp = mode === "signup"
  const config = useSecurityConfig()
  const [remember, setRemember] = useState(false)
  const [needsCheck, setNeedsCheck] = useState(false)
  const [captcha, setCaptcha] = useState<string | null>(null)
  const [checkRound, setCheckRound] = useState(0)
  const [cooldown, startCooldown] = useCountdown()
  const [expired] = useState(() => {
    try { return window.sessionStorage.getItem(EXPIRED_KEY) === "1" } catch { return false }
  })

  useEffect(() => {
    if (client) navigate(next ?? "/account", { replace: true })
  }, [client, next])

  const set = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }))

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError("")
    if (isSignUp && form.password !== form.confirm) {
      setError("The passwords don't match.")
      return
    }
    setBusy(true)
    try {
      if (isSignUp) {
        await signUp({
          full_name: form.full_name.trim(),
          email: form.email.trim(),
          phone_number: form.phone_number.trim(),
          location: form.location.trim() || undefined,
          password: form.password,
        })
      } else if (form.email.includes("@")) {
        await signIn(form.email.trim(), form.password)
      } else {
        // A username: Abellar staff, into the Management System.
        if (needsCheck && !captcha) {
          setError("Complete the security check first.")
          setBusy(false)
          return
        }
        await staffSignIn(form.email.trim(), form.password, remember, captcha)
        navigate(next?.startsWith("/manage") ? next : "/manage", { replace: true })
      }
    } catch (submitError) {
      const failure = submitError as ApiError
      const info = (failure.detail ?? {}) as { captchaRequired?: boolean; retryAfter?: number }
      if (!isSignUp && !form.email.includes("@")) {
        if (needsCheck) setCheckRound((n) => n + 1) // a check token works once
        if (info.captchaRequired) setNeedsCheck(true)
        if (failure.status === 429) {
          startCooldown(info.retryAfter || 60)
          setError("Too many sign-in attempts. Please wait before trying again.")
        } else if (failure.status === 401) {
          setError(failure.message === "Complete the security check, then sign in again." ? failure.message : "Incorrect username or password.")
        } else {
          setError(failure.message || "Something went wrong. Please try again.")
        }
      } else {
        setError(failure.message)
      }
      setBusy(false)
    }
  }

  const switchTo = `${isSignUp ? "/signin" : "/signup"}${next ? `?next=${encodeURIComponent(next)}` : ""}`

  return (
    <div className="flex min-h-dvh flex-col bg-ab-bg text-ab-text">
      <SiteHeader />
      {/* The site's features float behind the form, purely as decoration. */}
      <main className="hero-panel relative flex flex-1 items-center justify-center overflow-hidden px-4 pb-32 pt-36 sm:py-40 xl:py-12">
        <FeatureBackdrop />
        <div className="ab-pop relative z-10 w-full max-w-md rounded-3xl border border-ab-border bg-ab-card p-6 shadow-xl sm:p-8">
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-ab-accent">{isSignUp ? "Buyer account" : "Abellar Realty"}</p>
          <h1 className="mt-1 text-2xl font-extrabold">{isSignUp ? "Create your account" : "Welcome back"}</h1>
          <p className="mt-1 text-sm text-ab-muted">
            {isSignUp
              ? "Follow your transactions and rate your agent."
              : "Buyers sign in with their email. Abellar staff sign in with their username."}
          </p>
          {expired && !isSignUp && !error && (
            <p role="status" className="mt-4 rounded-xl border border-ab-warning/40 bg-ab-warning/10 px-3 py-2 text-sm">Your session expired. Please sign in again.</p>
          )}

          <form onSubmit={submit} className="mt-6 space-y-4">
            {isSignUp && (
              <label className="block text-sm font-medium text-ab-muted">
                Full name
                <input required minLength={2} autoComplete="name" value={form.full_name} onChange={set("full_name")} className={field} />
              </label>
            )}
            <label className="block text-sm font-medium text-ab-muted">
              {isSignUp ? "Email" : "Email or username"}
              <input required type={isSignUp ? "email" : "text"} autoComplete={isSignUp ? "email" : "username"} autoCapitalize="none"
                spellCheck={false} value={form.email} onChange={set("email")} className={field} />
            </label>
            {isSignUp && (
              <>
                <label className="block text-sm font-medium text-ab-muted">
                  Phone number
                  <input required type="tel" autoComplete="tel" minLength={7} value={form.phone_number} onChange={set("phone_number")} placeholder="0917 123 4567" className={field} />
                </label>
                <label className="block text-sm font-medium text-ab-muted">
                  Address / city <span className="text-ab-faint">(optional)</span>
                  <input autoComplete="address-level2" value={form.location} onChange={set("location")} className={field} />
                </label>
              </>
            )}
            <div className="text-sm font-medium text-ab-muted">
              <label htmlFor="auth-password">Password</label>
              <span className="relative block">
                <input
                  id="auth-password"
                  required
                  minLength={isSignUp ? 8 : 1}
                  type={showPassword ? "text" : "password"}
                  autoComplete={isSignUp ? "new-password" : "current-password"}
                  value={form.password}
                  onChange={set("password")}
                  aria-describedby={isSignUp ? "password-hint" : undefined}
                  className={`${field} pr-11`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((shown) => !shown)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-ab-muted hover:bg-ab-hover"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </span>
              {isSignUp && <span id="password-hint" className="mt-1 block text-xs text-ab-faint">At least 8 characters.</span>}
            </div>
            {isSignUp && (
              <label className="block text-sm font-medium text-ab-muted">
                Confirm password
                <input required type={showPassword ? "text" : "password"} autoComplete="new-password" value={form.confirm} onChange={set("confirm")} className={field} />
              </label>
            )}

            {!isSignUp && (
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <label className="flex items-center gap-2 text-ab-muted">
                  <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="h-4 w-4 accent-[var(--color-ab-accent)]" />
                  Stay signed in
                </label>
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  <Link to="/forgot-password" className="font-semibold text-ab-accent hover:underline">Buyer: forgot password?</Link>
                  <Link to="/manage/forgot-password" className="font-semibold text-ab-accent hover:underline">Staff: forgot password?</Link>
                </div>
              </div>
            )}
            {!isSignUp && needsCheck && config?.captcha_site_key && (
              <Turnstile siteKey={config.captcha_site_key} onToken={setCaptcha} resetKey={checkRound}
                unavailableText="The security check couldn't load. Check your connection and reload the page." />
            )}

            {error && <p role="alert" className="rounded-xl border border-ab-danger/40 bg-ab-danger/10 px-3 py-2 text-sm text-ab-danger">{error}</p>}

            <button type="submit" disabled={busy || cooldown > 0} className="flex w-full items-center justify-center gap-2 rounded-xl bg-ab-accent px-4 py-3 font-bold text-ab-ink transition hover:bg-ab-accent-hover disabled:opacity-60">
              {busy && <LoaderCircle className="h-4 w-4 animate-spin" />}
              {isSignUp ? "Create account" : cooldown > 0 ? `Try again in ${formatWait(cooldown)}` : "Sign In"}
            </button>
          </form>

          <p className="mt-5 text-center text-sm text-ab-muted">
            {isSignUp ? "Already have an account?" : "Buying a home? New here?"}{" "}
            <Link to={switchTo} className="font-semibold text-ab-accent hover:underline">
              {isSignUp ? "Sign in" : "Create an account"}
            </Link>
          </p>
        </div>
      </main>
    </div>
  )
}
