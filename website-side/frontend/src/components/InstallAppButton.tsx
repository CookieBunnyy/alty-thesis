import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { Download, X } from "lucide-react"
import { useInstall, type AppArea, type InstallPlatform } from "@/lib/pwa"

const NAMES: Record<AppArea, string> = { site: "Abellar Realty", manage: "Alty MSA" }

// Where each browser keeps "install" when it can't be started from the page.
const STEPS: Record<InstallPlatform, string[]> = {
  ios: [
    "Tap the Share button in Safari (the square with an arrow).",
    "Choose \"Add to Home Screen\".",
    "Tap \"Add\". The app appears on your home screen.",
  ],
  safari: [
    "In Safari's menu bar choose File, then \"Add to Dock\".",
    "Click \"Add\". The app opens in its own window from the Dock or Launchpad.",
  ],
  firefox: [
    "Firefox can't install web apps on this device.",
    "Open this page in Chrome or Microsoft Edge, then press Install app.",
  ],
  chromium: [
    "If the app is already installed, open it from your home screen, desktop or Start menu.",
    "Otherwise open the browser menu (the three dots) and choose \"Install app\" or \"Add to Home screen\".",
  ],
}

type Props = {
  area: AppArea
  /** Over a photo (the public home page header). */
  overlay?: boolean
  /** Translator for the management system's language setting. */
  translate?: (text: string) => string
  className?: string
}

/** "Install app": installs this part of the site as its own app. */
export function InstallAppButton({ area, overlay = false, translate = (text) => text, className = "" }: Props) {
  const { hidden, canPrompt, platform, install } = useInstall(area)
  const [helpOpen, setHelpOpen] = useState(false)
  const tr = translate
  if (hidden) return null

  const onClick = async () => {
    if (canPrompt && (await install())) return
    setHelpOpen(true)
  }

  return (
    <>
      <button
        type="button"
        onClick={onClick}
        title={tr(`Install ${NAMES[area]} as an app`)}
        aria-label={tr(`Install ${NAMES[area]} as an app`)}
        className={`inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg border px-2.5 text-sm font-semibold transition ${
          overlay
            ? "border-white/30 bg-white/10 text-white hover:bg-white/20"
            : "border-ab-border-strong bg-ab-card-2 text-ab-text hover:bg-ab-hover"
        } ${className}`}
      >
        <Download className="h-4 w-4" />
        <span className="hidden sm:inline">{tr("Install app")}</span>
      </button>
      {helpOpen && <InstallHelp name={NAMES[area]} steps={STEPS[platform]} tr={tr} onClose={() => setHelpOpen(false)} />}
    </>
  )
}

function InstallHelp({ name, steps, tr, onClose }: { name: string; steps: string[]; tr: (text: string) => string; onClose: () => void }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose()
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [onClose])
  // Portal: headers with backdrop blur would otherwise trap a fixed overlay.
  return createPortal(
    <div className="fixed inset-0 z-[3000] flex items-end justify-center bg-black/50 p-4 sm:items-center" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="install-help-title"
        onClick={(event) => event.stopPropagation()}
        className="ab-pop w-full max-w-sm rounded-2xl border border-ab-border bg-ab-card p-5 text-left text-ab-text shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3">
          <h2 id="install-help-title" className="text-lg font-extrabold">{tr(`Install ${name}`)}</h2>
          <button type="button" onClick={onClose} aria-label={tr("Close")} className="rounded-lg p-1 text-ab-muted hover:bg-ab-hover">
            <X className="h-5 w-5" />
          </button>
        </div>
        <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-ab-muted">
          {steps.map((step) => <li key={step}>{tr(step)}</li>)}
        </ol>
        <button type="button" onClick={onClose} className="mt-5 w-full rounded-xl bg-ab-accent py-2.5 text-sm font-semibold text-ab-ink hover:bg-ab-accent-hover">
          {tr("Got it")}
        </button>
      </div>
    </div>,
    document.body,
  )
}
