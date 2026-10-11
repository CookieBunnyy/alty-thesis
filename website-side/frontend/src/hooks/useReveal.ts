import { useEffect, useRef, useState } from "react"

export const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches

/** Adds `is-visible` when the element scrolls into view and removes it once
 *  it is fully out of view again, so the animation replays each time the
 *  section is reached (CSS does the animation; see .reveal in index.css).
 *  `onChange` hears each enter/leave. Reduced motion only fades (index.css). */
export function useReveal<T extends HTMLElement>(onChange?: (visible: boolean) => void) {
  const ref = useRef<T | null>(null)
  const changed = useRef(onChange)
  useEffect(() => {
    changed.current = onChange
  })
  useEffect(() => {
    const element = ref.current
    if (!element) return
    // Reduced motion still fades (CSS drops the movement), so it observes too.
    if (!("IntersectionObserver" in window)) {
      element.classList.add("is-visible")
      changed.current?.(true)
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const shown = entry.target.classList.contains("is-visible")
          if (entry.isIntersecting && entry.intersectionRatio >= 0.12 && !shown) {
            entry.target.classList.add("is-visible")
            changed.current?.(true)
          } else if (!entry.isIntersecting && shown) {
            entry.target.classList.remove("is-visible")
            changed.current?.(false)
          }
        }
      },
      { rootMargin: "0px 0px -10% 0px", threshold: [0, 0.12] },
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return ref
}

/** Counts up to `target` once visible (a real number, only animated). */
export function useCountUp(target: number, durationMs = 1100) {
  const ref = useRef<HTMLElement | null>(null)
  const [value, setValue] = useState(0)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    let frame = 0
    const run = () => {
      if (prefersReducedMotion()) {
        setValue(target)
        return
      }
      const start = performance.now()
      const tick = (now: number) => {
        const progress = Math.min(1, (now - start) / durationMs)
        setValue(Math.round(target * (1 - Math.pow(1 - progress, 3))))
        if (progress < 1) frame = requestAnimationFrame(tick)
      }
      frame = requestAnimationFrame(tick)
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        observer.disconnect()
        run()
      }
    })
    observer.observe(element)
    return () => {
      observer.disconnect()
      cancelAnimationFrame(frame)
    }
  }, [target, durationMs])
  return { ref, value }
}
