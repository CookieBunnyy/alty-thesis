// RFO / pre-selling, financing accepted, reservation fee and equity terms,
// with the sample computation the website shows.
import { peso } from "./format"
import { t } from "./i18n"
import { FINANCING, PROPERTY_STATUS, sampleComputation, type SalesTerms } from "./listingTermsData"

const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"

export function SalesTermsFields({ terms, onChange, price, downPayment, monthly }: {
  terms: SalesTerms; onChange: (terms: SalesTerms) => void; price: string; downPayment: string; monthly: string
}) {
  const set = <K extends keyof SalesTerms>(key: K, value: SalesTerms[K]) => onChange({ ...terms, [key]: value })
  const toggle = (code: string) => set("financing_options", terms.financing_options.includes(code)
    ? terms.financing_options.filter((c) => c !== code) : [...terms.financing_options, code])
  const sample = sampleComputation(price, downPayment, monthly, terms)
  const rows: [string, string | null][] = sample ? [
    ["Total contract price (TCP)", peso(sample.tcp)],
    ["Reservation fee", sample.fee != null ? peso(sample.fee) : null],
    ["Down payment", sample.down != null ? peso(sample.down) : null],
    ["Net equity (down payment less reservation fee)", sample.netEquity != null ? peso(sample.netEquity) : null],
    ["Monthly equity", sample.monthlyEquity != null ? `${peso(sample.monthlyEquity)} × ${sample.months}` : null],
    ["Amount to finance (loan)", sample.toFinance != null ? peso(sample.toFinance) : null],
    ["Estimated monthly amortization", sample.amortization != null ? peso(sample.amortization) : null],
  ] : []
  return (
    <fieldset className="grid gap-3 rounded-xl border border-ab-border p-3 sm:col-span-2 sm:grid-cols-2">
      <legend className="px-1 text-sm font-semibold">{t("Status, financing and sample computation")}</legend>
      <label className="text-sm font-medium">{t("Property status")}
        <select className={field} value={terms.property_status} onChange={(e) => set("property_status", e.target.value)}>
          <option value="">{t("Not set")}</option>
          {Object.entries(PROPERTY_STATUS).map(([code, label]) => <option key={code} value={code}>{t(label)}</option>)}
        </select>
      </label>
      <div className="text-sm font-medium">
        <span>{t("Financing accepted")}</span>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {Object.entries(FINANCING).map(([code, label]) => (
            <label key={code} className={`inline-flex min-h-9 cursor-pointer items-center gap-1.5 rounded-full border px-3 text-xs font-semibold ${terms.financing_options.includes(code) ? "border-ab-accent bg-ab-accent-soft text-ab-accent" : "border-ab-border"}`}>
              <input type="checkbox" className="sr-only" checked={terms.financing_options.includes(code)} onChange={() => toggle(code)} />{t(label)}
            </label>
          ))}
        </div>
      </div>
      <label className="text-sm font-medium">{t("Reservation fee (₱)")}<input className={field} inputMode="decimal" value={terms.reservation_fee} onChange={(e) => set("reservation_fee", e.target.value)} placeholder="20000" /></label>
      <label className="text-sm font-medium">{t("Equity terms (months)")}<input className={field} inputMode="numeric" value={terms.equity_terms_months} onChange={(e) => set("equity_terms_months", e.target.value)} placeholder={t("e.g. 12 or 24")} /></label>
      {sample && (
        <div className="rounded-xl bg-ab-card-2 p-3 text-sm sm:col-span-2">
          <p className="mb-1 font-semibold">{t("Sample computation")}</p>
          <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
            {rows.filter(([, v]) => v).map(([label, value]) => (
              <div key={label} className="flex justify-between gap-2 border-b border-ab-border/60 py-0.5"><dt className="text-ab-muted">{t(label)}</dt><dd className="font-semibold tabular-nums">{value}</dd></div>
            ))}
          </dl>
          <p className="mt-1 text-xs text-ab-faint">{t("Shown on the website as a sample; the developer's computation sheet and the lender's approval give the final figures.")}</p>
        </div>
      )}
    </fieldset>
  )
}
