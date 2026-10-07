import { useCallback, useMemo, useState } from "react"
import { dateTime } from "./format"
import { InsightList, type Insight } from "./Insights"
import { Button, LoadState, PageHeader, Select, Tiles } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"
import { t } from "./i18n"

type Feed = { generated_at: string; counts: Record<Insight["severity"], number>; items: Insight[] }

const SCOPES = [
  { value: "", label: "All areas" },
  { value: "analytics", label: "Market & sales" },
  { value: "forecast", label: "Forecast" },
  { value: "property", label: "Properties" },
  { value: "agent", label: "Agents" },
  { value: "operations", label: "Operations" },
]

/** Central feed of what ALTY's analysis found across the system. The same
 *  insights appear in context on Analytics, Forecasting, properties and agents. */
export function InsightsPage() {
  const { api } = useStaffAuth()
  const [severity, setSeverity] = useState<Insight["severity"] | "">("")
  const [scope, setScope] = useState("")
  const load = useCallback(() => api<Feed>("/intelligence/insights"), [api])
  const { data, error, loading, reload } = useApiData(load, "insights")
  const shown = useMemo(() => (data?.items ?? []).filter((i) => (!severity || i.severity === severity) && (!scope || i.scope === scope)), [data, severity, scope])

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <PageHeader
        title="What needs attention, and what to do next"
        subtitle="Everything ALTY's analysis currently flags, highest priority first. Each item shows the finding, a suggested action, the supporting data and the rule behind it — management makes the decision."
        actions={<Button onClick={reload}>{t("Refresh")}</Button>}
      />
      {data && (
        <Tiles items={[
          { label: "High priority", value: data.counts.high, onClick: () => setSeverity(severity === "high" ? "" : "high"), active: severity === "high" },
          { label: "Needs attention", value: data.counts.medium, onClick: () => setSeverity(severity === "medium" ? "" : "medium"), active: severity === "medium" },
          { label: "Positive", value: data.counts.positive, onClick: () => setSeverity(severity === "positive" ? "" : "positive"), active: severity === "positive" },
          { label: "For information", value: data.counts.info, onClick: () => setSeverity(severity === "info" ? "" : "info"), active: severity === "info" },
        ]} />
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Select label="Area" value={scope} onChange={setScope} options={SCOPES} />
        {data && <p className="text-xs text-ab-faint">{t("Generated {when} from current records", { when: dateTime(data.generated_at) })}</p>}
      </div>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && <InsightList insights={shown} showSubject empty={t("Nothing matches these filters.")} />}
    </div>
  )
}
