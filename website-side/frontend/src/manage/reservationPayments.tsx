import { Fragment, useCallback, useEffect, useState, type FormEvent } from "react"
import { LoaderCircle, Trash2 } from "lucide-react"
import { peso } from "./format"
import { Button, Confirm, LoadState, Section } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData, clearApiCache } from "./useApiData"
import { useToast } from "./toastContext"
import { locale, t } from "./i18n"

type Item = { kind: string; label: string; due: string; amount: string; paid: string; status: "PAID" | "PARTIAL" | "OVERDUE" | "DUE" | "UPCOMING" }
type Plan = {
  available: boolean; reason?: string
  price: string; reservation_fee: string; down_payment: string; down_payment_paid: string
  down_payment_status: "PAID" | "PARTIAL" | "NOT_PAID" | "NONE"
  monthly_rate: string; monthly_payments: number; balance_after_down_payment: string
  total_paid: string; remaining: string; overpaid: string; fully_paid_by: string; is_fully_paid: boolean
  next_due: { label: string; due: string; amount: string; status: string } | null
  terms: string[]; items: Item[]
}
type Payment = { id: number; amount: string; paid_at: string; note: string | null; recorded_by: string | null }
type PlanResponse = { plan: Plan; payments: Payment[] }

const day = (iso: string) => {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number)
  return new Date(y, m - 1, d).toLocaleDateString(locale(), { month: "short", day: "numeric", year: "numeric" })
}
const monthYear = (iso: string) => {
  const [y, m] = iso.slice(0, 7).split("-").map(Number)
  return new Date(y, m - 1, 1).toLocaleDateString(locale(), { month: "long", year: "numeric" })
}
const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Manila" })

const STATUS = {
  PAID: { label: "Paid", tone: "bg-ab-accent-soft text-ab-accent" },
  PARTIAL: { label: "Partly paid", tone: "bg-ab-warning/15 text-ab-text" },
  OVERDUE: { label: "Overdue", tone: "bg-ab-danger/10 text-ab-danger" },
  DUE: { label: "Due this month", tone: "bg-ab-warning/15 text-ab-text" },
  UPCOMING: { label: "Upcoming", tone: "bg-ab-card-2 text-ab-muted" },
} as const
const DP = {
  PAID: "Down payment paid", PARTIAL: "Down payment partly paid", NOT_PAID: "Down payment not yet paid", NONE: "No down payment in the listing's terms",
} as const

const Chip = ({ status }: { status: Item["status"] }) => (
  <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS[status].tone}`}>{t(STATUS[status].label)}</span>
)

/** A reservation's down payment, payment schedule and recorded payments. */
export function PaymentSchedule({ transactionId, canRecord, onChanged }: { transactionId: string; canRecord: boolean; onChanged?: () => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const load = useCallback(() => api<PlanResponse>(`/transactions/${encodeURIComponent(transactionId)}/payment-plan`), [api, transactionId])
  const { data, error, loading, reload } = useApiData(load, `payment-plan:${transactionId}`)
  const [showAll, setShowAll] = useState(false)
  const [form, setForm] = useState({ amount: "", paid_at: today(), note: "" })
  const [formError, setFormError] = useState("")
  const [busy, setBusy] = useState(false)
  const [removing, setRemoving] = useState<Payment | null>(null)
  const plan = data?.plan

  const record = async (event: FormEvent) => {
    event.preventDefault()
    setFormError("")
    const amount = Number(form.amount.replace(/,/g, ""))
    if (!Number.isFinite(amount) || amount <= 0) return setFormError(t("Enter the amount received."))
    if (!form.paid_at) return setFormError(t("Enter the date it was paid."))
    setBusy(true)
    try {
      await api(`/transactions/${encodeURIComponent(transactionId)}/payments`, { method: "POST", body: JSON.stringify({ amount, paid_at: form.paid_at, note: form.note.trim() || null }) })
      setForm({ amount: "", paid_at: today(), note: "" })
      toast(t("Payment recorded."))
      await reload()
      onChanged?.()
    } catch (saveError) {
      setFormError(t((saveError as Error).message))
    } finally {
      setBusy(false)
    }
  }
  const remove = async () => {
    if (!removing) return
    setBusy(true)
    try {
      await api(`/transactions/${encodeURIComponent(transactionId)}/payments/${removing.id}`, { method: "DELETE" })
      toast(t("Payment removed."))
      setRemoving(null)
      await reload()
    } catch (removeError) {
      toast(t((removeError as Error).message), "error")
    } finally {
      setBusy(false)
    }
  }

  if (!plan) return <Section title="Payments"><LoadState loading={loading} error={error} onRetry={reload} /></Section>
  if (!plan.available) return <Section title="Payments"><p className="text-sm text-ab-muted">{t(plan.reason ?? "")}</p></Section>

  // Long schedules: the first months, the next unpaid one and the last, unless expanded.
  const items = plan.items
  const firstUnpaid = items.findIndex((item) => item.status !== "PAID")
  const visible = showAll || items.length <= 10
    ? items.map((item, index) => ({ item, index }))
    : items.map((item, index) => ({ item, index })).filter(({ index }) => index < 6 || index === items.length - 1 || (firstUnpaid >= 0 && Math.abs(index - firstUnpaid) <= 1))

  return (
    <Section title="Down payment and payment schedule">
      <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
        {[
          ["Price", peso(plan.price)],
          ["Reservation fee", peso(plan.reservation_fee)],
          ["Down payment", Number(plan.down_payment) ? peso(plan.down_payment) : "—"],
          ["Paid so far", peso(plan.total_paid)],
          ["Remaining", peso(plan.remaining)],
          ["Fully paid by", plan.is_fully_paid ? t("Fully paid") : monthYear(plan.fully_paid_by)],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl bg-ab-card-2 p-2.5">
            <p className="text-[11px] text-ab-faint">{t(label)}</p>
            <p className="font-bold tabular-nums">{value}</p>
          </div>
        ))}
      </div>
      <p className={`mt-3 rounded-xl px-3 py-2 text-sm font-semibold ${plan.down_payment_status === "PAID" ? "bg-ab-accent-soft text-ab-accent" : plan.down_payment_status === "NONE" ? "bg-ab-card-2 text-ab-muted" : "bg-ab-warning/15 text-ab-text"}`}>
        {t(DP[plan.down_payment_status])}
        {plan.down_payment_status !== "NONE" && ` · ${peso(plan.down_payment_paid)} ${t("of")} ${peso(plan.down_payment)}`}
      </p>
      {plan.next_due && (
        <p className="mt-2 text-sm text-ab-muted">
          {t("Next:")} <span className="font-semibold text-ab-text">{t(plan.next_due.label)}</span> · {peso(plan.next_due.amount)} · {t("due")} {day(plan.next_due.due)}
        </p>
      )}
      {Number(plan.monthly_payments) > 0 && (
        <p className="mt-1 text-sm text-ab-muted">
          {t("{n} monthly payment(s) of {amount}; the last one in {month}.", { n: plan.monthly_payments, amount: peso(plan.monthly_rate), month: monthYear(plan.fully_paid_by) })}
        </p>
      )}

      <div className="ab-table-scroll mt-3 max-h-80 rounded-xl border border-ab-border">
        <table className="w-full text-left text-xs">
          <thead className="text-[10px] uppercase tracking-wide text-ab-faint">
            <tr className="border-b border-ab-border"><th className="px-3 py-2">{t("Payment")}</th><th className="px-3 py-2">{t("Due")}</th><th className="px-3 py-2 text-right">{t("Amount")}</th><th className="px-3 py-2">{t("Status")}</th></tr>
          </thead>
          <tbody>
            {visible.map(({ item, index }, position) => (
              <Fragment key={index}>
                {position > 0 && index - visible[position - 1].index > 1 && (
                  <tr><td colSpan={4} className="px-3 py-1 text-center text-ab-faint">⋯ {t("{n} more", { n: index - visible[position - 1].index - 1 })}</td></tr>
                )}
                <tr className="border-b border-ab-border last:border-0">
                  <td className="px-3 py-2">{t(item.label)}</td>
                  <td className="whitespace-nowrap px-3 py-2">{day(item.due)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {peso(item.amount)}
                    {item.status === "PARTIAL" || (item.status === "OVERDUE" && Number(item.paid) > 0) ? <span className="block text-[10px] text-ab-faint">{t("{paid} paid", { paid: peso(item.paid) })}</span> : null}
                  </td>
                  <td className="px-3 py-2"><Chip status={item.status} /></td>
                </tr>
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {items.length > 10 && (
        <button type="button" onClick={() => setShowAll((value) => !value)} className="mt-2 text-xs font-semibold text-ab-accent hover:underline">
          {showAll ? t("Show fewer") : t("Show all {n} payments", { n: items.length })}
        </button>
      )}
      <details className="mt-3 text-xs text-ab-muted">
        <summary className="cursor-pointer font-semibold">{t("How the schedule is worked out")}</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5">{plan.terms.map((term) => <li key={term}>{t(term)}</li>)}</ul>
      </details>

      <div className="mt-4">
        <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("Payments received")}</p>
        {data!.payments.length === 0 ? (
          <p className="mt-1 text-sm text-ab-muted">{t("Only the reservation fee so far.")}</p>
        ) : (
          <ul className="mt-1 divide-y divide-ab-border text-sm">
            {data!.payments.map((payment) => (
              <li key={payment.id} className="flex items-center gap-3 py-2">
                <span className="min-w-0 flex-1">
                  <span className="font-semibold tabular-nums">{peso(payment.amount)}</span> · {day(payment.paid_at)}
                  {payment.note && <span className="block truncate text-xs text-ab-faint">{payment.note}</span>}
                  {payment.recorded_by && <span className="block text-[11px] text-ab-faint">{t("Recorded by {name}", { name: payment.recorded_by })}</span>}
                </span>
                {canRecord && (
                  <button type="button" onClick={() => setRemoving(payment)} aria-label={t("Remove payment")} className="rounded-lg p-1.5 text-ab-muted hover:bg-ab-hover hover:text-ab-danger">
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        {canRecord && !plan.is_fully_paid && (
          <form onSubmit={record} className="mt-3 grid gap-2 rounded-xl border border-ab-border p-3 sm:grid-cols-3" noValidate>
            <label className="text-xs font-medium">{t("Amount received (₱)")}
              <input inputMode="decimal" value={form.amount} onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
                placeholder={plan.next_due ? String(Number(plan.next_due.amount)) : ""}
                className="mt-1 block w-full rounded-lg border border-ab-border bg-ab-input px-2.5 py-2 text-sm" />
            </label>
            <label className="text-xs font-medium">{t("Date paid")}
              <input type="date" max={today()} value={form.paid_at} onChange={(e) => setForm((f) => ({ ...f, paid_at: e.target.value }))}
                className="mt-1 block w-full rounded-lg border border-ab-border bg-ab-input px-2.5 py-2 text-sm" />
            </label>
            <label className="text-xs font-medium">{t("Note (optional)")}
              <input value={form.note} maxLength={300} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))}
                placeholder={t("e.g. OR #1234, bank transfer")} className="mt-1 block w-full rounded-lg border border-ab-border bg-ab-input px-2.5 py-2 text-sm" />
            </label>
            {formError && <p role="alert" className="text-xs text-ab-danger sm:col-span-3">{formError}</p>}
            <div className="sm:col-span-3">
              <Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Record payment")}</Button>
            </div>
          </form>
        )}
      </div>
      {removing && (
        <Confirm
          title={t("Remove this payment?")}
          message={t("{amount} paid on {day} will be removed and the schedule recalculated.", { amount: peso(removing.amount), day: day(removing.paid_at) })}
          confirmLabel={t("Remove payment")} busy={busy} typeToConfirm="Delete"
          onConfirm={() => void remove()} onCancel={() => setRemoving(null)}
        />
      )}
    </Section>
  )
}

/** The reservation proceeded to a purchase: record the sale (property -> SOLD). */
export function ProceedToSaleDialog({ transactionId, label, price, onClose, onDone }: {
  transactionId: string; label: string; price: number | null; onClose: () => void; onDone: () => void
}) {
  const { api } = useStaffAuth()
  const [amount, setAmount] = useState(price ? String(price) : "")
  const [date, setDate] = useState(today())
  const [note, setNote] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose()
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [busy, onClose])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const value = amount.trim() ? Number(amount.replace(/,/g, "")) : null
    if (value !== null && (!Number.isFinite(value) || value <= 0)) return setError(t("Enter the sale amount, or leave it blank to use the listing's price."))
    setBusy(true)
    setError("")
    try {
      await api(`/transactions/${encodeURIComponent(transactionId)}/complete-sale`, {
        method: "POST", body: JSON.stringify({ amount: value, sale_date: date, note: note.trim() || null }),
      })
      clearApiCache() // properties, clients and dashboards change too
      onDone()
    } catch (saleError) {
      setError(t((saleError as Error).message))
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[75] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={t("Proceed to sale")}>
      <button type="button" aria-label={t("Close")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={submit} className="ab-pop relative w-full max-w-md rounded-2xl border border-ab-border bg-ab-card p-6 shadow-2xl" noValidate>
        <h2 className="text-lg font-extrabold">{t("Proceed to sale")}</h2>
        <p className="mt-1 text-sm text-ab-muted">{label}</p>
        <p className="mt-3 rounded-xl bg-ab-card-2 p-3 text-xs text-ab-muted">
          {t("The reservation is kept as history and marked Completed, a Sold transaction is added, and the property and the client become Sold.")}
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="text-sm font-medium">{t("Sale amount (₱)")}
            <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder={t("Listing price")} className="mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2.5 text-sm" />
          </label>
          <label className="text-sm font-medium">{t("Sale date")}
            <input type="date" max={today()} value={date} onChange={(e) => setDate(e.target.value)} className="mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2.5 text-sm" />
          </label>
          <label className="text-sm font-medium sm:col-span-2">{t("Note (optional)")}
            <input value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} placeholder={t("e.g. Bank loan approved; deed signed")} className="mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2.5 text-sm" />
          </label>
        </div>
        {error && <p role="alert" className="mt-3 text-sm text-ab-danger">{error}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button>
          <Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t("Mark as sold")}</Button>
        </div>
      </form>
    </div>
  )
}
