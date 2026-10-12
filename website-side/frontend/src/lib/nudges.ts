// One-time hints ("Install the app", "Ask the assistant"): remembered in this
// browser so a dismissed hint stays away for a while.
const DAY = 24 * 60 * 60 * 1000

export function nudgeDue(key: string, days: number): boolean {
  try {
    const at = Number(localStorage.getItem(`alty.nudge.${key}`) ?? 0)
    return !at || Date.now() - at > days * DAY
  } catch {
    return true // blocked storage: show it this visit
  }
}

export function nudgeDone(key: string): void {
  try {
    localStorage.setItem(`alty.nudge.${key}`, String(Date.now()))
  } catch {
    // blocked storage: it may show again next visit
  }
}

/** Something modal (a dialog, a guided tour) is open: don't interrupt it. */
export const dialogOpen = () => Boolean(document.querySelector("[role='dialog'][aria-modal='true'], [role='alertdialog']"))
