// Interface language for the management system (English / Filipino).
//
// t("English text") returns the text in the chosen language and falls back
// to English. Placeholders: t("{n} of {total} documents", { n, total }).
// The choice is remembered in this browser. Changing it re-renders every page
// (LanguageProvider remounts the app), so plain t() calls are enough — no hook
// is needed. Text that comes from the server (record data, analysis
// sentences, error details) is shown as it is stored.
import { FILIPINO, FILIPINO_PATTERNS } from "./i18n.fil"

export const LANGUAGES = { en: "English", fil: "Filipino" } as const
export type Lang = keyof typeof LANGUAGES

const KEY = "alty.manage.language"
const TABLES: Record<Lang, Record<string, string>> = { en: {}, fil: FILIPINO }
const PATTERNS: Record<Lang, [RegExp, string][]> = { en: [], fil: FILIPINO_PATTERNS }

function saved(): Lang {
  try {
    const value = localStorage.getItem(KEY)
    return value === "fil" ? "fil" : "en"
  } catch {
    return "en"
  }
}

let current: Lang = saved()

export function getLanguage(): Lang {
  return current
}

export function applyLanguage(lang: Lang): void {
  current = lang
  try {
    localStorage.setItem(KEY, lang)
  } catch {
    // private window / blocked storage: the choice lasts for this visit
  }
  document.documentElement.lang = lang === "fil" ? "fil" : "en"
}

/** Locale for dates and numbers. */
export function locale(): string {
  return current === "fil" ? "fil-PH" : "en-PH"
}

export function t(text: string, vars?: Record<string, string | number | null | undefined>): string {
  let found = TABLES[current][text]
  if (found === undefined) {
    const rule = PATTERNS[current].find(([pattern]) => pattern.test(text))
    if (rule) found = text.replace(rule[0], rule[1])
  }
  if (import.meta.env.DEV && current !== "en" && found === undefined && text.trim()) missing.add(text)
  const out = found ?? text
  return vars ? out.replace(/\{(\w+)\}/g, (match, key: string) => (key in vars ? String(vars[key] ?? "") : match)) : out
}

/** Untranslated strings seen in development (window.__altyMissing()). */
const missing = new Set<string>()
if (import.meta.env.DEV && typeof window !== "undefined") {
  ;(window as unknown as { __altyMissing: () => string[] }).__altyMissing = () => [...missing]
}
