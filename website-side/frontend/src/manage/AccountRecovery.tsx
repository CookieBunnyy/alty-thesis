import { useEffect, useState, type FormEvent } from "react"
import { CheckCircle2, Eye, EyeOff, LoaderCircle, MailCheck } from "lucide-react"
import { Link } from "@/components/Link"
import { Turnstile } from "@/components/Turnstile"
import { authRequest, formatWait, useCountdown, useSecurityConfig } from "./authRequests"
import { t } from "./i18n"

const field =
  "mt-1.5 block w-full rounded-xl border border-ab-border bg-ab-input px-4 py-3 text-sm text-ab-text placeholder:text-ab-faint focus:border-ab-accent focus:outline-none"
const primary =
  "mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-ab-accent px-4 py-3.5 font-semibold text-ab-ink transition hover:bg-ab-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
const RESEND_AFTER = 60

function Alert({ tone, children }: { tone: "error" | "info" | "success"; children: React.ReactNode }) {
  const tones = {
    error: "border-ab-danger/40 bg-ab-danger/10 text-ab-danger",
    info: "border-ab-warning/40 bg-ab-warning/10 text-ab-text",
    success: "border-ab-accent/40 bg-ab-accent-soft text-ab-text",
  }
  return <p role={tone === "error" ? "alert" : "status"} className={`mt-4 rounded-xl border px-3 py-2 text-sm ${tones[tone]}`}>{children}</p>
}

const BackToSignIn = () => (
  <p className="mt-6 text-center text-sm">
    <Link to="/manage/signin" className="font-semibold text-ab-accent hover:underline">{t("Back to sign in")}</Link>
  </p>
)

/** "Forgot password?": a reset link to the account's registered email. The
 *  answer is the same whether or not the address belongs to an account. */
export function ForgotPasswordForm() {
  const config = useSecurityConfig()
  const [email, setEmail] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [sent, setSent] = useState(false)
  const [cooldown, startCooldown] = useCountdown()
  const [needsCheck, setNeedsCheck] = useState(false)
  const [captcha, setCaptcha] = useState<string | null>(null)
  const [checkRound, setCheckRound] = useState(0)

  const send = async (event?: FormEvent) => {
    event?.preventDefault()
    setError("")
    if (!EMAIL.test(email.trim())) return setError(t("Enter a valid email address."))
    if (needsCheck && !captcha) return setError(t("Complete the security check first."))
    setBusy(true)
    const reply = await authRequest("/password-reset/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.trim(), ...(captcha ? { captcha_token: captcha } : {}) }),
    })
    setBusy(false)
    if (needsCheck) setCheckRound((n) => n + 1) // a check token works once
    if (reply.ok) {
      setSent(true)
      startCooldown(RESEND_AFTER)
      return
    }
    if (reply.captchaRequired) {
      setNeedsCheck(true)
      setError(t("Complete the security check, then try again."))
    } else if (reply.status === 429) {
      setError(t("Too many requests. Please wait a while and try again."))
      startCooldown(Math.max(reply.retryAfter, RESEND_AFTER))
    } else if (reply.status === 503) {
      setError(t("Password recovery isn't available. Ask the Administrator to reset it."))
    } else if (reply.status === 0) {
      setError(t("Can't reach the server. Check your connection and try again."))
    } else {
      setError(t("Something went wrong. Please try again."))
    }
  }

  if (config && !config.password_reset_enabled) {
    return (
      <div>
        <Alert tone="info">{t("Ask the Administrator to reset it in Users & Access.")}</Alert>
        <BackToSignIn />
      </div>
    )
  }

  if (sent) {
    return (
      <div className="text-center">
        <MailCheck className="mx-auto h-10 w-10 text-ab-accent" aria-hidden />
        <p role="status" className="mt-3 text-sm text-ab-text">
          {t("If that email belongs to a staff account, we've sent it a link to reset the password. Check the inbox and the spam folder.")}
        </p>
        <p className="mt-2 text-xs text-ab-faint">
          {t("The link works once and expires in {minutes} minutes.", { minutes: config?.password_reset_minutes ?? 20 })}
        </p>
        {error && <Alert tone="error">{error}</Alert>}
        {needsCheck && config?.captcha_site_key && <Turnstile siteKey={config.captcha_site_key} onToken={setCaptcha} resetKey={checkRound} unavailableText={t("The security check couldn't load. Check your connection and reload the page.")} />}
        <button type="button" onClick={() => void send()} disabled={busy || cooldown > 0}
          className="mt-5 inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-ab-border-strong px-4 text-sm font-semibold hover:bg-ab-hover disabled:cursor-not-allowed disabled:opacity-60">
          {busy && <LoaderCircle className="h-4 w-4 animate-spin" />}
          {cooldown > 0 ? t("Send again in {time}", { time: formatWait(cooldown) }) : t("Send the link again")}
        </button>
        <BackToSignIn />
      </div>
    )
  }

  return (
    <form onSubmit={send} noValidate>
      <label className="block text-sm font-medium" htmlFor="reset-email">{t("Registered email")}</label>
      <input id="reset-email" type="email" autoComplete="email" inputMode="email" value={email}
        onChange={(e) => setEmail(e.target.value)} className={field} placeholder="name@example.com" autoFocus />
      <p className="mt-2 text-xs text-ab-faint">{t("The email the Administrator registered for your staff account.")}</p>
      {needsCheck && config?.captcha_site_key && <Turnstile siteKey={config.captcha_site_key} onToken={setCaptcha} resetKey={checkRound} unavailableText={t("The security check couldn't load. Check your connection and reload the page.")} />}
      {error && <Alert tone="error">{error}</Alert>}
      <button type="submit" disabled={busy || cooldown > 0} className={primary}>
        {busy && <LoaderCircle className="h-4 w-4 animate-spin" />}
        {busy ? t("Sending…") : cooldown > 0 ? t("Try again in {time}", { time: formatWait(cooldown) }) : t("Send reset link")}
      </button>
      <BackToSignIn />
    </form>
  )
}

/** Reads the token from the link (#token=…) once, then removes it from the
 *  address bar and history so it isn't left behind or shared by accident. */
function useLinkToken(): string | null {
  const [token] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get("token"))
  useEffect(() => {
    if (window.location.hash) window.history.replaceState(null, "", window.location.pathname)
  }, [])
  return token
}

/** The page the reset link opens: choose a new password. */
export function ResetPasswordForm() {
  const token = useLinkToken()
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [linkBroken, setLinkBroken] = useState(!token)
  const [done, setDone] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError("")
    if (password.length < 8) return setError(t("Password must be at least 8 characters."))
    if (password !== confirm) return setError(t("The passwords don't match."))
    setBusy(true)
    const reply = await authRequest("/password-reset/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, new_password: password }),
    })
    setBusy(false)
    if (reply.ok) {
      setDone(true)
      setPassword("")
      setConfirm("")
    } else if (reply.status === 400) {
      setLinkBroken(true)
    } else if (reply.status === 422) {
      setError(t("Password must be at least 8 characters."))
    } else if (reply.status === 429) {
      setError(t("Too many attempts. Please wait a while and try again."))
    } else if (reply.status === 0) {
      setError(t("Can't reach the server. Check your connection and try again."))
    } else {
      setError(t("Something went wrong. Please try again."))
    }
  }

  if (done) {
    return (
      <div className="text-center">
        <CheckCircle2 className="mx-auto h-10 w-10 text-ab-accent" aria-hidden />
        <p role="status" className="mt-3 text-sm">{t("Your password was changed. Every device signed in to your account was signed out.")}</p>
        <Link to="/manage/signin" className={primary}>{t("Sign in with the new password")}</Link>
      </div>
    )
  }
  if (linkBroken) {
    return (
      <div>
        <Alert tone="error">{t("This reset link is invalid or has expired. Request a new one.")}</Alert>
        <Link to="/manage/forgot-password" className={primary}>{t("Request a new link")}</Link>
        <BackToSignIn />
      </div>
    )
  }
  return (
    <form onSubmit={submit} noValidate>
      <label className="block text-sm font-medium" htmlFor="new-password">{t("New password")}</label>
      <div className="relative">
        <input id="new-password" type={show ? "text" : "password"} autoComplete="new-password" value={password}
          onChange={(e) => setPassword(e.target.value)} className={`${field} pr-12`} autoFocus />
        <button type="button" onClick={() => setShow((value) => !value)} aria-label={show ? t("Hide password") : t("Show password")}
          className="absolute right-2.5 top-1/2 mt-[3px] -translate-y-1/2 rounded-lg p-1.5 text-ab-muted hover:text-ab-text">
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
      <label className="mt-4 block text-sm font-medium" htmlFor="confirm-password">{t("Confirm new password")}</label>
      <input id="confirm-password" type={show ? "text" : "password"} autoComplete="new-password" value={confirm}
        onChange={(e) => setConfirm(e.target.value)} className={field} />
      <p className="mt-2 text-xs text-ab-faint">{t("At least 8 characters.")}</p>
      {error && <Alert tone="error">{error}</Alert>}
      <button type="submit" disabled={busy} className={primary}>
        {busy && <LoaderCircle className="h-4 w-4 animate-spin" />}
        {busy ? t("Saving…") : t("Set new password")}
      </button>
      <BackToSignIn />
    </form>
  )
}
