import { useEffect, useState } from "react"
import { useActivity } from "@/lib/loading"

type Phase = "idle" | "running" | "finishing"

/** Thin bar at the top of the window while the site waits for the server.
 *  Appears after a short delay (no flicker on instant responses), creeps
 *  forward while waiting, then completes and fades out. */
export function TopProgressBar() {
  const busy = useActivity()
  const [phase, setPhase] = useState<Phase>("idle")

  useEffect(() => {
    if (busy) {
      const timer = window.setTimeout(() => setPhase("running"), 120)
      return () => window.clearTimeout(timer)
    }
    // Finish the bar only if it was shown, then hide it.
    const finish = window.setTimeout(() => setPhase((current) => (current === "running" ? "finishing" : "idle")), 0)
    const hide = window.setTimeout(() => setPhase("idle"), 450)
    return () => {
      window.clearTimeout(finish)
      window.clearTimeout(hide)
    }
  }, [busy])

  return (
    <div
      role="progressbar"
      aria-label="Loading"
      aria-hidden={phase === "idle"}
      aria-busy={phase === "running"}
      className="pointer-events-none fixed inset-x-0 top-0 z-[3000] h-[3px]"
    >
      <div className={`ab-progress h-full bg-ab-accent shadow-[0_0_10px_var(--color-ab-accent)] ab-progress-${phase}`} />
    </div>
  )
}
