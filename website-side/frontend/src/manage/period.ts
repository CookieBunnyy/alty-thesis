// Period helpers for list filters (see filters.tsx). Dates are read in
// Philippine time, so a 30 Sept 11 pm record stays in September.
import { locale, t } from "./i18n"

/** "" means "all" at that level. */
export type Period = { year: string; quarter: string; month: string }

export const ALL_TIME: Period = { year: "", quarter: "", month: "" }

/** "2026-09" for a date, in Philippine time. */
export const manilaMonth = (iso: string) => new Date(iso).toLocaleDateString("en-CA", { timeZone: "Asia/Manila" }).slice(0, 7)

export const nowMonth = () => manilaMonth(new Date().toISOString())
export const quarterOf = (month: number) => String(Math.floor((month - 1) / 3) + 1)

export function thisMonth(): Period {
  const [year, month] = nowMonth().split("-")
  return { year, quarter: quarterOf(Number(month)), month }
}

export function thisYear(): Period {
  return { year: nowMonth().slice(0, 4), quarter: "", month: "" }
}

/** Does a date fall in the period? Records without a date only show for "all years". */
export function inPeriod(iso: string | null | undefined, period: Period): boolean {
  if (!period.year) return true
  if (!iso) return false
  const [year, month] = manilaMonth(iso).split("-")
  if (year !== period.year) return false
  if (period.month) return month === period.month
  if (period.quarter) return quarterOf(Number(month)) === period.quarter
  return true
}

export const monthName = (month: string) => new Date(2000, Number(month) - 1, 1).toLocaleDateString(locale(), { month: "long" })

/** "September 2026", "Q3 2026", "2026" or "all time". */
export function periodLabel(period: Period): string {
  if (!period.year) return t("all time")
  if (period.month) return `${monthName(period.month)} ${period.year}`
  if (period.quarter) return `Q${period.quarter} ${period.year}`
  return period.year
}

/** Matches a record's team id against the TeamFilter value. */
export const inTeam = (teamId: number | null | undefined, team: string) => !team || String(teamId ?? 0) === team
