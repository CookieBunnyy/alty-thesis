// Shared list filters: a Year / Quarter / Month period picker and a Team picker.
import { useMemo } from "react"
import { Select } from "./ui"
import { ALL_TIME, manilaMonth, monthName, nowMonth, quarterOf, type Period } from "./period"

/** Year, Quarter and Month dropdowns. Years come from the records' dates (and this year). */
export function PeriodFilter({ value, onChange, dates }: { value: Period; onChange: (period: Period) => void; dates: (string | null | undefined)[] }) {
  const years = useMemo(() => {
    const found = new Set(dates.filter(Boolean).map((d) => manilaMonth(d!).slice(0, 4)))
    found.add(nowMonth().slice(0, 4))
    if (value.year) found.add(value.year)
    return [...found].sort().reverse()
  }, [dates, value.year])
  const months = Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, "0"))
    .filter((m) => !value.quarter || quarterOf(Number(m)) === value.quarter)

  return (
    <>
      <Select label="Year" value={value.year}
        onChange={(year) => onChange(year ? { ...value, year } : ALL_TIME)}
        options={[{ value: "", label: "All years" }, ...years.map((y) => ({ value: y, label: y }))]} />
      {value.year && (
        <Select label="Quarter" value={value.quarter}
          onChange={(quarter) => onChange({ ...value, quarter, month: quarter && value.month && quarterOf(Number(value.month)) !== quarter ? "" : value.month })}
          options={[{ value: "", label: "Whole year" }, ...["1", "2", "3", "4"].map((q) => ({ value: q, label: `Q${q}` }))]} />
      )}
      {value.year && (
        <Select label="Month" value={value.month}
          onChange={(month) => onChange({ ...value, month, quarter: month ? quarterOf(Number(month)) : value.quarter })}
          options={[{ value: "", label: value.quarter ? "All months in the quarter" : "All months" }, ...months.map((m) => ({ value: m, label: monthName(m) }))]} />
      )}
    </>
  )
}

/** Team / cluster dropdown; "0" = records without a team. */
export function TeamFilter({ value, onChange, teams, includeNone = true }: {
  value: string; onChange: (team: string) => void; teams: { id: number | string; name: string }[]; includeNone?: boolean
}) {
  return (
    <Select label="Team / Cluster" value={value} onChange={onChange} options={[
      { value: "", label: "All teams" },
      ...teams.map((team) => ({ value: String(team.id), label: team.name })),
      ...(includeNone ? [{ value: "0", label: "No team" }] : []),
    ]} />
  )
}
