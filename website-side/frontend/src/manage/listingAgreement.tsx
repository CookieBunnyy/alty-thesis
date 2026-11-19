// The owner's listing agreement for a property (recorded from an uploaded
// Listing Agreement document), shown in the property's details.
import { date, peso, text } from "./format"
import { Facts, Section } from "./ui"
import { t } from "./i18n"

export type ListingAgreement = {
  agreement_date: string | null; seller_name: string; seller_address: string | null; seller_contact: string | null
  broker_name: string | null; agency_name: string | null; property_address: string | null
  tct_number: string | null; tax_declaration_number: string | null
  fixtures_excluded: string | null; personal_property_included: string | null
  rights_to_sell: string | null; listing_price: number | null; listing_start: string | null; listing_end: string | null
  extension_days: number | null; commission_type: string | null; commission_rate: number | null; commission_amount: number | null
  leasing_commission_rate: number | null; deed_type: string | null; cooperating_commission_rate: number | null
  dual_agency_allowed: boolean | null; marketing_permissions: string[] | null; governing_law: string | null
  additional_terms: string | null; source_document_id: string | null
}

const RIGHTS: Record<string, string> = {
  EXCLUSIVE_RIGHT_TO_SELL: "Exclusive right to sell", EXCLUSIVE_AGENCY: "Exclusive agency", OPEN_LISTING: "Open listing",
}
const percent = (value: number | null) => (value == null ? null : `${Number(value)}%`)

export function ListingAgreementSection({ agreement }: { agreement: ListingAgreement | null | undefined }) {
  if (!agreement) return null
  const a = agreement
  const today = new Date().toISOString().slice(0, 10)
  const expired = Boolean(a.listing_end && a.listing_end < today)
  const commission = a.commission_type === "FIXED" ? (a.commission_amount != null ? peso(a.commission_amount) : null) : percent(a.commission_rate)
  return (
    <Section title="Listing agreement">
      {expired && <p className="mb-3 rounded-lg border border-ab-warning/40 bg-ab-warning/10 px-3 py-2 text-sm text-ab-warning">{t("The listing period ended on {date}. Renew the agreement to keep marketing this property.", { date: date(a.listing_end) })}</p>}
      <Facts items={[
        ["Property owner", a.seller_name],
        ["Owner's contact", [a.seller_contact, a.seller_address].filter(Boolean).join(" · ") || null],
        ["Broker", [a.broker_name, a.agency_name].filter(Boolean).join(", ") || null],
        ["Agreement date", a.agreement_date ? date(a.agreement_date) : null],
        ["Rights to sell", a.rights_to_sell ? t(RIGHTS[a.rights_to_sell] ?? a.rights_to_sell) : null],
        ["Listing price", a.listing_price != null ? peso(a.listing_price) : null],
        ["Listing period", a.listing_start && a.listing_end ? `${date(a.listing_start)} – ${date(a.listing_end)}` : null],
        ["Extension period", a.extension_days != null ? t("{n} days", { n: a.extension_days }) : null],
        ["Commission", commission],
        ["Cooperating broker's commission", percent(a.cooperating_commission_rate)],
        ["Leasing commission", percent(a.leasing_commission_rate)],
        ["Disclosed dual agency", a.dual_agency_allowed == null ? null : t(a.dual_agency_allowed ? "Allowed" : "Not allowed")],
        ["Deed type", a.deed_type],
        ["TCT no.", a.tct_number],
        ["Tax declaration no.", a.tax_declaration_number],
        ["Fixtures excluded", a.fixtures_excluded],
        ["Personal property included", a.personal_property_included],
        ["Marketing permissions", a.marketing_permissions?.length ? a.marketing_permissions.join(" · ") : null],
        ["Governing law", a.governing_law],
        ["Additional terms", a.additional_terms],
        ["Property address", text(a.property_address)],
      ]} />
    </Section>
  )
}
