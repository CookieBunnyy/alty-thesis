import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "leaflet/dist/leaflet.css"

import "./index.css"
import { AppRoutes } from "./AppRoutes"
import { ThemeProvider } from "./hooks/useTheme"
import { AuthProvider } from "./components/AuthProvider"
import { TopProgressBar } from "./components/TopProgressBar"
import { installFetchTracking } from "./lib/loading"
import { setupPwa } from "./lib/pwa"
import { moveToOwnHost } from "./lib/hosts"

// Count API requests for the loading bar before anything fetches.
installFetchTracking()
// Installable app: service worker + the browser's install prompt.
setupPwa()

// The public site and the Management System have separate domains in
// production; a page opened on the wrong one moves before anything renders.
if (!moveToOwnHost()) createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <TopProgressBar />
        <AppRoutes />
      </AuthProvider>
    </ThemeProvider>
  </StrictMode>,
)
