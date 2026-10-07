import { useCallback } from "react"
import { Star } from "lucide-react"
import { Link } from "@/components/Link"
import { date, peso, statusLabel, text, transactionDate } from "./format"
import { Badge, LoadState, PageHeader, Section, Tiles } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"
import { t } from "./i18n"

type Work = {
  agent: { agent_id: string; full_name: string; agent_location: string | null; status: string; transactions_count: number; completed_sales: number; total_sales: string | null; performance_score: string | null; client_rating: number | null; review_count: number }
  activity: {
    recorded: { clients: number; transactions: number; active_reservations: number; completed_sales: number; sales_value: number; properties: number }
    clients: { client_id: string; full_name: string; status: string; property_id: number | null }[]
    transactions: { transaction_id: string; client_name: string | null; property_id: number; property_title: string | null; transaction_type: string; transaction_date: string; amount: number; status: string }[]
  }
  reviews: { client_rating: number | null; review_count: number; reviews: { id: number; rating: number; review: string | null; reviewer: string; property_title: string | null; created_at: string }[] }
}

/** The signed-in agent's own clients, transactions and reviews. Shown when
 *  the account is linked to an agent record in Users & Access. */
export function MyWorkPage() {
  const { api } = useStaffAuth()
  const load = useCallback(() => api<Work>("/agents/me/work"), [api])
  const { data, error, loading, reload } = useApiData(load)
  const open = data?.activity.transactions.filter((tx) => tx.status === "RESERVED") ?? []
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageHeader title="My Work" subtitle={data ? `${data.agent.full_name} · ${data.agent.agent_id}${data.agent.agent_location ? ` · ${data.agent.agent_location}` : ""}` : t("Your clients, transactions and client reviews.")} />
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <>
          <Tiles items={[
            { label: "My clients", value: data.activity.recorded.clients },
            { label: "Open reservations", value: data.activity.recorded.active_reservations, detail: "Waiting to become sales" },
            { label: "Completed sales", value: data.activity.recorded.completed_sales, detail: "Recorded in ALTY" },
            { label: "Sales value", value: peso(data.activity.recorded.sales_value), detail: "Recorded in ALTY" },
            { label: "Client rating", value: data.reviews.client_rating != null ? `${data.reviews.client_rating.toFixed(1)} ★` : "—", detail: t("{n} verified review(s)", { n: data.reviews.review_count }) },
          ]} />
          <div className="grid gap-5 lg:grid-cols-2">
            <Section title={`${t("Open reservations")} (${open.length})`}>
              {open.length === 0 ? <p className="text-sm italic text-ab-faint">{t("No open reservations.")}</p> : (
                <ul className="space-y-2">
                  {open.map((tx) => (
                    <li key={tx.transaction_id} className="rounded-xl border border-ab-border p-3 text-sm">
                      <p className="font-semibold">{text(tx.client_name)} · {peso(tx.amount)}</p>
                      <p className="text-xs text-ab-muted">
                        <Link to={`/manage/properties?id=${tx.property_id}`} className="hover:underline">{text(tx.property_title)}</Link> · {t("reserved {date}", { date: transactionDate(tx.transaction_date) })}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
            <Section title={`${t("My clients")} (${data.activity.clients.length})`}>
              {data.activity.clients.length === 0 ? <p className="text-sm italic text-ab-faint">{t("No clients assigned yet.")}</p> : (
                <ul className="space-y-1.5">
                  {data.activity.clients.map((c) => (
                    <li key={c.client_id} className="flex items-center justify-between gap-2 text-sm">
                      <Link to={`/manage/clients?id=${c.client_id}`} className="truncate font-semibold hover:underline">{c.full_name}</Link>
                      <Badge value={c.status} />
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          </div>
          <Section title="All my transactions">
            {data.activity.transactions.length === 0 ? <p className="text-sm italic text-ab-faint">{t("No transactions recorded yet.")}</p> : (
              <ul className="space-y-2">
                {data.activity.transactions.map((tx) => (
                  <li key={tx.transaction_id} className="flex items-start justify-between gap-2 rounded-xl border border-ab-border p-3 text-sm">
                    <span className="min-w-0">
                      <Link to={`/manage/transactions?id=${tx.transaction_id}`} className="font-semibold hover:underline">{statusLabel(tx.transaction_type)} · {peso(tx.amount)}</Link>
                      <span className="block text-xs text-ab-muted">{transactionDate(tx.transaction_date)} · {text(tx.client_name)} · {text(tx.property_title)}</span>
                    </span>
                    <Badge value={tx.status} />
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <Section title="Client reviews">
            {data.reviews.reviews.length === 0 ? <p className="text-sm italic text-ab-faint">{t("No client reviews yet.")}</p> : (
              <ul className="space-y-2">
                {data.reviews.reviews.map((r) => (
                  <li key={r.id} className="rounded-xl border border-ab-border p-3 text-sm">
                    <p className="flex items-center gap-1 font-semibold">
                      {Array.from({ length: 5 }, (_, i) => <Star key={i} className={`h-3.5 w-3.5 ${i < r.rating ? "fill-ab-warning text-ab-warning" : "text-ab-faint"}`} />)}
                      <span className="ml-1 font-normal text-ab-muted">{r.reviewer} · {date(r.created_at)}</span>
                    </p>
                    {r.review && <p className="mt-1 text-ab-muted">{r.review}</p>}
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <p className="text-xs text-ab-faint">
            {t("From your agent record (synced): {n} transactions, {s} completed sales", { n: data.agent.transactions_count, s: data.agent.completed_sales })}
            {data.agent.performance_score ? `, ${t("performance {v}%", { v: Number(data.agent.performance_score).toFixed(1) })}` : ""}.
          </p>
        </>
      )}
    </div>
  )
}
