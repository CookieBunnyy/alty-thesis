// Help for newcomers: tooltips, "?" help tips and guided tours.
//
// Tooltip — shows on mouse hover (after a short delay) and on keyboard focus,
// Esc hides it, and screen readers get the same text through aria-describedby.
// HelpTip — a small "?" button next to a term; tap or click it on touch screens.
// Tours — step-by-step pop-ups that point at parts of the page marked with
// data-tour="…". The welcome tour runs once after the first sign-in and each
// page's tour runs the first time that page is opened (see tours.ts). The Help
// button in the top bar (or the "?" key) replays them; Settings turns them off.
import {
  cloneElement, useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState,
  type KeyboardEvent, type ReactElement, type ReactNode,
} from "react"
import { createPortal } from "react-dom"
import { ArrowLeft, ArrowRight, Check, CircleHelp, Compass, Map as MapIcon, X } from "lucide-react"
import { useLocation } from "@/lib/router"
import { useStaffAuth } from "./staffContext"
import { glossary } from "./glossary"
import { TOURS, type TourStep } from "./tours"
import { GuideContext, useGuide, type GuideApi } from "./guideContext"
import { t } from "./i18n"

// ---------------------------------------------------------------- tooltips

type Side = "top" | "bottom" | "right"

export function Tooltip({ content, children, side = "top", openOnClick = false, className = "inline-flex" }: {
  content: ReactNode; children: ReactElement<Record<string, unknown>>; side?: Side; openOnClick?: boolean; className?: string
}) {
  const id = useId()
  const anchor = useRef<HTMLSpanElement>(null)
  const bubble = useRef<HTMLSpanElement>(null)
  const timer = useRef<number | undefined>(undefined)
  const [open, setOpen] = useState(false)

  const show = (delay: number) => {
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setOpen(true), delay)
  }
  const hide = useCallback(() => {
    window.clearTimeout(timer.current)
    setOpen(false)
  }, [])
  useEffect(() => () => window.clearTimeout(timer.current), [])

  // Place the bubble next to its element, inside the window.
  useLayoutEffect(() => {
    if (!open || !anchor.current || !bubble.current) return
    const a = anchor.current.getBoundingClientRect()
    const b = bubble.current.getBoundingClientRect()
    const gap = 8
    let place = side
    if (place === "right" && a.right + gap + b.width > window.innerWidth - 8) place = "top"
    if (place === "top" && a.top - gap - b.height < 8) place = "bottom"
    const left = place === "right" ? a.right + gap : a.left + a.width / 2 - b.width / 2
    const top = place === "right" ? a.top + a.height / 2 - b.height / 2 : place === "top" ? a.top - gap - b.height : a.bottom + gap
    bubble.current.style.left = `${Math.max(8, Math.min(left, window.innerWidth - b.width - 8))}px`
    bubble.current.style.top = `${Math.max(8, Math.min(top, window.innerHeight - b.height - 8))}px`
    bubble.current.style.visibility = "visible"
  }, [open, side])

  // Esc, scrolling or a tap elsewhere hides it.
  useEffect(() => {
    if (!open) return
    const onKey = (e: globalThis.KeyboardEvent) => e.key === "Escape" && hide()
    const onDown = (e: PointerEvent) => anchor.current && !anchor.current.contains(e.target as Node) && hide()
    window.addEventListener("keydown", onKey)
    window.addEventListener("scroll", hide, true)
    document.addEventListener("pointerdown", onDown)
    return () => {
      window.removeEventListener("keydown", onKey)
      window.removeEventListener("scroll", hide, true)
      document.removeEventListener("pointerdown", onDown)
    }
  }, [open, hide])

  const describedBy = [children.props["aria-describedby"], id].filter(Boolean).join(" ")
  return (
    <span
      ref={anchor}
      className={className}
      onPointerEnter={(e) => e.pointerType === "mouse" && show(350)}
      onPointerLeave={(e) => e.pointerType === "mouse" && hide()}
      onFocus={() => show(0)}
      onBlur={hide}
      onClick={openOnClick ? () => show(0) : undefined}
    >
      {cloneElement(children, { "aria-describedby": describedBy })}
      {/* Always in the page for screen readers; the visible bubble is drawn above everything. */}
      <span id={id} hidden>{content}</span>
      {open && createPortal(
        <span ref={bubble} aria-hidden style={{ visibility: "hidden" }}
          className="pointer-events-none fixed z-[100] max-w-[min(18rem,calc(100vw-16px))] rounded-lg border border-ab-border-strong bg-ab-sidebar px-2.5 py-1.5 text-left text-xs font-medium normal-case leading-snug tracking-normal text-ab-text shadow-xl">
          {content}
        </span>,
        document.body,
      )}
    </span>
  )
}

/** A "?" button that explains a term. */
export function HelpTip({ text, label, side = "top" }: { text: string; label?: string; side?: Side }) {
  return (
    <Tooltip content={t(text)} side={side} openOnClick>
      <button type="button" aria-label={label ? t("What is “{term}”?", { term: t(label) }) : t("More information")}
        onClick={(e) => e.stopPropagation()}
        className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full align-middle text-ab-faint transition hover:text-ab-accent focus-visible:text-ab-accent focus-visible:outline-2 focus-visible:outline-ab-accent">
        <CircleHelp className="h-3.5 w-3.5" aria-hidden />
      </button>
    </Tooltip>
  )
}

/** A label followed by its "?" explanation when the glossary has one. */
export function Term({ label, side }: { label: string; side?: Side }) {
  const text = glossary(label)
  return (
    <>
      {t(label)}
      {text && <> <HelpTip text={text} label={label} side={side} /></>}
    </>
  )
}

// ---------------------------------------------------------------- tours

type GuideState = { auto: boolean; seen: string[] }
const storageKey = (userId: number | string) => `alty.manage.guide.${userId}`

function load(userId: number | string): GuideState {
  try {
    const value = JSON.parse(localStorage.getItem(storageKey(userId)) ?? "null")
    if (value && Array.isArray(value.seen)) return { auto: value.auto !== false, seen: value.seen }
  } catch {
    // unreadable or blocked storage: start fresh
  }
  return { auto: true, seen: [] }
}

function save(userId: number | string, state: GuideState) {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(state))
  } catch {
    // blocked storage: tours may show again next visit
  }
}

/** The first element with this data-tour name that is actually on screen. */
function findTarget(name: string): HTMLElement | null {
  for (const el of document.querySelectorAll<HTMLElement>(`[data-tour="${name}"]`)) {
    const r = el.getBoundingClientRect()
    if (r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden") return el
  }
  return null
}

const pathOf = (pathname: string) => pathname.replace(/\/+$/, "") || "/manage"

export function GuideProvider({ children }: { children: ReactNode }) {
  const { user } = useStaffAuth()
  const { pathname } = useLocation()
  const path = pathOf(pathname)
  const userId = user?.id ?? ""
  const [state, setState] = useState<GuideState>(() => (userId ? load(userId) : { auto: true, seen: [] }))
  const [loadedFor, setLoadedFor] = useState(userId)
  const [active, setActive] = useState<{ id: string; steps: TourStep[] } | null>(null)

  // Another account signed in on this browser: use its own tour history.
  if (loadedFor !== userId) {
    setLoadedFor(userId)
    setState(userId ? load(userId) : { auto: true, seen: [] })
  }

  const update = useCallback((next: (s: GuideState) => GuideState) => {
    setState((s) => {
      const value = next(s)
      if (userId) save(userId, value)
      return value
    })
  }, [userId])

  const start = useCallback((id: string) => {
    const steps = (TOURS[id]?.(user) ?? []).filter((step) => !step.target || findTarget(step.target))
    if (steps.length) setActive({ id, steps })
  }, [user])

  const finish = useCallback(() => {
    if (active) update((s) => (s.seen.includes(active.id) ? s : { ...s, seen: [...s.seen, active.id] }))
    setActive(null)
  }, [active, update])

  // First visits: the welcome tour, then each page's own tour. Waits for the
  // page to finish loading so the tour can point at what's really there.
  const next = !userId || !state.auto || active ? null : !state.seen.includes("welcome") ? "welcome" : TOURS[path] && !state.seen.includes(path) ? path : null
  useEffect(() => {
    if (!next) return
    let waited = 0
    const timer = window.setInterval(() => {
      waited += 250
      const busy = document.querySelector("main [aria-busy='true']")
      if (busy && waited < 6000) return
      window.clearInterval(timer)
      if (!document.querySelector("[role='dialog'][aria-modal='true']")) start(next)
    }, 250)
    return () => window.clearInterval(timer)
  }, [next, start])

  // "?" anywhere (outside text fields) opens this page's tour.
  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key !== "?" || active || e.ctrlKey || e.metaKey || e.altKey) return
      const el = e.target as HTMLElement
      if (el.closest("input, textarea, select, [contenteditable='true']")) return
      e.preventDefault()
      start(TOURS[path] ? path : "welcome")
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [active, path, start])

  const api = useMemo<GuideApi>(() => ({
    start,
    hasTour: (id) => Boolean(TOURS[id]),
    auto: state.auto,
    setAuto: (auto) => update((s) => ({ ...s, auto })),
    reset: () => update((s) => ({ ...s, seen: [] })),
  }), [start, state.auto, update])

  return (
    <GuideContext.Provider value={api}>
      {children}
      {active && <Tour key={active.id} steps={active.steps} onClose={finish} />}
    </GuideContext.Provider>
  )
}

function Tour({ steps, onClose }: { steps: TourStep[]; onClose: () => void }) {
  const [index, setIndex] = useState(0)
  const [measured, setMeasured] = useState<{ step: TourStep; rect: DOMRect } | null>(null)
  const card = useRef<HTMLDivElement>(null)
  const primary = useRef<HTMLButtonElement>(null)
  const step = steps[index]
  const rect = measured?.step === step ? measured.rect : null
  const last = index === steps.length - 1
  const titleId = useId()
  const bodyId = useId()

  // Back to where the person was when the tour closes.
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null
    return () => before?.focus?.()
  }, [])

  // Bring the highlighted part into view and follow it while the page moves.
  useEffect(() => {
    const target = step.target ? findTarget(step.target) : null
    if (!target) return
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    target.scrollIntoView({ block: "center", inline: "nearest", behavior: reduce ? "auto" : "smooth" })
    let frame = 0
    const measure = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => setMeasured({ step, rect: target.getBoundingClientRect() }))
    }
    measure()
    window.addEventListener("resize", measure)
    window.addEventListener("scroll", measure, true)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener("resize", measure)
      window.removeEventListener("scroll", measure, true)
    }
  }, [step])

  useEffect(() => primary.current?.focus({ preventScroll: true }), [index])

  // The card sits under (or above) the highlighted part; on phones, at the bottom.
  useLayoutEffect(() => {
    const el = card.current
    if (!el) return
    const phone = window.innerWidth < 640
    const h = el.offsetHeight
    const w = el.offsetWidth
    let top: number
    let left: number
    if (!rect || phone) {
      left = (window.innerWidth - w) / 2
      top = rect && phone && rect.top + rect.height / 2 > window.innerHeight / 2 ? 16 : !rect ? (window.innerHeight - h) / 2 : window.innerHeight - h - 16
    } else {
      left = Math.max(16, Math.min(rect.left, window.innerWidth - w - 16))
      top = rect.bottom + 14 + h < window.innerHeight - 8 ? rect.bottom + 14 : rect.top - 14 - h > 8 ? rect.top - 14 - h : window.innerHeight - h - 16
      // A tall part (like the side menu): put the card beside it.
      if (rect.height > window.innerHeight * 0.6 && rect.right + 16 + w < window.innerWidth) {
        left = rect.right + 16
        top = Math.max(16, Math.min(rect.top + 40, window.innerHeight - h - 16))
      }
    }
    el.style.left = `${Math.max(8, left)}px`
    el.style.top = `${Math.max(8, top)}px`
  }, [rect, index])

  const go = (to: number) => (to < 0 ? undefined : to >= steps.length ? onClose() : setIndex(to))

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Escape") { e.preventDefault(); onClose() }
    else if (e.key === "ArrowRight") { e.preventDefault(); go(index + 1) }
    else if (e.key === "ArrowLeft") { e.preventDefault(); go(index - 1) }
    else if (e.key === "Tab" && card.current) {
      // Keep keyboard focus inside the tour card.
      const items = [...card.current.querySelectorAll<HTMLElement>("button:not([disabled])")]
      const at = items.indexOf(document.activeElement as HTMLElement)
      e.preventDefault()
      items[(at + (e.shiftKey ? -1 : 1) + items.length) % items.length]?.focus()
    }
  }

  const pad = 6
  return createPortal(
    <div className="fixed inset-0 z-[90]" onKeyDown={onKeyDown}>
      {/* Dim the page; the highlighted part shows through a cut-out. Clicks here do nothing, so a stray tap doesn't lose the tour. */}
      <div className="absolute inset-0" aria-hidden />
      {rect ? (
        <div aria-hidden className="pointer-events-none fixed rounded-xl ring-2 ring-ab-accent transition-all duration-200 motion-reduce:transition-none"
          style={{ left: rect.left - pad, top: rect.top - pad, width: rect.width + pad * 2, height: rect.height + pad * 2, boxShadow: "0 0 0 9999px rgba(0,0,0,0.6)" }} />
      ) : (
        <div aria-hidden className="absolute inset-0 bg-black/60" />
      )}
      <div ref={card} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={bodyId} key={index}
        className="ab-pop fixed w-[min(22rem,calc(100vw-32px))] rounded-2xl border border-ab-border-strong bg-ab-card p-5 text-ab-text shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-ab-accent">{t("Step {n} of {total}", { n: index + 1, total: steps.length })}</p>
          <button type="button" onClick={onClose} aria-label={t("Close the tour")} className="-mr-2 -mt-2 rounded-lg p-2 text-ab-muted hover:bg-ab-hover hover:text-ab-text">
            <X className="h-4 w-4" />
          </button>
        </div>
        <h2 id={titleId} className="mt-1 text-lg font-bold leading-snug">{t(step.title)}</h2>
        <p id={bodyId} className="mt-1.5 text-sm leading-relaxed text-ab-muted">{t(step.body)}</p>
        <div className="mt-4 flex gap-1" aria-hidden>
          {steps.map((_, i) => <span key={i} className={`h-1.5 flex-1 rounded-full ${i <= index ? "bg-ab-accent" : "bg-ab-hover"}`} />)}
        </div>
        <div className="mt-4 flex items-center gap-2">
          {!last && <button type="button" onClick={onClose} className="mr-auto text-sm font-semibold text-ab-muted underline-offset-2 hover:text-ab-text hover:underline">{t("Skip tour")}</button>}
          {last && <span className="mr-auto" />}
          {index > 0 && (
            <button type="button" onClick={() => go(index - 1)}
              className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-ab-border-strong px-3 text-sm font-semibold hover:bg-ab-hover">
              <ArrowLeft className="h-4 w-4" /> {t("Back")}
            </button>
          )}
          <button ref={primary} type="button" onClick={() => go(index + 1)}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-xl bg-ab-accent px-4 text-sm font-semibold text-ab-ink hover:bg-ab-accent-hover">
            {last ? <><Check className="h-4 w-4" /> {t("Done")}</> : <>{t("Next")} <ArrowRight className="h-4 w-4" /></>}
          </button>
        </div>
        <p className="mt-3 hidden text-[11px] text-ab-faint sm:block">{t("Tip: use the ← → arrow keys to move between steps and Esc to close.")}</p>
        {/* Read out each new step for screen reader users. */}
        <p className="sr-only" aria-live="polite">{t("Step {n} of {total}", { n: index + 1, total: steps.length })}: {t(step.title)}. {t(step.body)}</p>
      </div>
    </div>,
    document.body,
  )
}

/** Top-bar Help button: replay tours and turn automatic tours on or off. */
export function HelpMenu() {
  const { start, hasTour, auto, setAuto } = useGuide()
  const { pathname } = useLocation()
  const path = pathOf(pathname)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const menuId = useId()

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false)
    const onKey = (e: globalThis.KeyboardEvent) => e.key === "Escape" && setOpen(false)
    document.addEventListener("mousedown", onDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  const run = (id: string) => {
    setOpen(false)
    // Let the menu close first so the tour can point at the page.
    window.setTimeout(() => start(id), 50)
  }
  const item = "flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left text-sm hover:bg-ab-hover disabled:cursor-not-allowed disabled:opacity-50"

  return (
    <div ref={ref} className="relative shrink-0" data-tour="help">
      <Tooltip content={t("Help and guided tours (press ?)")} side="bottom">
        <button type="button" onClick={() => setOpen((v) => !v)} aria-label={t("Help")} aria-expanded={open} aria-controls={menuId}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-ab-border-strong bg-ab-card-2 text-ab-text hover:bg-ab-hover">
          <CircleHelp className="h-4 w-4" />
        </button>
      </Tooltip>
      {open && (
        <div id={menuId} className="ab-pop absolute right-0 top-full z-50 mt-2 w-[min(20rem,calc(100vw-24px))] rounded-2xl border border-ab-border bg-ab-card p-2 shadow-2xl">
          <p className="px-3 pb-1 pt-2 text-[10px] font-bold uppercase tracking-[0.18em] text-ab-faint">{t("Help")}</p>
          <button type="button" className={item} onClick={() => run(path)} disabled={!hasTour(path)}>
            <MapIcon className="mt-0.5 h-4 w-4 shrink-0 text-ab-accent" />
            <span><span className="block font-semibold">{t("Tour this page")}</span><span className="block text-xs text-ab-faint">{t("What this page is for and how to use it.")}</span></span>
          </button>
          <button type="button" className={item} onClick={() => run("welcome")}>
            <Compass className="mt-0.5 h-4 w-4 shrink-0 text-ab-accent" />
            <span><span className="block font-semibold">{t("Getting started")}</span><span className="block text-xs text-ab-faint">{t("The menu, search, notifications and your account.")}</span></span>
          </button>
          <label className="mt-1 flex cursor-pointer items-start gap-3 border-t border-ab-border px-3 pb-2 pt-3 text-sm">
            <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} className="mt-0.5 h-4 w-4 accent-[var(--color-ab-accent)]" />
            <span><span className="block font-semibold">{t("Show tours automatically")}</span><span className="block text-xs text-ab-faint">{t("The first time you open each page.")}</span></span>
          </label>
          <p className="px-3 pb-2 text-xs text-ab-faint">{t("Look for the ? icons next to terms: point at them, focus them with Tab, or tap them to see what they mean.")}</p>
        </div>
      )}
    </div>
  )
}
