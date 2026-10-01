// Main Alty FastAPI server: live property data and client transactions.
export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "")

// Recommendation chat service (website-side/backend).
export const CHAT_API_URL = (import.meta.env.VITE_CHAT_API_URL ?? "https://alty-thesis.onrender.com").replace(
  /\/$/,
  "",
)

export const publicUrl = (path: string) => (/^https?:\/\//.test(path) ? path : `${API_URL}${path}`)
