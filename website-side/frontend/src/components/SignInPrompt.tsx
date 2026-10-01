import { LockKeyhole, X } from "lucide-react"
import { Link } from "@/components/Link"

type Props = { next: string; action?: string; onClose: () => void }

/** Shown when a visitor tries to reserve or purchase without signing in. */
export function SignInPrompt({ next, action = "reserve or purchase a property", onClose }: Props) {
  const query = `?next=${encodeURIComponent(next)}`
  return (
    <div className="fixed inset-0 z-[2200] flex items-center justify-center bg-black/55 p-4 backdrop-blur-sm" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="signin-prompt-title"
        onClick={(event) => event.stopPropagation()}
        className="ab-pop w-full max-w-sm rounded-2xl border border-ab-border bg-ab-card p-6 text-center shadow-2xl"
      >
        <button type="button" onClick={onClose} aria-label="Close" className="float-right -mr-2 -mt-2 rounded-full p-2 text-ab-muted hover:bg-ab-hover">
          <X className="h-4 w-4" />
        </button>
        <span className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-ab-accent-soft text-ab-accent">
          <LockKeyhole className="h-6 w-6" />
        </span>
        <h2 id="signin-prompt-title" className="text-xl font-bold text-ab-text">
          Sign in to continue
        </h2>
        <p className="mt-2 text-sm text-ab-muted">
          You need an Abellar Realty client account to {action}. We'll bring you right back here afterwards.
        </p>
        <div className="mt-5 grid gap-2">
          <Link to={`/signin${query}`} className="rounded-xl bg-ab-accent px-4 py-2.5 text-sm font-semibold text-ab-ink transition hover:bg-ab-accent-hover">
            Sign In
          </Link>
          <Link to={`/signup${query}`} className="rounded-xl border border-ab-border-strong px-4 py-2.5 text-sm font-semibold text-ab-text transition hover:bg-ab-hover">
            Create an account
          </Link>
        </div>
      </div>
    </div>
  )
}
