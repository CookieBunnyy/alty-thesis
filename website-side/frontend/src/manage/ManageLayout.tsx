import { useEffect, useState, type ReactNode } from "react"
import {
  ArrowLeftRight,
  BarChart3,
  Briefcase,
  Building,
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
  UserPlus,
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
import { StaffAvatar } from "./avatars"
import { InstallAppButton } from "@/components/InstallAppButton"
import { HelpMenu, Tooltip } from "./guide"

type NavItem = { key: string; label: string; icon: LucideIcon; path?: string; hint?: string }

// Same groups, labels and permission keys as the desktop sidebar. Only pages
// that already work on the web get a link; the rest are listed as coming in a
// later migration phase (never as a page that does nothing).
const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Main",
    items: [
      { key: "dashboard", label: "Dashboard", icon: Gauge, path: "/manage", hint: "A summary of the whole business at a glance" },
      { key: "properties", label: "Properties", icon: Home, path: "/manage/properties", hint: "Every listing and whether it is available, reserved or sold" },
      { key: "clients", label: "Buyers & Sellers", icon: Users, path: "/manage/clients", hint: "Clients, created automatically from documents" },
      { key: "transactions", label: "Transactions", icon: ArrowLeftRight, path: "/manage/transactions", hint: "Every reservation and sale on record" },
      { key: "agents", label: "Agents", icon: UserRound, path: "/manage/agents", hint: "Agents, their clients, sales and reviews" },
      { key: "partners", label: "Partners / Developers", icon: Handshake, path: "/manage/partners", hint: "Developers and partner companies" },
    ],
  },
  {
    group: "Intelligence",
    items: [
      { key: "analytics", label: "Analytics", icon: BarChart3, path: "/manage/analytics", hint: "How sales and listings are performing" },
      { key: "forecasting", label: "Business Outlook", icon: LineChart, path: "/manage/forecasting", hint: "Past months against their forecast, and the months ahead" },
      // Decision support is a layer inside Analytics, Forecasting, properties and
      // agents; this is its central feed (same "dss" permission as the desktop).
      { key: "dss", label: "Recommendations", icon: ListChecks, path: "/manage/insights", hint: "What needs attention and what to do next" },
      { key: "media", label: "Digital Preview", icon: Images, path: "/manage/media", hint: "Property photos and their quality checks" },
    ],
  },
  {
    group: "Operations",
    items: [
      { key: "documents", label: "Document Repository", icon: FolderOpen, path: "/manage/documents", hint: "Upload documents; ALTY reads and files them" },
      { key: "workforce", label: "Workforce", icon: Network, path: "/manage/workforce", hint: "The team and how work is shared" },
      { key: "branches", label: "Branches", icon: Building, path: "/manage/branches", hint: "Your offices and how each one is doing" },
      { key: "recruitment", label: "Recruitment", icon: UserPlus, path: "/manage/recruitment", hint: "Agent applicants, from application to onboarding" },
      { key: "users", label: "Users & Access", icon: ShieldUser, path: "/manage/users", hint: "Staff accounts and what each role can open" },
      { key: "audit", label: "Audit Logs", icon: ClipboardList, path: "/manage/audit", hint: "A permanent record of every action" },
      { key: "settings", label: "Settings", icon: Settings, path: "/manage/settings", hint: "Appearance, language and tours" },
    ],
  },
]

// Phones and tablets: a bottom bar with the most used pages (in this order,
// only those the role can open) and the account's own profile. The full menu
// is the button at the top left.
const QUICK = ["dashboard", "properties", "transactions", "documents", "clients", "agents", "analytics"]

function BottomNav({ pathname, can, me }: { pathname: string; can: (key: string) => boolean; me: ReactNode }) {
  const items = NAV.flatMap((group) => group.items)
  const quick = QUICK.map((key) => items.find((item) => item.key === key)).filter((item): item is NavItem => Boolean(item?.path && can(item.key))).slice(0, 4)
  const cell = "flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 px-1 text-[10px] font-semibold"
  return (
    <nav aria-label={t("Quick navigation")}
      data-tour="bottom-nav" className="fixed inset-x-0 bottom-0 z-40 flex border-t border-ab-border bg-ab-sidebar/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
      {quick.map(({ key, label, icon: Icon, path }) => {
        const active = path === pathname
        return (
          <Link key={key} to={path!} aria-current={active ? "page" : undefined}
            className={`${cell} ${active ? "text-ab-accent" : "text-ab-muted hover:text-ab-text"}`}>
            <Icon className="h-5 w-5" />
            <span className="max-w-full truncate">{t(SHORT[key] ?? label)}</span>
          </Link>
        )
      })}
      <Link to="/manage/profile" aria-current={pathname === "/manage/profile" ? "page" : undefined}
        className={`${cell} ${pathname === "/manage/profile" ? "text-ab-accent" : "text-ab-muted hover:text-ab-text"}`}>
        <span className={`rounded-full ${pathname === "/manage/profile" ? "ring-2 ring-ab-accent" : ""}`}>{me}</span>
        <span>{t("Profile")}</span>
      </Link>
    </nav>
  )
}

// Short names that fit under an icon on a phone.
const SHORT: Record<string, string> = { documents: "Documents", clients: "Clients", transactions: "Transactions" }

export function ManageLayout({ title, children }: { title: string; children: ReactNode }) {
  const { user, can, signOut } = useStaffAuth()
  const { theme, toggleTheme } = useTheme()
  const { pathname } = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  // Phones: the menu closes when a page opens (e.g. from search inside it).
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMenuOpen(false), [pathname])
  const me = user ? <StaffAvatar userId={user.id} name={user.full_name} version={user.photo_version} /> : null

  const sidebar = (
    <nav aria-label={t("Management")} className="flex h-full flex-col gap-5 overflow-y-auto p-4">
      <Link to="/manage" className="px-2 leading-tight">
        <span className="block text-lg font-extrabold tracking-wide text-ab-text">ALTY</span>
        <span className="block text-[10px] font-semibold uppercase tracking-[0.18em] text-ab-faint">Abellar Realty</span>
      </Link>
      {user?.agent_id && (
        <Link to="/manage/my-work" data-tour="my-work" onClick={() => setMenuOpen(false)} aria-current={pathname === "/manage/my-work" ? "page" : undefined}
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
              {visible.map(({ key, label, icon: Icon, path, hint }) => {
                const active = path === pathname
                const base = "flex min-h-10 items-center gap-2.5 rounded-xl px-3 text-sm font-semibold transition"
                return (
                  <li key={key}>
                    {path ? (
                      <Tooltip content={t(hint ?? label)} side="right" className="block">
                      <Link
                        to={path}
                        onClick={() => setMenuOpen(false)}
                        aria-current={active ? "page" : undefined}
                        className={`${base} ${active ? "bg-ab-accent text-ab-ink" : "text-ab-muted hover:bg-ab-hover hover:text-ab-text"}`}
                      >
                        <Icon className="h-4 w-4 shrink-0" /> {t(label)}
                      </Link>
                      </Tooltip>
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
      <aside data-tour="nav" className="sticky top-0 hidden h-dvh w-64 shrink-0 border-r border-ab-border bg-ab-sidebar lg:block">{sidebar}</aside>

      {menuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label={t("Menu")}>
          <button type="button" aria-label={t("Close menu")} className="absolute inset-0 bg-black/50" onClick={() => setMenuOpen(false)} />
          <aside className="ab-pop relative flex h-full w-80 max-w-[88vw] flex-col border-r border-ab-border bg-ab-sidebar">
            <button type="button" onClick={() => setMenuOpen(false)} aria-label={t("Close menu")} className="absolute right-3 top-3 z-10 rounded-lg p-2 text-ab-muted hover:bg-ab-hover">
              <X className="h-4 w-4" />
            </button>
            <div className="px-4 pt-16 md:hidden"><GlobalSearch className="block w-full" /></div>
            <div className="min-h-0 flex-1">{sidebar}</div>
            <div className="border-t border-ab-border p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
              <div className="flex items-center gap-3">
                {user && <StaffAvatar userId={user.id} name={user.full_name} version={user.photo_version} size="md" />}
                <span className="min-w-0 flex-1 leading-tight">
                  <span className="block truncate text-sm font-bold">{user?.full_name}</span>
                  <span className="block truncate text-xs text-ab-faint">{t(user?.role ?? "")}</span>
                </span>
                <ThemeToggle theme={theme} onToggle={toggleTheme} />
              </div>
              <button type="button" onClick={signOut}
                className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-ab-border-strong text-sm font-semibold text-ab-muted hover:bg-ab-hover hover:text-ab-danger">
                <LogOut className="h-4 w-4" /> {t("Sign out")}
              </button>
            </div>
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 flex h-14 items-center gap-2 border-b border-ab-border bg-ab-sidebar/95 px-3 backdrop-blur sm:h-16 sm:gap-3 sm:px-6">
          <button type="button" data-tour="menu-button" onClick={() => setMenuOpen(true)} aria-label={t("Open menu")} className="shrink-0 rounded-lg border border-ab-border-strong p-2 lg:hidden">
            <Menu className="h-4 w-4" />
          </button>
          <h1 className="min-w-0 flex-1 truncate text-base font-bold sm:text-lg md:flex-none md:shrink-0">{title}</h1>
          <div className="hidden min-w-0 flex-1 justify-center px-2 md:flex" data-tour="search"><GlobalSearch /></div>
          <InstallAppButton area="manage" translate={t} />
          <span data-tour="bell" className="shrink-0"><NotificationBell /></span>
          <HelpMenu />
          <span className="hidden lg:block"><ThemeToggle theme={theme} onToggle={toggleTheme} /></span>
          <Link to="/manage/profile" title={t("My profile")} data-tour="profile"
            className="hidden items-center gap-2.5 rounded-xl border border-ab-border bg-ab-card px-2 py-1.5 transition hover:border-ab-border-strong lg:flex">
            {me}
            <span className="hidden leading-tight sm:block">
              <span className="block text-xs font-bold">{user?.full_name}</span>
              <span className="block text-[11px] text-ab-faint">{t(user?.role ?? "")}</span>
            </span>
          </Link>
          <span className="hidden lg:block">
            <Tooltip content={t("Sign out")} side="bottom">
              <button type="button" onClick={signOut} aria-label={t("Sign out")} className="rounded-lg border border-ab-border-strong p-2 text-ab-muted hover:bg-ab-hover hover:text-ab-danger">
                <LogOut className="h-4 w-4" />
              </button>
            </Tooltip>
          </span>
        </header>
        <main className="min-w-0 flex-1 p-3 pb-24 sm:p-6 sm:pb-24 lg:pb-6">
          <ErrorBoundary key={pathname}>{children}</ErrorBoundary>
        </main>
      </div>
      <BottomNav pathname={pathname} can={can}
        me={user ? <StaffAvatar userId={user.id} name={user.full_name} version={user.photo_version} size="xs" /> : null} />
    </div>
  )
}
