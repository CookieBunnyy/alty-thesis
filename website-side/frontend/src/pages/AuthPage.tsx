import { useEffect, useState } from "react"
import { Eye, EyeOff, LoaderCircle } from "lucide-react"
import { useAuth } from "@/lib/auth"
import { Link } from "@/components/Link"
import { navigate, safeNext, useLocation } from "@/lib/router"
import { SiteHeader } from "@/components/SiteHeader"

const field =
  "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2.5 text-sm text-ab-text placeholder:text-ab-faint focus:border-ab-accent focus:outline-none"

/** Client Sign In / Sign Up. After success, returns to `?next=` (e.g. the
 *  property and action the visitor was attempting), else the account page. */
export function AuthPage({ mode }: { mode: "signin" | "signup" }) {
  const { search } = useLocation()
  const { client, signIn, signUp } = useAuth()
  const next = safeNext(search.get("next"))
  const [form, setForm] = useState({ full_name: "", email: "", phone_number: "", location: "", password: "", confirm: "" })
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const isSignUp = mode === "signup"

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
      } else {
        await signIn(form.email.trim(), form.password)
      }
    } catch (submitError) {
      setError((submitError as Error).message)
      setBusy(false)
    }
  }

  const switchTo = `${isSignUp ? "/signin" : "/signup"}${next ? `?next=${encodeURIComponent(next)}` : ""}`

  return (
    <div className="flex min-h-dvh flex-col bg-ab-bg text-ab-text">
      <SiteHeader />
      <main className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="ab-pop w-full max-w-md rounded-3xl border border-ab-border bg-ab-card p-6 shadow-xl sm:p-8">
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-ab-accent">Client account</p>
          <h1 className="mt-1 text-2xl font-extrabold">{isSignUp ? "Create your account" : "Welcome back"}</h1>
          <p className="mt-1 text-sm text-ab-muted">
            {isSignUp
              ? "Follow your transactions and rate your agent."
              : "Sign in to your Abellar Realty client account."}
          </p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            {isSignUp && (
              <label className="block text-sm font-medium text-ab-muted">
                Full name
                <input required minLength={2} autoComplete="name" value={form.full_name} onChange={set("full_name")} className={field} />
              </label>
            )}
            <label className="block text-sm font-medium text-ab-muted">
              Email
              <input required type="email" autoComplete="email" value={form.email} onChange={set("email")} className={field} />
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

            {error && <p role="alert" className="rounded-xl border border-ab-danger/40 bg-ab-danger/10 px-3 py-2 text-sm text-ab-danger">{error}</p>}

            <button type="submit" disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-xl bg-ab-accent px-4 py-3 font-bold text-ab-ink transition hover:bg-ab-accent-hover disabled:opacity-60">
              {busy && <LoaderCircle className="h-4 w-4 animate-spin" />}
              {isSignUp ? "Create account" : "Sign In"}
            </button>
          </form>

          <p className="mt-5 text-center text-sm text-ab-muted">
            {isSignUp ? "Already have an account?" : "New to Abellar Realty?"}{" "}
            <Link to={switchTo} className="font-semibold text-ab-accent hover:underline">
              {isSignUp ? "Sign in" : "Create an account"}
            </Link>
          </p>
        </div>
      </main>
    </div>
  )
}
