import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "leaflet/dist/leaflet.css"

import "./index.css"
import { AppRoutes } from "./AppRoutes"
import { ThemeProvider } from "./hooks/useTheme"
import { AuthProvider } from "./components/AuthProvider"
import { TopProgressBar } from "./components/TopProgressBar"
import { installFetchTracking } from "./lib/loading"

// Count API requests for the loading bar before anything fetches.
installFetchTracking()

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <TopProgressBar />
        <AppRoutes />
      </AuthProvider>
    </ThemeProvider>
  </StrictMode>,
)
