// Why a transaction was cancelled: the short line shown in lists, and the
// dialog that cancels an open reservation (a reason is required).
import { useEffect, useState, type FormEvent } from "react"
import { CircleX, LoaderCircle } from "lucide-react"
import { dateTime } from "./format"
import { t } from "./i18n"
import { Button } from "./ui"
import { useStaffAuth } from "./staffContext"

const NO_REASON = "No reason was recorded (cancelled before reasons were tracked)."

/** "Why: …" under a cancelled transaction; nothing for other statuses. */
export function CancelReason({ status, reason, compact = false }: { status: string; reason?: string | null; compact?: boolean }) {
  if (status !== "CANCELLED") return null
  return (
    <span className={`block text-[11px] ${reason ? "text-ab-danger" : "italic text-ab-faint"} ${compact ? "line-clamp-1 max-w-64" : ""}`}
      title={reason ?? undefined}>
      {reason ? `${t("Why:")} ${reason}` : t(NO_REASON)}
    </span>
  )
}

/** Full cancellation details for a record panel. */
export function CancellationDetails({ reason, by, at }: { reason?: string | null; by?: string | null; at?: string | null }) {
  return (
    <div role="note" className="rounded-2xl border border-ab-danger/40 bg-ab-danger/5 p-4">
      <p className="flex items-center gap-2 text-sm font-extrabold uppercase tracking-wide text-ab-danger">
        <CircleX className="h-4 w-4" /> {t("Cancelled")}
      </p>
      <p className={`mt-1.5 text-sm ${reason ? "text-ab-text" : "italic text-ab-faint"}`}>
        {reason ? <><span className="font-semibold">{t("Reason:")}</span> {reason}</> : t(NO_REASON)}
      </p>
      {(by || at) && (
        <p className="mt-1 text-xs text-ab-muted">
          {[by && t("By {name}", { name: by }), at && dateTime(at)].filter(Boolean).join(" · ")}
        </p>
      )}
    </div>
  )
}

const QUICK_REASONS = [
  "Buyer's bank loan was not approved",
  "Buyer backed out",
  "Payment was not received on time",
  "Buyer chose another property",
  "Recorded by mistake",
]

/** Cancel an open reservation; the reason is required and kept on the record. */
export function CancelReservationDialog({ transactionId, label, onClose, onDone }: {
  transactionId: string; label: string; onClose: () => void; onDone: () => void
}) {
  const { api } = useStaffAuth()
  const [reason, setReason] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose()
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [busy, onClose])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (reason.trim().length < 3) return setError(t("Please give the reason for cancelling."))
    setBusy(true)
    setError("")
    try {
      await api(`/transactions/${encodeURIComponent(transactionId)}/cancel`, { method: "POST", body: JSON.stringify({ reason: reason.trim() }) })
      onDone()
    } catch (cancelError) {
      setError(t((cancelError as Error).message))
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[75] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={t("Cancel reservation")}>
      <button type="button" aria-label={t("Close")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={submit} className="ab-pop relative w-full max-w-md rounded-2xl border border-ab-border bg-ab-card p-6 shadow-2xl">
        <h2 className="text-lg font-bold">{t("Cancel reservation")}</h2>
        <p className="mt-1 text-sm text-ab-muted">{label}</p>
        <p className="mt-3 text-sm text-ab-muted">{t("The property goes back to Available if no other reservation holds it. The reason is kept on the transaction for everyone to see.")}</p>
        <label className="mt-4 block text-sm font-medium" htmlFor="cancel-reason">{t("Why is it being cancelled?")}</label>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {QUICK_REASONS.map((quick) => (
            <button key={quick} type="button" onClick={() => setReason(t(quick))}
              className="rounded-full border border-ab-border px-2.5 py-1 text-xs text-ab-muted hover:border-ab-accent hover:text-ab-text">
              {t(quick)}
            </button>
          ))}
        </div>
        <textarea id="cancel-reason" autoFocus value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000}
          className="mt-2 block min-h-24 w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"
          placeholder={t("e.g. The buyer's bank loan was not approved")} />
        {error && <p role="alert" className="mt-2 text-sm text-ab-danger">{error}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <Button onClick={onClose} disabled={busy}>{t("Keep reservation")}</Button>
          <Button type="submit" variant="danger" disabled={busy || reason.trim().length < 3}>
            {busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Cancel reservation")}
          </Button>
        </div>
      </form>
    </div>
  )
}
