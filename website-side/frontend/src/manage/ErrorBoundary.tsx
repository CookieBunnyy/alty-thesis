import { Component, type ReactNode } from "react"
import { AlertTriangle } from "lucide-react"
import { t } from "./i18n"

/** Keeps a page error from blanking the whole Management System: the menu
 *  stays usable and the user sees what failed. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div role="alert" className="mx-auto max-w-lg rounded-2xl border border-ab-danger/40 bg-ab-card p-6 text-center">
        <AlertTriangle className="mx-auto h-7 w-7 text-ab-danger" />
        <p className="mt-2 font-bold">{t("This page couldn't be displayed")}</p>
        <p className="mt-1 break-words text-sm text-ab-muted">{this.state.error.message}</p>
        <button type="button" onClick={() => this.setState({ error: null })} className="mt-4 rounded-xl border border-ab-border-strong px-4 py-2 text-sm font-semibold hover:bg-ab-hover">
          {t("Try again")}
        </button>
      </div>
    )
  }
}
