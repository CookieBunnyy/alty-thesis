// Users & Access: "Forgot password" requests waiting for the Administrator
// (used while email isn't set up). Approving lets the person choose a new
// password on the device that asked; the check code proves it's them.
import { useCallback, useState, type FormEvent } from "react"
import { Check, KeyRound, LoaderCircle, X } from "lucide-react"
import { dateTime } from "./format"
import { Button } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData } from "./useApiData"
import { t } from "./i18n"

type ResetRequest = {
  id: number; status: "PENDING" | "APPROVED"; code: string; note: string | null; created_at: string; until: string | null
  user: { id: number; username: string; full_name: string; role: string } | null
}

const digits = (value: string) => value.replace(/\D/g, "")

export function PasswordRequestsPanel() {
  const { api } = useStaffAuth()
  const toast = useToast()
  const load = useCallback(() => api<ResetRequest[]>("/password-requests"), [api])
  const { data, reload } = useApiData(load)
  const [approving, setApproving] = useState<ResetRequest | null>(null)
  const [busy, setBusy] = useState<number | null>(null)

  const decide = async (request: ResetRequest, action: "approve" | "deny") => {
    setBusy(request.id)
    try {
      await api(`/password-requests/${request.id}/${action}`, { method: "POST" })
      toast(action === "approve"
        ? t("Approved. {name} can now choose a new password on their device.", { name: request.user?.full_name ?? "" })
        : t("Request declined."))
      setApproving(null)
    } catch (error) {
      toast(t((error as Error).message), "error")
    } finally {
      setBusy(null)
      await reload()
    }
  }

  if (!data?.length) return null
  return (
    <section className="rounded-2xl border border-ab-warning/40 bg-ab-warning/5 p-4" aria-labelledby="reset-requests">
      <h2 id="reset-requests" className="flex items-center gap-2 text-sm font-bold">
        <KeyRound className="h-4 w-4 text-ab-warning" aria-hidden /> {t("Password reset requests")}
      </h2>
      <p className="mt-1 text-xs text-ab-muted">{t("Approve only after the person tells you the check code shown on their screen (in person or by phone).")}</p>
      <ul className="mt-3 space-y-2">
        {data.map((r) => (
          <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ab-border bg-ab-card p-3 text-sm">
            <div className="min-w-0">
              <p className="font-semibold">{r.user?.full_name ?? "—"} <span className="font-normal text-ab-faint">· {r.user?.username} · {t(r.user?.role ?? "")}</span></p>
              <p className="text-xs text-ab-faint">
                {t("Asked {when}", { when: dateTime(r.created_at) })}
                {r.status === "APPROVED" && r.until ? ` · ${t("approved, usable until {when}", { when: dateTime(r.until) })}` : ""}
              </p>
              {r.note && <p className="mt-1 text-xs italic text-ab-muted">“{r.note}”</p>}
            </div>
            {r.status === "PENDING" ? (
              <div className="flex gap-2">
                <Button disabled={busy === r.id} onClick={() => void decide(r, "deny")}><X className="h-4 w-4" /> {t("Decline")}</Button>
                <Button variant="primary" disabled={busy === r.id} onClick={() => setApproving(r)}><Check className="h-4 w-4" /> {t("Approve")}</Button>
              </div>
            ) : (
              <span className="rounded-full bg-ab-success/15 px-2 py-0.5 text-[11px] font-semibold text-ab-success">{t("Approved — waiting for the new password")}</span>
            )}
          </li>
        ))}
      </ul>
      {approving && <ApproveDialog request={approving} busy={busy === approving.id} onCancel={() => setApproving(null)} onApprove={() => void decide(approving, "approve")} />}
    </section>
  )
}

function ApproveDialog({ request, busy, onCancel, onApprove }: { request: ResetRequest; busy: boolean; onCancel: () => void; onApprove: () => void }) {
  const [typed, setTyped] = useState("")
  const matches = digits(typed) === digits(request.code)
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (matches && !busy) onApprove()
  }
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={t("Approve password reset")}>
      <button type="button" aria-label={t("Cancel")} className="absolute inset-0 bg-black/55" onClick={onCancel} />
      <form onSubmit={submit} className="ab-pop relative w-full max-w-md rounded-2xl border border-ab-border bg-ab-card p-6 shadow-2xl">
        <h2 className="text-lg font-bold">{t("Approve password reset")}</h2>
        <p className="mt-2 text-sm text-ab-muted">
          {t("Ask {name} to read you the check code on their screen, and type it here. Approve only if it matches.", { name: request.user?.full_name ?? "" })}
        </p>
        <label className="mt-4 block text-sm font-medium" htmlFor="check-code">{t("Check code they read to you")}</label>
        <input id="check-code" autoFocus inputMode="numeric" autoComplete="off" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="000 000"
          className="mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 font-mono text-lg tracking-widest focus:border-ab-accent focus:outline-none" />
        {digits(typed).length >= 6 && !matches && <p role="alert" className="mt-2 text-sm text-ab-danger">{t("The code doesn't match. Don't approve: this request may not be theirs.")}</p>}
        <div className="mt-6 flex justify-end gap-2">
          <Button onClick={onCancel} disabled={busy}>{t("Cancel")}</Button>
          <Button type="submit" variant="primary" disabled={busy || !matches}>
            {busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Approve")}
          </Button>
        </div>
      </form>
    </div>
  )
}
