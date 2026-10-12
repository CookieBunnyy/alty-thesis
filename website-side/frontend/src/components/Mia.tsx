import { useEffect, useState } from "react"
import { ChatBotIcon } from "./icons/ChatBotIcon"

/** MIA, the Marketing Intelligence Assistant: the site's property chatbot. */
export const MIA_NAME = "MIA"
export const MIA_FULL_NAME = "Marketing Intelligence Assistant"
export const MIA_GREETING =
  "Hi! I'm MIA, your Marketing Intelligence Assistant. What is your budget and location preference?"

/** What MIA is "doing" while a reply is on its way, shown one at a time in random order. */
const TYPING_PHRASES = [
  "MIA is typing",
  "MIA is thinking",
  "MIA is choosing the best answer",
  "MIA is checking the listings",
  "MIA is looking at the map",
  "MIA is comparing properties",
  "MIA is crunching the numbers",
  "MIA is finding homes that fit",
  "MIA is double-checking the details",
  "MIA is almost done",
]
const PHRASE_MS = 1900

/** MIA's face: the robot head on an accent circle, with an "online" dot. */
export function MiaAvatar({ size = "md", online = false }: { size?: "sm" | "md"; online?: boolean }) {
  const box = size === "sm" ? "h-6 w-6" : "h-9 w-9"
  const icon = size === "sm" ? "h-4 w-4" : "h-5 w-5"
  return (
    <span className={`relative inline-flex ${box} shrink-0 items-center justify-center rounded-full bg-ab-accent text-ab-ink shadow-sm`} aria-hidden>
      <ChatBotIcon className={icon} />
      {online && <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-ab-sidebar bg-emerald-500" />}
    </span>
  )
}

/** The chat window's title bar content: avatar, name and what MIA stands for. */
export function MiaHeader() {
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <MiaAvatar online />
      <div className="min-w-0">
        <p className="flex items-center gap-2 text-sm font-extrabold tracking-wide">
          {MIA_NAME}
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ab-accent">Online</span>
        </p>
        <p className="truncate text-[11px] text-ab-muted">{MIA_FULL_NAME}</p>
      </div>
    </div>
  )
}

/** Shown while MIA prepares a reply: bouncing dots and a phrase that
 *  fades out and is replaced by another, picked at random (never the same twice in a row). */
export function MiaTyping() {
  const [index, setIndex] = useState(0) // always starts with "MIA is typing"
  const [visible, setVisible] = useState(true)
  useEffect(() => {
    let swap: number | undefined
    const timer = window.setInterval(() => {
      setVisible(false)
      swap = window.setTimeout(() => {
        setIndex((current) => {
          let next = current
          while (next === current) next = Math.floor(Math.random() * TYPING_PHRASES.length)
          return next
        })
        setVisible(true)
      }, 250)
    }, PHRASE_MS)
    return () => {
      window.clearInterval(timer)
      window.clearTimeout(swap)
    }
  }, [])

  return (
    <div className="flex flex-col items-start gap-1" role="status" aria-live="polite">
      <div className="flex items-end gap-2">
        <MiaAvatar size="sm" />
        <div className="flex items-center gap-1 rounded-2xl rounded-bl-none bg-ab-hover px-4 py-3 shadow-sm" aria-hidden>
          <span className="mia-dot" />
          <span className="mia-dot [animation-delay:0.15s]" />
          <span className="mia-dot [animation-delay:0.3s]" />
        </div>
      </div>
      <p className={`ml-9 text-[11px] font-medium text-ab-muted transition-opacity duration-200 ${visible ? "opacity-100" : "opacity-0"}`}>
        {TYPING_PHRASES[index]}
        <span className="mia-ellipsis" aria-hidden />
      </p>
    </div>
  )
}
