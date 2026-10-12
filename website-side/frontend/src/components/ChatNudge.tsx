import { useEffect, useState } from "react"
import { X } from "lucide-react"
import { dialogOpen, nudgeDone, nudgeDue } from "@/lib/nudges"

const KEY = "chat"

/** Speech bubble beside the chat button: "the assistant answers FAQs".
 *  Shows a few seconds after the page opens, hides after a while; once the
 *  chat is opened or the bubble dismissed it stays away for 3 days. */
export function ChatNudge({ chatOpen, onOpen }: { chatOpen: boolean; onOpen: () => void }) {
  const [show, setShow] = useState(false)

  useEffect(() => {
    if (chatOpen || !nudgeDue(KEY, 3)) return
    const timer = window.setTimeout(() => !dialogOpen() && setShow(true), 3000)
    return () => window.clearTimeout(timer)
  }, [chatOpen])

  // Gone on its own after a short while, so it never gets in the way.
  useEffect(() => {
    if (!show) return
    const timer = window.setTimeout(() => setShow(false), 12000)
    return () => window.clearTimeout(timer)
  }, [show])

  // Opening the chat counts as "seen".
  useEffect(() => {
    if (chatOpen) nudgeDone(KEY)
  }, [chatOpen])

  if (!show || chatOpen) return null

  const dismiss = () => {
    nudgeDone(KEY)
    setShow(false)
  }

  return (
    <div role="status" aria-live="polite"
      className="ab-pop absolute bottom-6 right-[5.25rem] z-[1100] w-[min(15rem,calc(100vw-7rem))] rounded-2xl rounded-br-md border border-ab-border bg-ab-card py-3 pl-4 pr-9 text-left text-ab-text shadow-[0_12px_30px_rgba(12,53,41,0.25)]">
      <button type="button" onClick={onOpen} className="block text-left">
        <span className="block text-sm font-bold">Have a question? 👋</span>
        <span className="mt-0.5 block text-xs text-ab-muted">Ask me — quick answers to FAQs.</span>
      </button>
      <button type="button" onClick={dismiss} aria-label="Dismiss" className="absolute right-2 top-2 rounded-lg p-1 text-ab-faint hover:bg-ab-hover hover:text-ab-text">
        <X className="h-3.5 w-3.5" />
      </button>
      {/* Pointer towards the chat button */}
      <span aria-hidden className="absolute -right-1.5 bottom-4 h-3 w-3 rotate-45 border-r border-t border-ab-border bg-ab-card" />
    </div>
  )
}
