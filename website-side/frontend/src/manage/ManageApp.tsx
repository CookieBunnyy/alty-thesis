// Web Management System (/manage/*). Loaded only when a /manage page is opened,
// so the public site never downloads it. Uses the same FastAPI backend, roles
// and permissions as the desktop app.
import { useEffect } from "react"
import { LoaderCircle } from "lucide-react"
import { navigate, useLocation } from "@/lib/router"
import { AgentsPage } from "./AgentsPage"
import { AuditPage } from "./AuditPage"
import { MyWorkPage } from "./MyWorkPage"
import { PartnersPage } from "./PartnersPage"
import { SettingsPage } from "./SettingsPage"
import { UsersPage } from "./UsersPage"
import { WorkforcePage } from "./WorkforcePage"
import { AnalyticsPage } from "./AnalyticsPage"
import { ForecastingPage } from "./ForecastingPage"
import { InsightsPage } from "./InsightsPage"
import { ClientsPage } from "./ClientsPage"
import { DashboardPage } from "./DashboardPage"
import { DocumentsPage } from "./DocumentsPage"
import { MediaPage } from "./MediaPage"
import { PropertiesPage } from "./PropertiesPage"
import { ToastProvider } from "./Toasts"
import { TransactionsPage } from "./TransactionsPage"
import { ManageLayout } from "./ManageLayout"
import { ManageSignIn } from "./ManageSignIn"
import { StaffAuthProvider } from "./staffAuth"
import { useStaffAuth } from "./staffContext"

// path -> [permission key, title, page]
const PAGES: Record<string, [string, string, () => React.ReactNode]> = {
  "/manage": ["dashboard", "Dashboard", () => <DashboardPage />],
  "/manage/properties": ["properties", "Properties", () => <PropertiesPage />],
  "/manage/agents": ["agents", "Agents", () => <AgentsPage />],
  "/manage/clients": ["clients", "Buyers & Sellers", () => <ClientsPage />],
  "/manage/transactions": ["transactions", "Transactions", () => <TransactionsPage />],
  "/manage/partners": ["partners", "Partners / Developers", () => <PartnersPage />],
  "/manage/documents": ["documents", "Document Repository", () => <DocumentsPage />],
  "/manage/media": ["media", "Digital Preview", () => <MediaPage />],
  "/manage/analytics": ["analytics", "Analytics", () => <AnalyticsPage />],
  "/manage/forecasting": ["forecasting", "Forecasting", () => <ForecastingPage />],
  "/manage/insights": ["dss", "Insights", () => <InsightsPage />],
  "/manage/workforce": ["workforce", "Workforce", () => <WorkforcePage />],
  "/manage/users": ["users", "Users & Access", () => <UsersPage />],
  "/manage/audit": ["audit", "Audit Logs", () => <AuditPage />],
  "/manage/settings": ["settings", "Settings", () => <SettingsPage />],
}

export default function ManageApp() {
  return (
    <StaffAuthProvider>
      <ToastProvider>
        <ManageRoutes />
      </ToastProvider>
    </StaffAuthProvider>
  )
}

function ManageRoutes() {
  const { pathname, href } = useLocation()
  const { user, isReady, can } = useStaffAuth()
  const path = pathname.replace(/\/+$/, "") || "/manage"

  useEffect(() => {
    document.title = `${path === "/manage/signin" ? "Management sign in" : PAGES[path]?.[1] ?? "Management"} · ALTY`
  }, [path])

  // Every page except sign-in needs a staff session.
  const needsSignIn = path !== "/manage/signin" && isReady && !user
  useEffect(() => {
    if (needsSignIn) navigate(`/manage/signin?next=${encodeURIComponent(href)}`, { replace: true })
  }, [needsSignIn, href])

  if (path === "/manage/signin") return <ManageSignIn />
  if (!isReady || !user) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-ab-bg text-ab-muted" role="status">
        <LoaderCircle className="mr-2 h-5 w-5 animate-spin text-ab-accent" /> Checking your session…
      </div>
    )
  }

  // "My Work": any account linked to an agent record.
  if (path === "/manage/my-work" && user.agent_id) {
    return <ManageLayout title="My Work"><MyWorkPage /></ManageLayout>
  }
  const page = PAGES[path]
  if (page && can(page[0])) {
    return <ManageLayout title={page[1]}>{page[2]()}</ManageLayout>
  }
  return (
    <ManageLayout title="Not available">
      <div className="mx-auto max-w-lg rounded-2xl border border-ab-border bg-ab-card p-8 text-center">
        <p className="text-lg font-bold">This page isn't available</p>
        <p className="mt-1 text-sm text-ab-muted">
          It either doesn't exist yet on the web, or your role ({user.role}) can't open it.
        </p>
      </div>
    </ManageLayout>
  )
}
