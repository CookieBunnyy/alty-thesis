import { lazy, Suspense, useEffect } from "react"
import { LoaderCircle } from "lucide-react"
import App from "./App.tsx"
import { Link } from "@/components/Link"
import { matchPath, useLocation } from "@/lib/router"
import { HomePage } from "./pages/HomePage"
import { PropertiesPage } from "./pages/PropertiesPage"
import { AuthPage } from "./pages/AuthPage"
import { AccountPage } from "./pages/AccountPage"
import { AgentPage } from "./pages/AgentPage"
import { SiteHeader } from "./components/SiteHeader"

// Management System: its own bundle, downloaded only by staff who open /manage.
const ManageApp = lazy(() => import("./manage/ManageApp"))

const TITLES: Record<string, string> = {
  "/": "Abellar Realty — Real Estate Property Discovery and Services",
  "/properties": "Properties · Abellar Realty",
  "/map": "Property Map · Abellar Realty",
  "/signin": "Sign In · Abellar Realty",
  "/signup": "Create Account · Abellar Realty",
  "/account": "My Account · Abellar Realty",
}

function NotFound() {
  return (
    <div className="min-h-dvh bg-ab-bg text-ab-text">
      <SiteHeader />
      <main className="mx-auto max-w-xl px-4 py-24 text-center">
        <h1 className="text-3xl font-extrabold">Page not found</h1>
        <p className="mt-2 text-ab-muted">That page doesn't exist.</p>
        <Link to="/" className="mt-6 inline-block rounded-xl bg-ab-accent px-5 py-2.5 font-semibold text-ab-ink">Go home</Link>
      </main>
    </div>
  )
}

export function AppRoutes() {
  const { pathname } = useLocation()
  if (pathname === "/manage" || pathname.startsWith("/manage/")) {
    return (
      <Suspense
        fallback={
          <div className="flex min-h-dvh items-center justify-center bg-ab-bg text-ab-muted" role="status">
            <LoaderCircle className="mr-2 h-5 w-5 animate-spin text-ab-accent" /> Loading…
          </div>
        }
      >
        <ManageApp />
      </Suspense>
    )
  }
  // Keyed wrapper: each page fades in when you switch pages.
  return (
    <div key={pathname} className="ab-page-in">
      <CurrentPage />
    </div>
  )
}

function CurrentPage() {
  const { pathname } = useLocation()
  useEffect(() => {
    document.title = TITLES[pathname] ?? (pathname.startsWith("/agents/") ? "Agent · Abellar Realty" : "Abellar Realty")
  }, [pathname])

  if (pathname === "/") return <HomePage />
  if (pathname === "/properties") return <PropertiesPage />
  if (pathname === "/map") return <App />
  if (pathname === "/signin") return <AuthPage key="signin" mode="signin" />
  if (pathname === "/signup") return <AuthPage key="signup" mode="signup" />
  if (pathname === "/account") return <AccountPage />
  const agent = matchPath("/agents/:id", pathname)
  if (agent) return <AgentPage agentId={agent.id} />
  return <NotFound />
}
