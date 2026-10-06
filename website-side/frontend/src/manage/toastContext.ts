import { createContext, useContext } from "react"

export type ToastTone = "success" | "error" | "info"
export const ToastContext = createContext<(message: string, tone?: ToastTone) => void>(() => {})
/** Show a short message (bottom right). */
export const useToast = () => useContext(ToastContext)
