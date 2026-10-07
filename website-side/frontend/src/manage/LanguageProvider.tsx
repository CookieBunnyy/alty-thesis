import { useCallback, useEffect, useState, type ReactNode } from "react"
import { applyLanguage, getLanguage, type Lang } from "./i18n"
import { LanguageContext } from "./languageContext"

/** Holds the chosen language; changing it re-renders the whole management app. */
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(getLanguage)
  useEffect(() => {
    applyLanguage(lang)
    return () => { document.documentElement.lang = "en" }
  }, [lang])
  const setLang = useCallback((next: Lang) => {
    applyLanguage(next)
    setLangState(next)
  }, [])
  return (
    <LanguageContext.Provider value={{ lang, setLang }}>
      <div key={lang} className="contents">{children}</div>
    </LanguageContext.Provider>
  )
}
