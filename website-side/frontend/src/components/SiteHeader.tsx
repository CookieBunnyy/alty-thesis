import { useEffect, useRef, useState } from "react"
import { ChevronDown, LogOut, Menu, Receipt, Star, UserRound, X } from "lucide-react"
import { useAuth } from "@/lib/auth"
import { Link } from "@/components/Link"
import { navigate, useLocation } from "@/lib/router"
import { useTheme } from "@/hooks/useTheme"
import { ThemeToggle } from "./ThemeToggle"

const NAV = [
  { to: "/", label: "Home" },
  { to: "/properties", label: "Properties" },
  { to: "/map", label: "Property Map" },
] as const

/** Public site header: brand, Home / Properties / Property Map, and either
 *  Sign Up / Sign In or the signed-in client's menu. No internal links. */
export function SiteHeader({ overlay = false }: { overlay?: boolean }) {
  const { pathname, href } = useLocation()
  const { client, signOut } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [menuOpen, setMenuOpen] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const accountRef = useRef<HTMLDivElement | null>(null)
  const next = encodeURIComponent(href)

  // Close the menus when the page changes (state derived during render).
  const [menuPath, setMenuPath] = useState(pathname)
  if (menuPath !== pathname) {
    setMenuPath(pathname)
    setMenuOpen(false)
    setAccountOpen(false)
  }

  useEffect(() => {
    if (!accountOpen) return
    const close = (event: MouseEvent) => {
      if (!accountRef.current?.contains(event.target as Node)) setAccountOpen(false)
    }
    document.addEventListener("mousedown", close)
    return () => document.removeEventListener("mousedown", close)
  }, [accountOpen])

  const isActive = (to: string) => (to === "/" ? pathname === "/" : pathname.startsWith(to))
  const firstName = client?.full_name.split(" ")[0] ?? ""
  const logOut = () => {
    signOut()
    navigate("/")
  }

  return (
    <header
      className={`relative z-[1500] w-full border-b ${
        overlay ? "border-transparent bg-transparent text-white" : "border-ab-border bg-ab-sidebar/95 text-ab-text backdrop-blur"
      }`}
    >
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 md:h-16">
        <Link to="/" className="flex shrink-0 items-center gap-2" aria-label="Abellar Realty home">
          <span className="leading-tight">
            <span className="block text-base font-extrabold tracking-wide">ABELLAR REALTY</span>
            <span className={`block text-[10px] font-semibold uppercase tracking-[0.18em] ${overlay ? "text-white/70" : "text-ab-faint"}`}>
              ALTY Property Finder
            </span>
          </span>
        </Link>

        <nav aria-label="Main" className="ml-6 hidden items-center gap-1 md:flex">
          {NAV.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              aria-current={isActive(item.to) ? "page" : undefined}
              className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${
                isActive(item.to)
                  ? overlay
                    ? "bg-white/15 text-white"
                    : "bg-ab-accent-soft text-ab-accent"
                  : overlay
                    ? "text-white/85 hover:bg-white/10 hover:text-white"
                    : "text-ab-muted hover:bg-ab-hover hover:text-ab-text"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle theme={theme} onToggle={toggleTheme} overlay={overlay} />

          {client ? (
            <div className="relative hidden md:block" ref={accountRef}>
              <button
                type="button"
                onClick={() => setAccountOpen((open) => !open)}
                aria-expanded={accountOpen}
                className={`flex h-9 items-center gap-2 rounded-lg border px-3 text-sm font-semibold transition ${
                  overlay ? "border-white/30 bg-white/10 hover:bg-white/20" : "border-ab-border-strong bg-ab-card-2 hover:bg-ab-hover"
                }`}
              >
                <UserRound className="h-4 w-4" /> {firstName}
                <ChevronDown className="h-3.5 w-3.5" />
              </button>
              {accountOpen && (
                <div className="ab-pop absolute right-0 top-11 w-56 rounded-xl border border-ab-border bg-ab-card p-1.5 text-ab-text shadow-xl" role="menu">
                  <p className="truncate px-3 py-2 text-xs text-ab-muted">{client.email}</p>
                  <Link to="/account" role="menuitem" className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-ab-hover">
                    <UserRound className="h-4 w-4 text-ab-accent" /> My Profile
                  </Link>
                  <Link to="/account#transactions" role="menuitem" className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-ab-hover">
                    <Receipt className="h-4 w-4 text-ab-accent" /> My Transactions
                  </Link>
                  <Link to="/account#reviews" role="menuitem" className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-ab-hover">
                    <Star className="h-4 w-4 text-ab-accent" /> My Reviews
                  </Link>
                  <button type="button" onClick={logOut} role="menuitem" className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-ab-danger hover:bg-ab-hover">
                    <LogOut className="h-4 w-4" /> Log out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="hidden items-center gap-2 md:flex">
              <Link
                to={`/signup?next=${next}`}
                className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${
                  overlay ? "text-white hover:bg-white/10" : "text-ab-text hover:bg-ab-hover"
                }`}
              >
                Sign Up
              </Link>
              <Link to={`/signin?next=${next}`} className="rounded-lg bg-ab-accent px-4 py-2 text-sm font-semibold text-ab-ink transition hover:bg-ab-accent-hover">
                Sign In
              </Link>
            </div>
          )}

          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
            aria-controls="mobile-nav"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            className={`flex h-10 w-10 items-center justify-center rounded-lg border md:hidden ${
              overlay ? "border-white/30 bg-white/10" : "border-ab-border-strong bg-ab-card-2"
            }`}
          >
            {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {menuOpen && (
        <nav id="mobile-nav" aria-label="Main" className="ab-pop border-t border-ab-border bg-ab-card px-4 pb-4 pt-2 text-ab-text shadow-xl md:hidden">
          {NAV.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={`block rounded-lg px-3 py-3 text-base font-semibold ${isActive(item.to) ? "bg-ab-accent-soft text-ab-accent" : "hover:bg-ab-hover"}`}
            >
              {item.label}
            </Link>
          ))}
          <div className="my-2 h-px bg-ab-border" />
          {client ? (
            <>
              <Link to="/account" className="block rounded-lg px-3 py-3 font-semibold hover:bg-ab-hover">My Profile</Link>
              <Link to="/account#transactions" className="block rounded-lg px-3 py-3 font-semibold hover:bg-ab-hover">My Transactions</Link>
              <Link to="/account#reviews" className="block rounded-lg px-3 py-3 font-semibold hover:bg-ab-hover">My Reviews</Link>
              <button type="button" onClick={logOut} className="block w-full rounded-lg px-3 py-3 text-left font-semibold text-ab-danger hover:bg-ab-hover">
                Log out
              </button>
            </>
          ) : (
            <div className="grid grid-cols-2 gap-2 pt-1">
              <Link to={`/signup?next=${next}`} className="rounded-xl border border-ab-border-strong px-4 py-3 text-center font-semibold">Sign Up</Link>
              <Link to={`/signin?next=${next}`} className="rounded-xl bg-ab-accent px-4 py-3 text-center font-semibold text-ab-ink">Sign In</Link>
            </div>
          )}
        </nav>
      )}
    </header>
  )
}
