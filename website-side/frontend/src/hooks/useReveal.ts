import { useEffect, useRef, useState } from "react"

export const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches

/** Adds `is-visible` once the element scrolls into view (CSS does the
 *  animation; see .reveal in index.css). Reduced motion shows it at once. */
export function useReveal<T extends HTMLElement>() {
  const ref = useRef<T | null>(null)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    if (prefersReducedMotion() || !("IntersectionObserver" in window)) {
      element.classList.add("is-visible")
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible")
            observer.unobserve(entry.target)
          }
        }
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.12 },
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
