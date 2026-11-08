// Property drawer: developer accreditation, marketing approval and the
// sellers marketing the listing (/property-listings/{id}/marketing, /sellers).
import { useCallback, useState } from "react"
import { BadgeCheck, CircleAlert, LoaderCircle, Megaphone, UserMinus, UserPlus } from "lucide-react"
import { Link } from "@/components/Link"
import { date, dateTime } from "./format"
import { Button, LoadState, Section } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData } from "./useApiData"
import { t } from "./i18n"

type Marketing = {
  status: "DRAFT" | "APPROVED" | "WITHDRAWN"; approved_by: string | null; approved_at: string | null
  accreditation: { valid: boolean; status: string; reason: string | null; developer?: string; partner_id?: number; reference?: string | null; valid_until?: string | null }
  can_approve: boolean; public: boolean
  sellers: { agent_id: string; full_name: string; assigned_by: string | null; assigned_at: string }[]
}
type SellerOption = { agent_id: string; full_name: string; status: string }

const TONE: Record<string, string> = {
  APPROVED: "bg-ab-success/15 text-ab-success", DRAFT: "bg-ab-hover text-ab-muted", WITHDRAWN: "bg-ab-warning/15 text-ab-warning",
}
const LABEL: Record<string, string> = { APPROVED: "Approved for marketing", DRAFT: "Not approved", WITHDRAWN: "Withdrawn" }

export function MarketingBadge({ status }: { status?: string }) {
  const key = status ?? "DRAFT"
  return <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ${TONE[key] ?? TONE.DRAFT}`}>{t(LABEL[key] ?? key)}</span>
}

const REASONS: Record<string, string> = {
  NO_DEVELOPER: "No developer is recorded for this listing. Set its developer / partner first.",
  NOT_DEVELOPER: "The partner on this listing isn't recorded as a developer.",
  NONE: "The developer's accreditation of Abellar Realty isn't recorded yet.",
  PENDING: "The developer's accreditation of Abellar Realty is still pending.",
  EXPIRED: "The developer's accreditation of Abellar Realty has expired.",
  REVOKED: "The developer's accreditation of Abellar Realty was revoked.",
}

export function ListingMarketing({ listingId, canManage }: { listingId: number; canManage: boolean }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const load = useCallback(() => api<Marketing>(`/property-listings/${listingId}/marketing`), [api, listingId])
  const { data, error, loading, reload } = useApiData(load)
  const loadSellers = useCallback(() => (canManage ? api<SellerOption[]>("/agents") : Promise.resolve([])), [api, canManage])
  const sellers = useApiData(loadSellers, canManage ? "seller-options" : undefined)
  const [busy, setBusy] = useState(false)
  const [pick, setPick] = useState("")

  const run = async (request: Promise<Marketing>, done: string) => {
    setBusy(true)
    try {
      await request
      toast(done)
      await reload()
    } catch (actionError) {
      toast(t((actionError as Error).message), "error")
    } finally {
      setBusy(false)
    }
  }
  const acc = data?.accreditation
  const taken = new Set(data?.sellers.map((s) => s.agent_id))
  return (
    <Section title="Accreditation & marketing">
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && acc && (
        <div className="space-y-3 text-sm">
          <div className={`flex gap-2 rounded-xl border p-3 ${acc.valid ? "border-ab-success/40 bg-ab-success/5" : "border-ab-warning/40 bg-ab-warning/5"}`}>
            {acc.valid ? <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-ab-success" aria-hidden /> : <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-ab-warning" aria-hidden />}
            <div className="min-w-0">
              <p className="font-semibold">
                {acc.valid ? t("Accredited by {developer}", { developer: acc.developer ?? "" }) : t("Not accredited")}
              </p>
              <p className="text-xs text-ab-muted">
                {acc.valid
                  ? [acc.reference && t("Reference {ref}", { ref: acc.reference }), acc.valid_until && t("valid until {d}", { d: date(acc.valid_until) })].filter(Boolean).join(" · ") || t("No expiry recorded")
                  : t(REASONS[acc.status] ?? acc.reason ?? "")}
                {acc.partner_id && <> · <Link to={`/manage/partners?id=${acc.partner_id}`} className="font-semibold text-ab-accent hover:underline">{t("Open developer")}</Link></>}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="flex flex-wrap items-center gap-2">
              <MarketingBadge status={data.status} />
              <span className="text-xs text-ab-faint">
                {data.public ? t("Shown on the website") : t("Not shown on the website")}
                {data.status === "APPROVED" && data.approved_by ? ` · ${data.approved_at ? t("approved by {name}, {when}", { name: data.approved_by, when: dateTime(data.approved_at) }) : t("approved by {name}", { name: data.approved_by })}` : ""}
              </span>
            </span>
            {canManage && (data.status === "APPROVED" ? (
              <Button disabled={busy} onClick={() => void run(api(`/property-listings/${listingId}/marketing`, { method: "POST", body: JSON.stringify({ action: "withdraw" }) }), t("Withdrawn from marketing."))}>
                {t("Withdraw from marketing")}
              </Button>
            ) : (
              <Button variant="primary" disabled={busy || !data.can_approve} title={data.can_approve ? undefined : t("Needs verified developer accreditation")}
                onClick={() => void run(api(`/property-listings/${listingId}/marketing`, { method: "POST", body: JSON.stringify({ action: "approve" }) }), t("Approved for marketing."))}>
                {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Megaphone className="h-4 w-4" />} {t("Approve for marketing")}
              </Button>
            ))}
          </div>

          <div>
            <p className="text-xs font-bold uppercase tracking-wide text-ab-faint">{t("Sellers marketing this listing")}</p>
            {data.sellers.length === 0 ? <p className="mt-1 text-sm italic text-ab-faint">{t("No seller assigned yet.")}</p> : (
              <ul className="mt-1 space-y-1">
                {data.sellers.map((s) => (
                  <li key={s.agent_id} className="flex items-center justify-between gap-2 rounded-lg border border-ab-border px-3 py-2">
                    <span className="min-w-0">
                      <Link to={`/manage/agents?id=${s.agent_id}`} className="font-semibold hover:underline">{s.full_name}</Link>
                      <span className="block text-xs text-ab-faint">{t("Assigned {when} by {name}", { when: date(s.assigned_at), name: s.assigned_by ?? "—" })}</span>
                    </span>
                    {canManage && (
                      <button type="button" disabled={busy} aria-label={t("Remove {name}", { name: s.full_name })}
                        onClick={() => void run(api(`/property-listings/${listingId}/sellers/${encodeURIComponent(s.agent_id)}`, { method: "DELETE" }), t("Seller removed."))}
                        className="rounded-lg p-1.5 text-ab-danger hover:bg-ab-hover"><UserMinus className="h-4 w-4" /></button>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {canManage && (
              <div className="mt-2 flex flex-wrap gap-2">
                <select aria-label={t("Seller to assign")} value={pick} onChange={(e) => setPick(e.target.value)}
                  className="min-h-10 min-w-0 flex-1 rounded-xl border border-ab-border bg-ab-input px-3 text-sm">
                  <option value="">{t("Choose a seller…")}</option>
                  {(sellers.data ?? []).filter((s) => s.status === "ACTIVE" && !taken.has(s.agent_id)).map((s) => <option key={s.agent_id} value={s.agent_id}>{s.full_name}</option>)}
                </select>
                <Button disabled={!pick || busy} onClick={() => { const id = pick; setPick(""); void run(api(`/property-listings/${listingId}/sellers`, { method: "POST", body: JSON.stringify({ agent_id: id }) }), t("Seller assigned.")) }}>
                  <UserPlus className="h-4 w-4" /> {t("Assign")}
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </Section>
  )
}
