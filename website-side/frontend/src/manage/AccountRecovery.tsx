import { useCallback, useEffect, useState, type FormEvent } from "react"
import { CheckCircle2, Clock, Eye, EyeOff, LoaderCircle, MailCheck, ShieldCheck, XCircle } from "lucide-react"
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

  if (config && !config.password_reset_enabled && config.password_reset_mode === "admin") return <AdminApprovalRequest />
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

/** The page the reset link opens (or an approved request): choose a new password. */
export function ResetPasswordForm({ approvedToken, onDone }: { approvedToken?: string; onDone?: () => void } = {}) {
  const linkToken = useLinkToken()
  const token = approvedToken ?? linkToken
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
      onDone?.()
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
    if (approvedToken) {
      return (
        <div>
          <Alert tone="error">{t("This approval has expired or was already used. Send a new request.")}</Alert>
          <button type="button" onClick={onDone} className={primary}>{t("Send a new request")}</button>
          <BackToSignIn />
        </div>
      )
    }
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

// ---- Forgot password without email: the Administrator approves ---------------

type StoredRequest = { token: string; code: string; identifier: string; expires_at: string | null }
type RequestStatus = "PENDING" | "APPROVED" | "DENIED" | "EXPIRED" | "COMPLETED" | "CANCELLED"
const REQUEST_KEY = "alty.manage.passwordRequest"
const POLL_MS = 10000

function readStored(): StoredRequest | null {
  try {
    const value = JSON.parse(localStorage.getItem(REQUEST_KEY) ?? "null") as StoredRequest | null
    return value?.token && value.code ? value : null
  } catch {
    return null
  }
}

function writeStored(value: StoredRequest | null) {
  try {
    if (value) localStorage.setItem(REQUEST_KEY, JSON.stringify(value))
    else localStorage.removeItem(REQUEST_KEY)
  } catch {
    // Private mode: the request still works while this page stays open.
  }
}

/** "Forgot password?" while email isn't set up: the request goes to the
 *  Administrator. This browser keeps the request's secret, so only it can
 *  choose the new password once the request is approved. */
function AdminApprovalRequest() {
  const config = useSecurityConfig()
  const [request, setRequest] = useState<StoredRequest | null>(readStored)
  const [identifier, setIdentifier] = useState("")
  const [note, setNote] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [cooldown, startCooldown] = useCountdown()
  const [needsCheck, setNeedsCheck] = useState(false)
  const [captcha, setCaptcha] = useState<string | null>(null)
  const [checkRound, setCheckRound] = useState(0)

  const forget = useCallback(() => {
    writeStored(null)
    setRequest(null)
  }, [])

  const send = async (event: FormEvent) => {
    event.preventDefault()
    setError("")
    if (!identifier.trim()) return setError(t("Enter your username or registered email."))
    if (needsCheck && !captcha) return setError(t("Complete the security check first."))
    setBusy(true)
    const reply = await authRequest<{ request_token: string; code: string; expires_at: string | null }>("/password-reset/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier: identifier.trim(), note: note.trim() || null, ...(captcha ? { captcha_token: captcha } : {}) }),
    })
    setBusy(false)
    if (needsCheck) setCheckRound((n) => n + 1) // a check token works once
    if (reply.ok && reply.data) {
      const stored = { token: reply.data.request_token, code: reply.data.code, identifier: identifier.trim(), expires_at: reply.data.expires_at }
      writeStored(stored)
      setRequest(stored)
      setNote("")
      return
    }
    if (reply.captchaRequired) {
      setNeedsCheck(true)
      setError(t("Complete the security check, then try again."))
    } else if (reply.status === 429) {
      setError(t("Too many requests. Please wait a while and try again."))
      startCooldown(Math.max(reply.retryAfter, 60))
    } else if (reply.status === 0) {
      setError(t("Can't reach the server. Check your connection and try again."))
    } else {
      setError(t("Something went wrong. Please try again."))
    }
  }

  if (request) return <RequestStatusView request={request} onForget={forget} />

  return (
    <form onSubmit={send} noValidate>
      <Alert tone="info">{t("Your request goes to the Administrator. Once they approve it, you can choose a new password on this device.")}</Alert>
      <label className="mt-4 block text-sm font-medium" htmlFor="reset-identifier">{t("Username or registered email")}</label>
      <input id="reset-identifier" autoComplete="username" value={identifier} onChange={(e) => setIdentifier(e.target.value)}
        className={field} autoFocus maxLength={254} />
      <label className="mt-4 block text-sm font-medium" htmlFor="reset-note">{t("Message to the Administrator (optional)")}</label>
      <textarea id="reset-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300}
        className={field} placeholder={t("e.g. I'm at the main office today")} />
      {needsCheck && config?.captcha_site_key && <Turnstile siteKey={config.captcha_site_key} onToken={setCaptcha} resetKey={checkRound} unavailableText={t("The security check couldn't load. Check your connection and reload the page.")} />}
      {error && <Alert tone="error">{error}</Alert>}
      <button type="submit" disabled={busy || cooldown > 0} className={primary}>
        {busy && <LoaderCircle className="h-4 w-4 animate-spin" />}
        {busy ? t("Sending…") : cooldown > 0 ? t("Try again in {time}", { time: formatWait(cooldown) }) : t("Send request to the Administrator")}
      </button>
      <BackToSignIn />
    </form>
  )
}

function RequestStatusView({ request, onForget }: { request: StoredRequest; onForget: () => void }) {
  const [status, setStatus] = useState<RequestStatus | null>(null)
  const [offline, setOffline] = useState(false)

  useEffect(() => {
    let alive = true
    let timer: number | undefined
    const check = async () => {
      const reply = await authRequest<{ status: RequestStatus }>("/password-reset/status", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token: request.token }),
      })
      if (!alive) return
      setOffline(!reply.ok)
      let next = reply.data?.status ?? null
      // Unknown names stay "pending" on the server; the request still ends on time.
      if (next === "PENDING" && request.expires_at && Date.parse(request.expires_at) < Date.now()) next = "EXPIRED"
      if (next) setStatus(next)
      if (!next || next === "PENDING") timer = window.setTimeout(check, POLL_MS)
    }
    void check()
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [request])

  if (status === "APPROVED") {
    return (
      <div>
        <Alert tone="success">{t("The Administrator approved your request. Choose your new password.")}</Alert>
        <div className="mt-2"><ResetPasswordForm approvedToken={request.token} onDone={() => writeStored(null)} /></div>
      </div>
    )
  }
  const ended: Partial<Record<RequestStatus, string>> = {
    DENIED: t("The Administrator declined this request. Talk to them, or send a new request."),
    EXPIRED: t("This request expired before it was used. Send a new request."),
    CANCELLED: t("This request was closed because the password was already reset."),
    COMPLETED: t("Your password was already changed with this request."),
  }
  const endedText = status ? ended[status] : undefined
  if (endedText) {
    return (
      <div className="text-center">
        <XCircle className="mx-auto h-10 w-10 text-ab-muted" aria-hidden />
        <p role="status" className="mt-3 text-sm">{endedText}</p>
        <button type="button" onClick={onForget} className={primary}>{t("Send a new request")}</button>
        <BackToSignIn />
      </div>
    )
  }
  return (
    <div className="text-center">
      <Clock className="mx-auto h-10 w-10 text-ab-accent" aria-hidden />
      <p role="status" className="mt-3 text-sm">{t("Request sent for {name}. Waiting for the Administrator to approve it…", { name: request.identifier })}</p>
      <div className="mt-4 rounded-xl border border-ab-border bg-ab-input px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-ab-faint">{t("Check code")}</p>
        <p className="mt-1 font-mono text-3xl font-bold tracking-widest">{request.code}</p>
        <p className="mt-2 flex items-start gap-1.5 text-left text-xs text-ab-muted">
          <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ab-accent" aria-hidden />
          {t("Tell the Administrator this code (in person or by phone) so they know the request is really yours.")}
        </p>
      </div>
      <p className="mt-3 text-xs text-ab-faint">
        {offline ? t("Can't reach the server. Retrying…") : <><LoaderCircle className="mr-1 inline h-3.5 w-3.5 animate-spin align-[-2px]" aria-hidden />{t("This page updates by itself. You can also come back to it later on this device.")}</>}
      </p>
      <button type="button" onClick={onForget} className="mt-4 text-sm font-semibold text-ab-muted hover:text-ab-text hover:underline">{t("Cancel and start over")}</button>
      <BackToSignIn />
    </div>
  )
}
