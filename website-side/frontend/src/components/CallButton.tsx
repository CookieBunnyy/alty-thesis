// "Call" for a phone number, shared by the public site and the management pages.
// On a phone-sized screen it opens the phone's dialer with the number filled
// in; on a larger screen it shows a QR code that does the same when scanned
// with a phone's camera.
import { useEffect, useState, type ReactNode } from "react"
import { Check, Copy, Phone, X } from "lucide-react"
import QRCode from "qrcode"
import { telNumber } from "@/lib/phone"

/** Phone-sized screens dial directly (same breakpoint as the layouts). */
const PHONE_SCREEN = "(max-width: 767px)"

export type CallLabels = {
  title: string        // "Call {name}"
  textTitle: string    // "Text {name}"
  scan: string         // instructions under the QR code
  orCall: string       // "Call from this device"
  copy: string
  copied: string
  close: string
}

const ENGLISH: CallLabels = {
  title: "Call {name}",
  textTitle: "Text {name}",
  scan: "Scan this with your phone's camera. Your phone app opens with the number filled in.",
  orCall: "Open on this device",
  copy: "Copy number",
  copied: "Copied",
  close: "Close",
}

export function CallButton({ phone, name, className, children, labels = ENGLISH, kind = "call" }: {
  phone: string; name: string; className?: string; children: ReactNode; labels?: CallLabels
  /** "text" opens the messaging app instead of the dialer. */
  kind?: "call" | "text"
}) {
  const [showQr, setShowQr] = useState(false)
  const tel = `${kind === "text" ? "sms" : "tel"}:${telNumber(phone)}`
  return (
    <>
      <a
        href={tel}
        className={className}
        onClick={(event) => {
          // Phones dial straight away; larger screens show the QR code instead.
          if (!window.matchMedia(PHONE_SCREEN).matches) {
            event.preventDefault()
            setShowQr(true)
          }
        }}
      >
        {children}
      </a>
      {showQr && <CallQr tel={tel} phone={phone} title={(kind === "text" ? labels.textTitle : labels.title).replace("{name}", name)}
        labels={labels} onClose={() => setShowQr(false)} />}
    </>
  )
}

function CallQr({ tel, phone, title, labels, onClose }: { tel: string; phone: string; title: string; labels: CallLabels; onClose: () => void }) {
  const [image, setImage] = useState("")
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    let alive = true
    // Always dark on white so any phone camera can read it, in light or dark mode.
    QRCode.toDataURL(tel, { margin: 1, width: 240, errorCorrectionLevel: "M", color: { dark: "#111111", light: "#ffffff" } })
      .then((url) => { if (alive) setImage(url) })
      .catch(() => {})
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose()
    window.addEventListener("keydown", onKey)
    return () => { alive = false; window.removeEventListener("keydown", onKey) }
  }, [tel, onClose])
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(telNumber(phone))
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      // clipboard blocked: the number is shown on screen anyway
    }
  }
  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" aria-label={labels.close} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <div className="ab-pop relative w-full max-w-sm rounded-2xl border border-ab-border bg-ab-card p-6 text-center shadow-2xl">
        <button type="button" onClick={onClose} aria-label={labels.close} className="absolute right-3 top-3 rounded-lg p-2 text-ab-muted hover:bg-ab-hover">
          <X className="h-4 w-4" />
        </button>
        <h2 className="text-lg font-bold text-ab-text">{title}</h2>
        <p className="mt-0.5 text-sm font-semibold tabular-nums text-ab-muted">{phone}</p>
        <div className="mx-auto mt-4 flex h-[240px] w-[240px] items-center justify-center rounded-xl bg-white p-2">
          {image ? <img src={image} alt={`QR code for ${phone}`} width={224} height={224} /> : <span className="ab-skeleton h-full w-full rounded-lg" />}
        </div>
        <p className="mt-4 text-sm text-ab-muted">{labels.scan}</p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <button type="button" onClick={() => void copy()}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-ab-border-strong px-3.5 text-sm font-semibold text-ab-text hover:bg-ab-hover">
            {copied ? <Check className="h-4 w-4 text-ab-success" /> : <Copy className="h-4 w-4" />} {copied ? labels.copied : labels.copy}
          </button>
          <a href={tel} className="inline-flex min-h-10 items-center gap-1.5 rounded-xl bg-ab-accent px-3.5 text-sm font-semibold text-ab-ink hover:bg-ab-accent-hover">
            <Phone className="h-4 w-4" /> {labels.orCall}
          </a>
        </div>
      </div>
    </div>
  )
}
