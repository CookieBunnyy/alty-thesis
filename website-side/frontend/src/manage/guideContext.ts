import { createContext, useContext } from "react"

export type GuideApi = {
  /** Start the tour for a page path, or "welcome". */
  start: (id: string) => void
  hasTour: (id: string) => boolean
  /** Show each page's tour the first time it's opened. */
  auto: boolean
  setAuto: (auto: boolean) => void
  /** Forget which tours were seen. */
  reset: () => void
}

export const GuideContext = createContext<GuideApi>({ start: () => {}, hasTour: () => false, auto: true, setAuto: () => {}, reset: () => {} })

export function useGuide() {
  return useContext(GuideContext)
}
