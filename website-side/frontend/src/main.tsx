import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "leaflet/dist/leaflet.css"

import "./index.css"
import { AppRoutes } from "./AppRoutes"
import { ThemeProvider } from "./hooks/useTheme"
import { AuthProvider } from "./components/AuthProvider"
import { installFetchTracking } from "./lib/loading"
import { setupPwa } from "./lib/pwa"
import { dismissSplashWhenReady } from "./lib/splash"
import { moveToOwnHost } from "./lib/hosts"

// Count API requests before anything fetches (the welcome screen waits for the first data).
installFetchTracking()
// Installable app: service worker + the browser's install prompt.
setupPwa()

// The public site and the Management System have separate domains in
// production; a page opened on the wrong one moves before anything renders.
if (!moveToOwnHost()) {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <ThemeProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </ThemeProvider>
    </StrictMode>,
  )
  // The welcome screen (index.html) stays until the first data has arrived.
  dismissSplashWhenReady()
}
