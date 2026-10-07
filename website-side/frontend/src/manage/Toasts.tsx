import { useCallback, useState, type ReactNode } from "react"
import { AlertTriangle, CheckCircle2, Info } from "lucide-react"
import { ToastContext, type ToastTone } from "./toastContext"
import { t } from "./i18n"

type Toast = { id: number; message: string; tone: ToastTone }

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const show = useCallback((message: string, tone: ToastTone = "success") => {
    const id = Date.now() + Math.random()
    setToasts((current) => [...current.slice(-2), { id, message, tone }])
    window.setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), tone === "error" ? 7000 : 4000)
  }, [])
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="pointer-events-none fixed bottom-20 right-4 z-[80] lg:bottom-4 flex w-[min(92vw,380px)] flex-col gap-2" aria-live="polite">
        {toasts.map((toast) => {
          const Icon = toast.tone === "error" ? AlertTriangle : toast.tone === "info" ? Info : CheckCircle2
          const color = toast.tone === "error" ? "text-ab-danger" : toast.tone === "info" ? "text-ab-info" : "text-ab-success"
          return (
            <p key={toast.id} role={toast.tone === "error" ? "alert" : "status"} className="ab-pop flex items-start gap-2 rounded-xl border border-ab-border-strong bg-ab-card-2 px-4 py-3 text-sm shadow-xl">
              <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${color}`} /> <span>{t(toast.message)}</span>
            </p>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
