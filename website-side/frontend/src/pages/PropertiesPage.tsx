import { useCallback, useEffect, useMemo, useState } from "react"
import { ChevronLeft, ChevronRight, MapPinned, RefreshCw, Search, SlidersHorizontal } from "lucide-react"
import { PUBLIC_PROPERTIES_URL, availabilityRank, sortByAvailability } from "@/lib/properties"
import { requestJson } from "@/lib/auth"
import { Link } from "@/components/Link"
import { navigate, useLocation } from "@/lib/router"
import { usePropertyViewer } from "@/hooks/usePropertyViewer"
import { SiteHeader } from "@/components/SiteHeader"
import { SiteFooter } from "@/components/SiteFooter"
import { PropertyCard } from "@/components/PropertyCard"
import { PropertyGridSkeleton } from "@/components/Skeleton"
import { categoryCounts, categoryOf } from "@/lib/categories"
import type { Property } from "@/types"

const SORTS = {
  newest: { label: "Newest", fn: (a: Property, b: Property) => Number(b.listing_id) - Number(a.listing_id) },
  price_asc: { label: "Price: low to high", fn: (a: Property, b: Property) => a.price_total - b.price_total },
  price_desc: { label: "Price: high to low", fn: (a: Property, b: Property) => b.price_total - a.price_total },
} as const

const PAGE_SIZE = 9

/** A sidebar filter choice: a chip on small screens, a list row on desktop. */
function FilterOption({ active, onClick, label, count }: { active: boolean; onClick: () => void; label: string; count?: number }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors lg:border-transparent ${
        active
          ? "border-ab-accent bg-ab-accent/10 font-semibold text-ab-accent"
          : "border-ab-border text-ab-text hover:bg-ab-hover"
      }`}
    >
      <span>{label}</span>
      {count !== undefined && <span className="text-xs text-ab-faint">{count}</span>}
    </button>
  )
}

/** Page numbers with ellipses: 1 … 4 5 6 … 12 */
function pageNumbers(page: number, pageCount: number): (number | "gap")[] {
  const wanted = new Set([1, pageCount, page - 1, page, page + 1].filter((n) => n >= 1 && n <= pageCount))
  const sorted = [...wanted].sort((a, b) => a - b)
  const out: (number | "gap")[] = []
  sorted.forEach((n, i) => {
    if (i > 0 && n - sorted[i - 1] > 1) out.push("gap")
    out.push(n)
  })
  return out
}

function Pagination({ page, pageCount, onChange }: { page: number; pageCount: number; onChange: (page: number) => void }) {
  const base = "inline-flex h-10 min-w-10 items-center justify-center rounded-xl border px-3 text-sm font-semibold transition-colors"
  return (
    <nav aria-label="Pagination" className="mt-10 flex flex-wrap items-center justify-center gap-2">
      <button
        type="button"
        onClick={() => onChange(page - 1)}
        disabled={page === 1}
        aria-label="Previous page"
        className={`${base} border-ab-border hover:bg-ab-hover disabled:opacity-40 disabled:hover:bg-transparent`}
      >
        <ChevronLeft className="h-4 w-4" />
      </button>
      {pageNumbers(page, pageCount).map((n, i) =>
        n === "gap" ? (
          <span key={`gap-${i}`} className="px-1 text-ab-faint">…</span>
        ) : (
          <button
            key={n}
            type="button"
            onClick={() => onChange(n)}
            aria-current={n === page ? "page" : undefined}
            className={`${base} ${n === page ? "border-ab-accent bg-ab-accent text-ab-ink" : "border-ab-border hover:bg-ab-hover"}`}
          >
            {n}
          </button>
        ),
      )}
      <button
        type="button"
        onClick={() => onChange(page + 1)}
        disabled={page === pageCount}
        aria-label="Next page"
        className={`${base} border-ab-border hover:bg-ab-hover disabled:opacity-40 disabled:hover:bg-transparent`}
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </nav>
  )
}

/** All public listings (live data): available first, reserved and sold labelled. */
export function PropertiesPage() {
  const { search } = useLocation()
  const [properties, setProperties] = useState<Property[] | null>(null)
  const [error, setError] = useState("")
  const [query, setQuery] = useState(search.get("q") ?? "")
  const [category, setCategory] = useState(search.get("category") ?? "")
  const [sort, setSort] = useState<keyof typeof SORTS>("newest")
  const [page, setPage] = useState(() => Math.max(1, Number(search.get("page")) || 1))

  const load = useCallback(() => {
    requestJson<Property[]>(PUBLIC_PROPERTIES_URL)
      .then((data) => {
        setProperties(sortByAvailability(data))
        setError("")
      })
      .catch((loadError: Error) => setError(loadError.message))
  }, [])
  useEffect(load, [load])
  const viewer = usePropertyViewer()

  // Any filter or sort change starts back at the first page.
  const [filterKey, setFilterKey] = useState(`${query}|${category}|${sort}`)
  if (filterKey !== `${query}|${category}|${sort}`) {
    setFilterKey(`${query}|${category}|${sort}`)
    setPage(1)
  }

  // Keep the URL shareable as filters and the page change.
  useEffect(() => {
    const params = new URLSearchParams()
    if (query.trim()) params.set("q", query.trim())
    if (category) params.set("category", category)
    if (page > 1) params.set("page", String(page))
    navigate(`/properties${params.size ? `?${params}` : ""}`, { replace: true })
  }, [query, category, page])

  const categories = useMemo(
    () => categoryCounts(properties ?? []),
    [properties],
  )
  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (properties ?? [])
      .filter((p) => !category || categoryOf(p.category)?.key === category)
      .filter((p) => !needle || `${p.title} ${p.village_name ?? ""} ${p.category ?? ""}`.toLowerCase().includes(needle))
      // Available listings first, then reserved, then sold; the chosen sort within each.
      .sort((a, b) => availabilityRank(a) - availabilityRank(b) || SORTS[sort].fn(a, b))
  }, [properties, query, category, sort])
  const availableCount = (properties ?? []).filter((p) => availabilityRank(p) === 0).length

  const pageCount = Math.max(1, Math.ceil(shown.length / PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const pageStart = (currentPage - 1) * PAGE_SIZE
  const pageItems = shown.slice(pageStart, pageStart + PAGE_SIZE)
  const goToPage = (next: number) => {
    setPage(next)
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  return (
    <div className="flex min-h-dvh flex-col bg-ab-bg text-ab-text">
      <SiteHeader />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-10">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.22em] text-ab-accent">Properties</p>
            <h1 className="mt-1 text-3xl font-extrabold tracking-tight md:text-4xl">All properties</h1>
            <p className="mt-1 text-ab-muted">
              {properties
                ? `Showing ${shown.length ? `${pageStart + 1}–${pageStart + pageItems.length}` : 0} of ${shown.length} listing${shown.length === 1 ? "" : "s"} · ${availableCount} available, others labelled reserved or sold`
                : "Loading listings…"}
            </p>
          </div>
          <Link to="/map" className="inline-flex items-center gap-2 self-start rounded-xl border border-ab-border-strong px-4 py-2.5 text-sm font-semibold hover:bg-ab-hover md:self-auto">
            <MapPinned className="h-4 w-4 text-ab-accent" /> Open the property map
          </Link>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[15rem_1fr] lg:items-start">
          <aside className="rounded-2xl border border-ab-border bg-ab-card p-4 lg:sticky lg:top-20">
            <p className="flex items-center gap-2 text-sm font-extrabold uppercase tracking-wide">
              <SlidersHorizontal className="h-4 w-4 text-ab-accent" /> Search filter
            </p>

            <label className="mt-4 flex items-center gap-2 rounded-xl border border-ab-border bg-ab-input px-3 focus-within:border-ab-accent">
              <Search className="h-4 w-4 shrink-0 text-ab-faint" />
              <span className="sr-only">Search</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Property, village or city"
                className="min-h-11 w-full bg-transparent text-sm focus:outline-none"
              />
            </label>

            <fieldset className="mt-5 border-t border-ab-border pt-4">
              <legend className="sr-only">Category</legend>
              <p className="text-sm font-bold">Category</p>
              <div className="mt-2 flex flex-wrap gap-2 lg:flex-col lg:gap-0.5">
                {[{ key: "", label: "All categories", count: properties?.length ?? 0 }, ...categories].map((item) => (
                  <FilterOption
                    key={item.key || "all"}
                    active={category === item.key}
                    onClick={() => setCategory(item.key)}
                    label={item.label}
                    count={item.count}
                  />
                ))}
              </div>
            </fieldset>

            <fieldset className="mt-5 border-t border-ab-border pt-4">
              <legend className="sr-only">Sort by</legend>
              <p className="text-sm font-bold">Sort by</p>
              <div className="mt-2 flex flex-wrap gap-2 lg:flex-col lg:gap-0.5">
                {Object.entries(SORTS).map(([key, item]) => (
                  <FilterOption key={key} active={sort === key} onClick={() => setSort(key as keyof typeof SORTS)} label={item.label} />
                ))}
              </div>
            </fieldset>
          </aside>

          <section aria-label="Listings" className="min-w-0">
            {error && (
              <div role="alert" className="rounded-2xl border border-ab-danger/40 bg-ab-danger/10 p-6 text-center text-ab-danger">
                <p>Unable to load properties: {error}</p>
                <button type="button" onClick={load} className="mt-3 inline-flex items-center gap-1.5 rounded-xl border border-ab-border-strong px-4 py-2 text-sm font-semibold text-ab-text">
                  <RefreshCw className="h-4 w-4" /> Try again
                </button>
              </div>
            )}
            {!properties && !error && <PropertyGridSkeleton count={PAGE_SIZE} />}
            {properties && shown.length === 0 && (
              <p className="rounded-2xl border border-dashed border-ab-border bg-ab-card p-10 text-center text-ab-muted">
                {properties.length === 0 ? "No properties are available right now." : "No properties match your search."}
              </p>
            )}
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {pageItems.map((property, index) => (
                <PropertyCard
                  key={property.listing_id}
                  property={property}
                  onOpen={viewer.open}
                  onMap={viewer.showOnMap}
                  eager={index < 3}
                  className="ab-card-in"
                  style={{ animationDelay: `${Math.min(index, 8) * 50}ms` }}
                />
              ))}
            </div>
            {pageCount > 1 && <Pagination page={currentPage} pageCount={pageCount} onChange={goToPage} />}
          </section>
        </div>
      </main>
      <SiteFooter />
      {viewer.element}
    </div>
  )
}
