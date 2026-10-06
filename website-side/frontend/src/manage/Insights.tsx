// ALTY Decision Support panel: the reasoning layer's output, shown on the page
// where the decision is made (Analytics, Forecasting, a property, an agent).
import { useCallback, useState } from "react"
import { AlertOctagon, AlertTriangle, ChevronDown, Info, Lightbulb, Sparkles, TrendingUp } from "lucide-react"
import { Link } from "@/components/Link"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"
import { LoadState } from "./ui"

export type Insight = {
  id: string
  scope: string
  severity: "high" | "medium" | "positive" | "info"
  title: string
  finding: string
  recommendation: string | null
  factors: string[]
  rule: string
  subject: { type: "property" | "agent"; id: string | number; name: string | null } | null
}

const LOOK = {
  high: { label: "High priority", icon: AlertOctagon, tone: "text-ab-danger", ring: "border-ab-danger/45 bg-ab-danger/5" },
  medium: { label: "Needs attention", icon: AlertTriangle, tone: "text-ab-warning", ring: "border-ab-warning/45 bg-ab-warning/5" },
  positive: { label: "Positive", icon: TrendingUp, tone: "text-ab-success", ring: "border-ab-success/40 bg-ab-success/5" },
  info: { label: "For information", icon: Info, tone: "text-ab-info", ring: "border-ab-border bg-ab-card-2" },
} as const

const SUBJECT_PAGE = { property: "/manage/properties", agent: "/manage/agents" } as const

export function InsightCard({ insight, showSubject = false }: { insight: Insight; showSubject?: boolean }) {
  const [open, setOpen] = useState(false)
  const look = LOOK[insight.severity] ?? LOOK.info
  const Icon = look.icon
  return (
    <li className={`rounded-xl border p-3.5 ${look.ring}`}>
      <div className="flex items-start gap-2.5">
        <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${look.tone}`} aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold text-ab-text">
            <span className="sr-only">{look.label}: </span>{insight.title}
          </p>
          {showSubject && insight.subject && (
            <Link to={`${SUBJECT_PAGE[insight.subject.type]}?id=${insight.subject.id}`} className="text-xs font-semibold text-ab-accent hover:underline">
              {insight.subject.type === "property" ? "Property" : "Agent"}: {insight.subject.name ?? insight.subject.id}
            </Link>
          )}
          <p className="mt-1 text-sm text-ab-muted">{insight.finding}</p>
          {insight.recommendation && (
            <p className="mt-2 rounded-lg bg-ab-card px-3 py-2 text-sm">
              <span className="font-semibold text-ab-text">Recommendation: </span>
              <span className="text-ab-muted">{insight.recommendation}</span>
            </p>
          )}
          {(insight.factors.length > 0 || insight.rule) && (
            <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
              className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-ab-faint hover:text-ab-text">
              <ChevronDown className={`h-3.5 w-3.5 transition ${open ? "rotate-180" : ""}`} /> Supporting factors
            </button>
          )}
          {open && (
            <div className="mt-1.5 text-xs text-ab-muted">
              {insight.factors.length > 0 && <ul className="list-disc space-y-0.5 pl-5">{insight.factors.map((f) => <li key={f}>{f}</li>)}</ul>}
              <p className="mt-1.5 text-ab-faint">Rule: {insight.rule}</p>
            </div>
          )}
        </div>
      </div>
    </li>
  )
}

export function InsightList({ insights, empty, showSubject }: { insights: Insight[]; empty?: string; showSubject?: boolean }) {
  if (!insights.length) return <p className="text-sm italic text-ab-faint">{empty ?? "No insights right now."}</p>
  return <ul className="space-y-2.5">{insights.map((i) => <InsightCard key={i.id} insight={i} showSubject={showSubject} />)}</ul>
}

/** "ALTY Decision Support" box for a page section. */
export function InsightPanel({ insights, title = "ALTY Decision Support", empty }: { insights: Insight[]; title?: string; empty?: string }) {
  return (
    <section className="rounded-2xl border border-ab-accent/30 bg-ab-card p-5" aria-label={title}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-bold"><Sparkles className="h-4 w-4 text-ab-accent" /> {title}</h2>
        <p className="flex items-center gap-1 text-[11px] text-ab-faint"><Lightbulb className="h-3.5 w-3.5" /> Evidence-based suggestions — management makes the decision.</p>
      </div>
      <InsightList insights={insights} empty={empty} />
    </section>
  )
}

/** Insights for one property or agent, fetched on demand (management roles). */
export function SubjectInsights({ path, empty }: { path: string; empty: string }) {
  const { api } = useStaffAuth()
  const load = useCallback(() => api<{ insights: Insight[] }>(path), [api, path])
  const { data, error, loading, reload } = useApiData(load)
  return (
    <section className="rounded-2xl border border-ab-accent/30 bg-ab-card p-4" aria-label="ALTY Insight">
      <h3 className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-ab-faint">
        <Sparkles className="h-3.5 w-3.5 text-ab-accent" /> ALTY Insight
      </h3>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && <InsightList insights={data.insights} empty={empty} />}
    </section>
  )
}
