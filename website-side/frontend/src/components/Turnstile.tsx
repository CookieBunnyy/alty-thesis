import { useEffect, useRef, useState } from "react"

// Cloudflare Turnstile, loaded only when the server asks for the check. The
// site key is public; the token is verified by the API with its secret key.
type TurnstileApi = {
  render: (element: HTMLElement, options: Record<string, unknown>) => string
  remove: (id: string) => void
}
declare global {
  interface Window { turnstile?: TurnstileApi }
}

const SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
let loading: Promise<void> | null = null

function loadTurnstile(): Promise<void> {
  if (window.turnstile) return Promise.resolve()
  loading ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement("script")
    script.src = SCRIPT
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => {
      loading = null
      reject(new Error("Turnstile unavailable"))
    }
    document.head.appendChild(script)
  })
  return loading
}

/** The security check. `onToken` gets the token, or null when it expires or fails.
 *  Change `resetKey` to show a fresh check (a token works once). */
export function Turnstile({ siteKey, onToken, resetKey = 0, unavailableText = "The security check couldn't load. Check your connection and reload the page." }: {
  siteKey: string
  onToken: (token: string | null) => void
  resetKey?: number
  unavailableText?: string
}) {
  const box = useRef<HTMLDivElement | null>(null)
  const callback = useRef(onToken)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    callback.current = onToken
  })
  useEffect(() => {
    let id: string | null = null
    let alive = true
    callback.current(null)
    loadTurnstile()
      .then(() => {
        if (!alive || !box.current || !window.turnstile) return
        id = window.turnstile.render(box.current, {
          sitekey: siteKey,
          theme: "auto",
          callback: (token: string) => callback.current(token),
          "expired-callback": () => callback.current(null),
          "error-callback": () => callback.current(null),
        })
      })
      .catch(() => alive && setFailed(true))
    return () => {
      alive = false
      if (id && window.turnstile) window.turnstile.remove(id)
    }
  }, [siteKey, resetKey])
  return (
    <div className="mt-4">
      <div ref={box} className="min-h-[65px]" />
      {failed && <p role="alert" className="text-xs text-ab-danger">{unavailableText}</p>}
    </div>
  )
}
