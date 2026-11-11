// What happens after the reservation is sent to the developer (second
// interview): documents, equity, loan application and approval (LOG),
// inspection and turnover, full payment and title. Company staff tick the
// steps; sellers see them.
import { useState } from "react"
import { CheckCircle2, Circle, LoaderCircle } from "lucide-react"
import { Section } from "./ui"
import { canFile, date, isManagement } from "./format"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { t } from "./i18n"
import { FINANCING_LABEL, type DealFinancing, type Milestone } from "./dealStepsData"

const GROUPS: { title: string; keys: string[] }[] = [
  { title: "Documents from the buyer", keys: ["DOC_RESERVATION_AGREEMENT", "DOC_BUYER_INFO_SHEET", "DOC_VALID_IDS", "DOC_PROOF_OF_INCOME"] },
  { title: "Payments and financing", keys: ["EQUITY_PAID", "LOAN_APPLIED", "LOAN_APPROVED"] },
  { title: "Turnover and title", keys: ["TURNOVER", "FULLY_PAID"] },
]
const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"

export function DealSteps({ deal, financingTypes, onChanged }: { deal: DealFinancing; financingTypes: string[]; onChanged: () => void | Promise<void> }) {
  const { api, user } = useStaffAuth()
  const toast = useToast()
  const [busy, setBusy] = useState<string | null>(null)
  const company = canFile(user?.role)
  const manage = isManagement(user?.role)
  const started = ["RESERVED", "DEVELOPER_PROCESSING", "CLOSED"].includes(deal.stage)
  const steps = deal.milestones ?? []
  if (!started) return null

  const run = async (key: string, request: Promise<unknown>, done: string) => {
    setBusy(key)
    try {
      await request
      toast(done)
      await onChanged()
    } catch (actionError) {
      toast(t((actionError as Error).message), "error")
    } finally {
      setBusy(null)
    }
  }
  const tick = (m: Milestone) => run(m.key, api(`/deals/${deal.id}/milestones`, { method: "PUT", body: JSON.stringify({ key: m.key, done: !m.done_on }) }),
    t(m.done_on ? "Marked as not done." : "Marked as done."))
  const saveFinancing = (body: Record<string, unknown>) => run("financing", api(`/deals/${deal.id}`, { method: "PUT", body: JSON.stringify(body) }), t("Saved."))
  const done = steps.filter((m) => m.applies && m.done_on).length
  const total = steps.filter((m) => m.applies).length

  return (
    <Section title={t("After the reservation")}>
      <div className="mb-3 grid gap-3 sm:grid-cols-2">
        <label className="text-sm font-medium">{t("Financing")}
          <select className={field} value={deal.financing_type ?? ""} disabled={!manage || busy !== null}
            onChange={(e) => void saveFinancing({ financing_type: e.target.value || null })}>
            <option value="">{t("Not set yet")}</option>
            {financingTypes.map((f) => <option key={f} value={f}>{t(FINANCING_LABEL[f] ?? f)}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">{t("Equity terms (months)")}
          <select className={field} value={deal.equity_terms_months ?? ""} disabled={!manage || busy !== null}
            onChange={(e) => void saveFinancing({ equity_terms_months: e.target.value ? Number(e.target.value) : null })}>
            <option value="">{t("Not set yet")}</option>
            {[1, 3, 6, 9, 12, 15, 18, 24, 30, 36].map((n) => <option key={n} value={n}>{n === 1 ? t("Paid at once") : t("{n} months", { n })}</option>)}
          </select>
        </label>
      </div>
      <p className="mb-2 text-xs text-ab-muted">{t("{done} of {total} steps done.", { done, total })} {company && t("Tick each step when it's done; the deal closes when the sale is recorded.")}</p>
      <div className="space-y-3">
        {GROUPS.map((group) => (
          <div key={group.title}>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ab-faint">{t(group.title)}</p>
            <ul className="space-y-1">
              {group.keys.map((key) => steps.find((m) => m.key === key)).filter((m): m is Milestone => Boolean(m)).map((m) => (
                <li key={m.key}>
                  <button type="button" disabled={!company || !m.applies || busy !== null} onClick={() => void tick(m)}
                    className={`flex w-full items-start gap-2 rounded-xl border px-3 py-2 text-left text-sm transition ${m.done_on ? "border-ab-success/40 bg-ab-success/5" : "border-ab-border"} ${company && m.applies ? "hover:bg-ab-hover" : "cursor-default"} ${m.applies ? "" : "opacity-50"}`}>
                    {busy === m.key ? <LoaderCircle className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />
                      : m.done_on ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ab-success" /> : <Circle className="mt-0.5 h-4 w-4 shrink-0 text-ab-faint" />}
                    <span className="min-w-0">
                      <span className="block font-medium">{t(m.label)}</span>
                      <span className="block text-xs text-ab-faint">
                        {!m.applies ? t("Not needed for this financing")
                          : m.done_on ? `${date(m.done_on)}${m.by ? ` · ${m.by}` : ""}${m.note ? ` · ${m.note}` : ""}` : t("Not done yet")}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Section>
  )
}
