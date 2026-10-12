import { useState } from "react"
import { peso, transactionDate } from "./format"
import { Section } from "./ui"
import { t } from "./i18n"

type Row = { transaction_id: string; transaction_type: string; status: string; amount: string; transaction_date: string; property_title: string | null; client_name: string | null }

/** Gross sales for the transactions shown: the sum-ups before the total. */
export function GrossSalesRecap({ rows, period }: { rows: Row[]; period: string }) {
  const [open, setOpen] = useState(false)
  const sales = rows.filter((r) => r.transaction_type === "SOLD" && r.status === "COMPLETED")
    .sort((a, b) => a.transaction_date.localeCompare(b.transaction_date))
  const reservations = rows.filter((r) => r.transaction_type === "RESERVED" && r.status !== "CANCELLED")
  const cancelled = rows.filter((r) => r.status === "CANCELLED")
  const sum = (list: Row[]) => list.reduce((total, r) => total + Number(r.amount || 0), 0)
  const gross = sum(sales)
  // Running total after each sale (worked out once, not while drawing).
  const running = sales.reduce<number[]>((totals, sale) => [...totals, (totals.at(-1) ?? 0) + Number(sale.amount || 0)], [])

  const line = (label: string, n: number, amount: number, note: string, strong = false) => (
    <div className={`flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 py-2 ${strong ? "border-t border-ab-border-strong font-extrabold" : ""}`}>
      <span className="min-w-0">
        <span className={strong ? "" : "font-semibold"}>{t(label)}</span>
        {n >= 0 && <span className="ml-1.5 text-xs text-ab-faint">({n})</span>}
        {note && <span className="block text-xs font-normal text-ab-faint">{t(note)}</span>}
      </span>
      <span className={`tabular-nums ${strong ? "text-lg" : ""}`}>{peso(amount)}</span>
    </div>
  )

  return (
    <Section title={t("Gross sales recap · {period}", { period })}>
      <div className="divide-y divide-ab-border text-sm">
        {line("Completed sales", sales.length, gross, "Sold transactions marked Completed: these make up gross sales.")}
        {line("Reservation fees (open and completed)", reservations.length, sum(reservations), "Credited toward each property's price, so not added again.")}
        {line("Cancelled", cancelled.length, sum(cancelled), "Left out of the total.")}
        {line("Gross sales", -1, gross, "= the sum of the completed sales above", true)}
      </div>
      {sales.length > 0 && (
        <>
          <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} className="mt-2 text-xs font-semibold text-ab-accent hover:underline">
            {open ? t("Hide the sum") : t("Show the sum ({n} sales)", { n: sales.length })}
          </button>
          {open && (
            <ol className="ab-table-scroll mt-2 max-h-80 rounded-xl bg-ab-card-2 p-3 text-sm">
              {sales.map((sale, index) => {
                return (
                  <li key={sale.transaction_id} className="flex items-baseline justify-between gap-3 py-1">
                    <span className="min-w-0">
                      <span className="text-ab-faint">{index === 0 ? "" : "+ "}</span>
                      <span className="font-medium">{sale.property_title ?? t("Property")}</span>
                      <span className="block truncate text-xs text-ab-faint">{transactionDate(sale.transaction_date)} · {sale.client_name ?? "—"}</span>
                    </span>
                    <span className="shrink-0 text-right tabular-nums">
                      {peso(sale.amount)}
                      <span className="block text-[11px] text-ab-faint">{t("running total {v}", { v: peso(running[index]) })}</span>
                    </span>
                  </li>
                )
              })}
              <li className="mt-1 flex items-baseline justify-between border-t border-ab-border pt-2 font-extrabold">
                <span>{t("Gross sales")}</span><span className="tabular-nums">{peso(gross)}</span>
              </li>
            </ol>
          )}
        </>
      )}
    </Section>
  )
}
