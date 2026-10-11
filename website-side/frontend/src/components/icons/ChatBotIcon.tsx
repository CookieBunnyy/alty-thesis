import type { SVGProps } from "react"

/** The chat assistant: a friendly robot head with an antenna, ears and a
 *  speech-bubble tail. Drawn on the same 24×24 grid and 2px rounded strokes
 *  as the lucide icons used everywhere else, and coloured by `currentColor`. */
export function ChatBotIcon({ className = "h-6 w-6", strokeWidth = 2, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth}
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true" {...props}>
      {/* antenna */}
      <circle cx="12" cy="2.9" r="1.4" />
      <path d="M12 4.3v2.2" />
      {/* head, with the speech tail at the bottom left */}
      <path d="M8.2 6.5h7.6a3.2 3.2 0 0 1 3.2 3.2v5a3.2 3.2 0 0 1-3.2 3.2h-4.2c-.5 1.6-1.9 2.6-3.6 2.6.5-.7.7-1.6.6-2.6A3.2 3.2 0 0 1 5 14.7v-5a3.2 3.2 0 0 1 3.2-3.2Z" />
      {/* ears */}
      <path d="M5 10.2H3.8a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1H5" />
      <path d="M19 10.2h1.2a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1H19" />
      {/* eyes and smile */}
      <path d="M9.6 10.4v1" />
      <path d="M14.4 10.4v1" />
      <path d="M9.9 14.1c1.3.8 2.9.8 4.2 0" />
    </svg>
  )
}
