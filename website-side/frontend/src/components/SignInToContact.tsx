import type { ReactNode } from "react"
import { Link } from "./Link"
import { useLocation } from "@/lib/router"

/** Agents' phone numbers are for signed-in clients (the API withholds them
 *  otherwise). Without children: a short note with Sign In / Create account
 *  links; with children: a single button. Both return here after signing in. */
export function SignInToContact({ children, compact = false, returnTo }: { children?: ReactNode; compact?: boolean; returnTo?: string }) {
  const { href } = useLocation()
  const next = encodeURIComponent(returnTo ?? href)

  if (children) {
    return (
      <Link
        to={`/signin?next=${next}`}
        className={
          compact
            ? "inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-ab-accent/60 bg-ab-accent-soft px-3 text-xs font-semibold text-ab-text transition hover:bg-ab-hover"
            : "inline-flex items-center gap-2 rounded-xl bg-ab-accent px-4 py-2.5 text-sm font-semibold text-ab-ink transition hover:bg-ab-accent-hover"
        }
      >
        {children}
      </Link>
    )
  }
  return (
    <p className="rounded-lg border border-ab-border bg-ab-card-2 px-3 py-2 text-xs text-ab-muted">
      Sign in to call or text an agent.{" "}
      <Link to={`/signin?next=${next}`} className="font-semibold text-ab-accent hover:underline">Sign In</Link>
      {" · "}
      <Link to={`/signup?next=${next}`} className="font-semibold text-ab-accent hover:underline">Create account</Link>
    </p>
  )
}
