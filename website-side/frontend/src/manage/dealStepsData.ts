// Deal steps after the reservation: shared types and labels.

export type Milestone = { key: string; label: string; applies: boolean; done_on: string | null; by: string | null; note: string | null }
export type DealFinancing = { id: number; stage: string; financing_type: string | null; equity_terms_months: number | null; milestones?: Milestone[] }

export const FINANCING_LABEL: Record<string, string> = { BANK: "Bank loan", PAGIBIG: "Pag-IBIG loan", SSS: "SSS loan", IN_HOUSE: "In-house financing", CASH: "Cash" }

/** The next step that isn't done yet (for lists). */
export function nextStep(milestones: Milestone[] | undefined): string | null {
  const next = (milestones ?? []).find((m) => m.applies && !m.done_on)
  return next ? next.label : null
}
