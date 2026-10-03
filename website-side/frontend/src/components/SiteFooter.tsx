import { Link } from "@/components/Link"

export function SiteFooter() {
  return (
    <footer className="border-t border-ab-border bg-ab-sidebar">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-12 md:grid-cols-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-base font-extrabold tracking-wide text-ab-text">ABELLAR REALTY</span>
          </div>
          <p className="mt-3 max-w-xs text-sm text-ab-muted">Real Estate Property Discovery and Services.</p>
        </div>
        <nav aria-label="Footer" className="grid grid-cols-2 gap-2 text-sm">
          <Link to="/" className="text-ab-muted hover:text-ab-text">Home</Link>
          <Link to="/properties" className="text-ab-muted hover:text-ab-text">Properties</Link>
          <Link to="/map" className="text-ab-muted hover:text-ab-text">Property Map</Link>
          <Link to="/account" className="text-ab-muted hover:text-ab-text">My Account</Link>
        </nav>
        <p className="text-sm text-ab-muted md:text-right">
          Questions about a property? Choose it on the map or in Properties to contact an agent near it.
        </p>
      </div>
      <p className="border-t border-ab-border py-4 text-center text-xs text-ab-faint">
        © {new Date().getFullYear()} Abellar Realty · Map data © OpenStreetMap contributors
      </p>
    </footer>
  )
}
