// Listing details from the second interview: RFO or pre-selling, the
// financing the developer accepts, and the sample computation sheet.

export type SalesTerms = { property_status: string; financing_options: string[]; reservation_fee: string; equity_terms_months: string }
type Source = { property_status?: string | null; financing_options?: string[] | null; reservation_fee?: number | string | null; equity_terms_months?: number | null }

export const PROPERTY_STATUS: Record<string, string> = { RFO: "RFO (ready for occupancy)", PRE_SELLING: "Pre-selling" }
export const FINANCING: Record<string, string> = { BANK: "Bank", PAGIBIG: "Pag-IBIG", IN_HOUSE: "In-house", SSS: "SSS", CASH: "Cash" }

export const termsFrom = (listing?: Source | null): SalesTerms => ({
  property_status: listing?.property_status ?? "",
  financing_options: listing?.financing_options ?? [],
  reservation_fee: listing?.reservation_fee == null ? "" : String(Number(listing.reservation_fee)),
  equity_terms_months: listing?.equity_terms_months == null ? "" : String(listing.equity_terms_months),
})

/** Request fields; null when empty. Returns an error message instead when invalid. */
export function termsBody(terms: SalesTerms): Record<string, unknown> | string {
  const fee = terms.reservation_fee.trim() === "" ? null : Number(terms.reservation_fee.replace(/,/g, ""))
  const months = terms.equity_terms_months.trim() === "" ? null : Number(terms.equity_terms_months)
  if (fee !== null && (!Number.isFinite(fee) || fee < 0)) return "The reservation fee must be zero or more."
  if (months !== null && (!Number.isInteger(months) || months < 1 || months > 120)) return "Equity terms must be 1 to 120 months."
  return { property_status: terms.property_status || null, financing_options: terms.financing_options, reservation_fee: fee, equity_terms_months: months }
}

/** The sample computation from the figures on the form (same as the server's). */
export function sampleComputation(price: string, downPayment: string, monthly: string, terms: SalesTerms) {
  const n = (v: string) => (v.trim() === "" ? null : Number(v.replace(/,/g, "")))
  const tcp = n(price)
  if (!tcp || !Number.isFinite(tcp)) return null
  const fee = n(terms.reservation_fee)
  const down = n(downPayment)
  const months = n(terms.equity_terms_months)
  const netEquity = down !== null ? Math.max(down - (fee ?? 0), 0) : null
  return {
    tcp, fee, down, netEquity, months,
    monthlyEquity: netEquity && months ? netEquity / months : null,
    toFinance: down !== null ? Math.max(tcp - down, 0) : null,
    amortization: n(monthly) || null,
  }
}
