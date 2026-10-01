import { createContext, createElement, useCallback, useContext, useEffect, useState, type ReactNode } from "react"

export type ThemeMode = "dark" | "light"

const STORAGE_KEY = "alty-theme"

const readStored = (): ThemeMode | null => {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    return value === "light" || value === "dark" ? value : null
  } catch {
    return null
  }
}

// Dark is ALTY's default look; a saved choice wins, then the OS preference.
const initialTheme = (): ThemeMode => {
  if (typeof window === "undefined") return "dark"
  return readStored() ?? (window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark")
}

const applyTheme = (mode: ThemeMode) => {
  const root = document.documentElement
  root.dataset.theme = mode
  root.classList.toggle("dark", mode === "dark")
}

if (typeof document !== "undefined") applyTheme(initialTheme())

type ThemeValue = { theme: ThemeMode; setTheme: (mode: ThemeMode) => void; toggleTheme: () => void }

const ThemeContext = createContext<ThemeValue | null>(null)

/** One theme for the whole site: every ab-* colour reads CSS variables keyed
 *  off <html data-theme>, so switching restyles every page, the map chrome
 *  and (via `theme`) the basemap. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>(initialTheme)

  // The attribute changes before React re-renders, so components that read
  // CSS variables while rendering (the map's route colours) see the new theme.
  const setTheme = useCallback((mode: ThemeMode) => {
    applyTheme(mode)
    setThemeState(mode)
  }, [])

  useEffect(() => {
    applyTheme(theme)
    try {
      window.localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      /* storage blocked: the choice lasts for this visit */
    }
  }, [theme])

  const toggleTheme = useCallback(() => setTheme(theme === "dark" ? "light" : "dark"), [theme, setTheme])
  return createElement(ThemeContext.Provider, { value: { theme, setTheme, toggleTheme } }, children)
}

export function useTheme(): ThemeValue {
  const value = useContext(ThemeContext)
  if (!value) throw new Error("useTheme must be used inside <ThemeProvider>")
  return value
}
