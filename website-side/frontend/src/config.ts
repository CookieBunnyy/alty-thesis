// Main Alty FastAPI server: live property data, client accounts, maps.
// Set VITE_API_URL in Vercel (Project Settings -> Environment Variables) to
// the Render URL, e.g. https://alty-api.onrender.com, then redeploy.
const configuredApi = import.meta.env.VITE_API_URL as string | undefined

if (import.meta.env.PROD && !configuredApi) {
  console.error(
    "VITE_API_URL is not set for this build, so the site is calling http://localhost:8000, " +
      "which visitors can't reach. Set it in Vercel and redeploy.",
  )
}

export const API_URL = (configuredApi ?? "http://localhost:8000").replace(/\/$/, "")

// Recommendation chat service (website-side/backend).
export const CHAT_API_URL = (import.meta.env.VITE_CHAT_API_URL ?? "https://alty-thesis.onrender.com").replace(
  /\/$/,
  "",
)

export const publicUrl = (path: string) => (/^https?:\/\//.test(path) ? path : `${API_URL}${path}`)
