import type { AnchorHTMLAttributes, MouseEvent } from "react"
import { navigate } from "@/lib/router"

/** Same-site link that navigates without reloading the page. */
export function Link({ to, onClick, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & { to: string }) {
  const handle = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event)
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey) return
    if (props.target && props.target !== "_self") return
    event.preventDefault()
    navigate(to)
  }
  return <a href={to} onClick={handle} {...props} />
}
