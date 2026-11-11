import type { Property } from "@/types"

const STATUS: Record<string, string> = { RFO: "Ready for occupancy (RFO)", PRE_SELLING: "Pre-selling" }
const FINANCING: Record<string, string> = { BANK: "Bank", PAGIBIG: "Pag-IBIG", IN_HOUSE: "In-house", SSS: "SSS", CASH: "Cash" }
const peso = (value: number) => `₱${value.toLocaleString("en-PH", { maximumFractionDigits: 2 })}`

/** Status, developer, financing accepted and the sample computation sheet. */
export function PropertyComputation({ property }: { property: Property }) {
  const sample = property.sample_computation
  const facts = [
    property.property_status ? ["Status", STATUS[property.property_status] ?? property.property_status] : null,
    property.developer ? ["Developer", property.developer] : null,
    property.project_name ? ["Project", property.project_name] : null,
    property.financing_options?.length ? ["Financing", property.financing_options.map((f) => FINANCING[f] ?? f).join(" · ")] : null,
  ].filter((row): row is string[] => row !== null)
  const rows = sample ? [
    ["Total contract price (TCP)", peso(sample.tcp)],
    sample.reservation_fee != null ? ["Reservation fee", peso(sample.reservation_fee)] : null,
    sample.down_payment != null ? ["Down payment", peso(sample.down_payment)] : null,
    sample.net_equity != null ? ["Net equity", peso(sample.net_equity)] : null,
    sample.monthly_equity != null ? ["Monthly equity", `${peso(sample.monthly_equity)} × ${sample.equity_terms_months} mos.`] : null,
    sample.amount_to_finance != null ? ["Amount to finance", peso(sample.amount_to_finance)] : null,
    sample.monthly_amortization != null ? ["Est. monthly amortization", peso(sample.monthly_amortization)] : null,
  ].filter((row): row is string[] => row !== null) : []
  if (!facts.length && rows.length < 2) return null
  return (
    <section aria-labelledby="computation-title" className="space-y-2">
      {facts.length > 0 && (
        <dl className="grid grid-cols-2 gap-2 text-sm">
          {facts.map(([label, value]) => (
            <div key={label} className="rounded-xl border border-ab-border bg-ab-card-2 px-3 py-2">
              <dt className="text-[10px] font-bold uppercase tracking-wider text-ab-faint">{label}</dt>
              <dd className="font-semibold text-ab-text">{value}</dd>
            </div>
          ))}
        </dl>
      )}
      {rows.length >= 2 && (
        <div className="rounded-xl border border-ab-border p-3">
          <h3 id="computation-title" className="mb-1 text-xs font-semibold uppercase text-ab-faint">Sample computation</h3>
          <dl className="divide-y divide-ab-border/60 text-sm">
            {rows.map(([label, value]) => (
              <div key={label} className="flex justify-between gap-3 py-1"><dt className="text-ab-muted">{label}</dt><dd className="font-semibold tabular-nums text-ab-text">{value}</dd></div>
            ))}
          </dl>
          <p className="mt-1 text-[11px] leading-snug text-ab-faint">{sample?.note}</p>
        </div>
      )}
    </section>
  )
}
