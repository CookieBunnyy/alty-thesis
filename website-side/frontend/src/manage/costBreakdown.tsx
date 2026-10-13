// Transaction drawer: the property price plus the estimated taxes and fees
// of buying it (/transactions/{id}/cost-breakdown).
import { useCallback, useState } from "react"
import { Info, MapPin } from "lucide-react"
import { peso } from "./format"
import { LoadState, Section } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"
import { t } from "./i18n"

type Fee = { key: string; label: string; rate: number; amount: number; note: string }
type Breakdown = {
  price: number; buyer_fees: Fee[]; buyer_fees_total: number; total_cost: number; seller_fees: Fee[]
  location: { metro_manila: boolean; matched: string | null; reason: string }
  seller_is_developer: boolean; property_kind: "lot" | "dwelling"
  vat: { applies: boolean; amount: number; reason: string; code: "NOT_DEVELOPER" | "EXEMPT" | "INCLUDED"; threshold?: number }; basis: string
}

const placeName = (place: string) => (place.length <= 3 ? place.toUpperCase() : place.split(" ").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" "))

function locationReason(l: Breakdown["location"]): string {
  if (!l.matched) return t("The address doesn't name a Metro Manila city, so the provincial rate is used.")
  return l.metro_manila
    ? t("The address mentions {place}, in Metro Manila.", { place: placeName(l.matched) })
    : t("The address mentions {place}, outside Metro Manila.", { place: placeName(l.matched) })
}

function vatReason(v: Breakdown["vat"]): string {
  if (v.code === "EXEMPT") return t("VAT-exempt: a residential dwelling sold for {v} or less.", { v: peso(v.threshold ?? 0) })
  if (v.code === "INCLUDED") return t("The developer's sale is subject to 12% VAT, normally already included in the listed price; this is the VAT part of the price, not an extra charge.")
  return t("No VAT: the seller isn't recorded as a developer, so a sale by an individual owner is assumed (capital gains tax applies instead).")
}

const pct = (rate: number) => `${(rate * 100).toLocaleString(undefined, { maximumFractionDigits: 2 })}%`

export function CostBreakdown({ transactionId }: { transactionId: string }) {
  const { api } = useStaffAuth()
  const load = useCallback(() => api<Breakdown>(`/transactions/${encodeURIComponent(transactionId)}/cost-breakdown`), [api, transactionId])
  const { data, error, loading, reload } = useApiData(load)
  const [explain, setExplain] = useState(false)
  return (
    <Section title="Price and buying costs (estimate)"
      action={data && <button type="button" onClick={() => setExplain((v) => !v)} aria-expanded={explain} className="inline-flex items-center gap-1 text-xs font-semibold text-ab-accent hover:underline"><Info className="h-3.5 w-3.5" aria-hidden /> {explain ? t("Hide explanations") : t("What are these?")}</button>}>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <div className="space-y-3 text-sm">
          <p className="flex flex-wrap items-center gap-2 text-xs">
            <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 font-semibold ${data.location.metro_manila ? "bg-ab-accent-soft text-ab-accent" : "bg-ab-card-2 text-ab-muted"}`}>
              <MapPin className="h-3.5 w-3.5" aria-hidden /> {data.location.metro_manila ? t("Metro Manila (NCR) rates") : t("Provincial rates")}
            </span>
            <span className="text-ab-faint">{locationReason(data.location)}</span>
          </p>
          <ol className="rounded-xl bg-ab-card-2 p-3">
            <Row label={t("Property price")} value={peso(data.price)} strong />
            {data.buyer_fees.map((fee) => (
              <Row key={fee.key} label={`+ ${t(fee.label)}`} hint={pct(fee.rate)} value={peso(fee.amount)} note={explain ? t(fee.note) : undefined} />
            ))}
            <li className="mt-2 flex flex-wrap items-baseline justify-between gap-x-3 border-t border-ab-border pt-2">
              <span className="font-bold">{t("Estimated total cost to the buyer")}</span>
              <span className="text-base font-extrabold tabular-nums text-ab-accent">{peso(data.total_cost)}</span>
              <span className="w-full text-xs text-ab-faint">{t("Price + {v} in taxes and fees", { v: peso(data.buyer_fees_total) })}</span>
            </li>
          </ol>
          <div className="rounded-xl border border-ab-border p-3">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3">
              <span className="font-semibold">{t("VAT (12%)")}</span>
              <span className="tabular-nums">{data.vat.applies ? t("{v} included in the price", { v: peso(data.vat.amount) }) : t("Not applicable")}</span>
            </div>
            <p className="mt-1 text-xs text-ab-muted">{vatReason(data.vat)}</p>
          </div>
          {data.seller_fees.length > 0 && (
            <div className="rounded-xl border border-ab-border p-3">
              <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("Usually paid by the seller")}</p>
              <ul className="mt-1">
                {data.seller_fees.map((fee) => (
                  <Row key={fee.key} label={t(fee.label)} hint={pct(fee.rate)} value={peso(fee.amount)} note={explain ? t(fee.note) : undefined} />
                ))}
              </ul>
            </div>
          )}
          <p className="text-xs text-ab-faint">{t(data.basis)}</p>
        </div>
      )}
    </Section>
  )
}

function Row({ label, value, hint, note, strong }: { label: string; value: string; hint?: string; note?: string; strong?: boolean }) {
  return (
    <li className="flex flex-wrap items-baseline justify-between gap-x-3 py-1">
      <span className={`min-w-0 ${strong ? "font-semibold" : "text-ab-muted"}`}>{label}{hint && <span className="ml-1 text-xs text-ab-faint">({hint})</span>}</span>
      <span className={`tabular-nums ${strong ? "font-bold" : ""}`}>{value}</span>
      {note && <span className="w-full text-xs text-ab-faint">{note}</span>}
    </li>
  )
}
