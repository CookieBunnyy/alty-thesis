import { createContext, useContext } from "react"
import type { Lang } from "./i18n"

export const LanguageContext = createContext<{ lang: Lang; setLang: (lang: Lang) => void }>({
  lang: "en",
  setLang: () => {},
})

export function useLanguage() {
  return useContext(LanguageContext)
}
