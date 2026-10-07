import { useState, type ReactNode } from "react"
import {
  ArrowLeftRight,
  BarChart3,
  Briefcase,
  ClipboardList,
  FolderOpen,
  Gauge,
  Handshake,
  Home,
  Images,
  ListChecks,
  LineChart,
  LogOut,
  Menu,
  Network,
  Settings,
  ShieldUser,
  UserRound,
  Users,
  X,
  type LucideIcon,
} from "lucide-react"
import { Link } from "@/components/Link"
import { ThemeToggle } from "@/components/ThemeToggle"
import { useTheme } from "@/hooks/useTheme"
import { useLocation } from "@/lib/router"
import { ErrorBoundary } from "./ErrorBoundary"
import { GlobalSearch, NotificationBell } from "./HeaderTools"
import { useStaffAuth } from "./staffContext"
import { t } from "./i18n"

type NavItem = { key: string; label: string; icon: LucideIcon; path?: string }

// Same groups, labels and permission keys as the desktop sidebar. Only pages
// that already work on the web get a link; the rest are listed as coming in a
// later migration phase (never as a page that does nothing).
const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Main",
    items: [
      { key: "dashboard", label: "Dashboard", icon: Gauge, path: "/manage" },
      { key: "properties", label: "Properties", icon: Home, path: "/manage/properties" },
      { key: "clients", label: "Buyers & Sellers", icon: Users, path: "/manage/clients" },
      { key: "transactions", label: "Transactions", icon: ArrowLeftRight, path: "/manage/transactions" },
      { key: "agents", label: "Agents", icon: UserRound, path: "/manage/agents" },
      { key: "partners", label: "Partners / Developers", icon: Handshake, path: "/manage/partners" },
    ],
  },
  {
    group: "Intelligence",
    items: [
      { key: "analytics", label: "Analytics", icon: BarChart3, path: "/manage/analytics" },
      { key: "forecasting", label: "Forecasting", icon: LineChart, path: "/manage/forecasting" },
      // Decision support is a layer inside Analytics, Forecasting, properties and
      // agents; this is its central feed (same "dss" permission as the desktop).
      { key: "dss", label: "Recommendations", icon: ListChecks, path: "/manage/insights" },
      { key: "media", label: "Digital Preview", icon: Images, path: "/manage/media" },
    ],
  },
  {
    group: "Operations",
    items: [
      { key: "documents", label: "Document Repository", icon: FolderOpen, path: "/manage/documents" },
      { key: "workforce", label: "Workforce", icon: Network, path: "/manage/workforce" },
      { key: "users", label: "Users & Access", icon: ShieldUser, path: "/manage/users" },
      { key: "audit", label: "Audit Logs", icon: ClipboardList, path: "/manage/audit" },
      { key: "settings", label: "Settings", icon: Settings, path: "/manage/settings" },
    ],
  },
]

export function ManageLayout({ title, children }: { title: string; children: ReactNode }) {
  const { user, can, signOut } = useStaffAuth()
  const { theme, toggleTheme } = useTheme()
  const { pathname } = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const initials = (user?.full_name ?? "?").split(" ").map((part) => part[0]).slice(0, 2).join("").toUpperCase()

  const sidebar = (
    <nav aria-label={t("Management")} className="flex h-full flex-col gap-5 overflow-y-auto p-4">
      <Link to="/manage" className="px-2 leading-tight">
        <span className="block text-lg font-extrabold tracking-wide text-ab-text">ALTY</span>
        <span className="block text-[10px] font-semibold uppercase tracking-[0.18em] text-ab-faint">Abellar Realty</span>
      </Link>
      {user?.agent_id && (
        <Link to="/manage/my-work" onClick={() => setMenuOpen(false)} aria-current={pathname === "/manage/my-work" ? "page" : undefined}
          className={`flex min-h-10 items-center gap-2.5 rounded-xl px-3 text-sm font-semibold transition ${pathname === "/manage/my-work" ? "bg-ab-accent text-ab-ink" : "border border-ab-accent/40 text-ab-text hover:bg-ab-hover"}`}>
          <Briefcase className="h-4 w-4 shrink-0" /> {t("My Work")}
        </Link>
      )}
      {NAV.map(({ group, items }) => {
        const visible = items.filter((item) => can(item.key))
        if (!visible.length) return null
        return (
          <div key={group}>
            <p className="px-2 pb-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-ab-faint">{t(group)}</p>
            <ul className="space-y-0.5">
              {visible.map(({ key, label, icon: Icon, path }) => {
                const active = path === pathname
                const base = "flex min-h-10 items-center gap-2.5 rounded-xl px-3 text-sm font-semibold transition"
                return (
                  <li key={key}>
                    {path ? (
                      <Link
                        to={path}
                        onClick={() => setMenuOpen(false)}
                        aria-current={active ? "page" : undefined}
                        className={`${base} ${active ? "bg-ab-accent text-ab-ink" : "text-ab-muted hover:bg-ab-hover hover:text-ab-text"}`}
                      >
                        <Icon className="h-4 w-4 shrink-0" /> {t(label)}
                      </Link>
                    ) : (
                      <span className={`${base} cursor-default text-ab-faint`} title={t("Coming in a later migration phase — use the desktop app for now")}>
                        <Icon className="h-4 w-4 shrink-0" /> <span className="flex-1">{t(label)}</span>
                        <span className="rounded-full border border-ab-border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide">{t("Soon")}</span>
                      </span>
                    )}
                  </li>
                )
              })}
            </ul>
          </div>
        )
      })}
    </nav>
  )

  return (
    <div className="flex min-h-dvh bg-ab-bg text-ab-text">
      <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 border-r border-ab-border bg-ab-sidebar lg:block">{sidebar}</aside>

      {menuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label={t("Menu")}>
          <button type="button" aria-label={t("Close menu")} className="absolute inset-0 bg-black/50" onClick={() => setMenuOpen(false)} />
          <aside className="ab-pop relative h-full w-72 max-w-[85vw] border-r border-ab-border bg-ab-sidebar">
            <button type="button" onClick={() => setMenuOpen(false)} aria-label={t("Close menu")} className="absolute right-3 top-3 rounded-lg p-2 text-ab-muted hover:bg-ab-hover">
              <X className="h-4 w-4" />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 flex h-16 items-center gap-3 border-b border-ab-border bg-ab-sidebar/95 px-4 backdrop-blur sm:px-6">
          <button type="button" onClick={() => setMenuOpen(true)} aria-label={t("Open menu")} className="rounded-lg border border-ab-border-strong p-2 lg:hidden">
            <Menu className="h-4 w-4" />
          </button>
          <h1 className="min-w-0 shrink-0 truncate text-lg font-bold">{title}</h1>
          <div className="flex min-w-0 flex-1 justify-center px-2"><GlobalSearch /></div>
          <NotificationBell />
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
          <div className="flex items-center gap-2.5 rounded-xl border border-ab-border bg-ab-card px-2 py-1.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-ab-accent-soft text-xs font-extrabold text-ab-accent">{initials}</span>
            <span className="hidden leading-tight sm:block">
              <span className="block text-xs font-bold">{user?.full_name}</span>
              <span className="block text-[11px] text-ab-faint">{t(user?.role ?? "")}</span>
            </span>
          </div>
          <button type="button" onClick={signOut} title={t("Sign out")} aria-label={t("Sign out")} className="rounded-lg border border-ab-border-strong p-2 text-ab-muted hover:bg-ab-hover hover:text-ab-danger">
            <LogOut className="h-4 w-4" />
          </button>
        </header>
        <main className="min-w-0 flex-1 p-4 sm:p-6">
          <ErrorBoundary key={pathname}>{children}</ErrorBoundary>
        </main>
      </div>
    </div>
  )
}
