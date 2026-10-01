import { useCallback, useEffect, useMemo, useState } from "react"
import { MapPinned, RefreshCw, Search } from "lucide-react"
import { API_URL } from "@/config"
import { requestJson } from "@/lib/auth"
import { Link } from "@/components/Link"
import { navigate, useLocation } from "@/lib/router"
import { usePropertyViewer } from "@/hooks/usePropertyViewer"
import { SiteHeader } from "@/components/SiteHeader"
import { SiteFooter } from "@/components/SiteFooter"
import { PropertyCard } from "@/components/PropertyCard"
import { PropertyGridSkeleton } from "@/components/Skeleton"
import type { Property } from "@/types"

const SORTS = {
  newest: { label: "Newest", fn: (a: Property, b: Property) => Number(b.listing_id) - Number(a.listing_id) },
  price_asc: { label: "Price: low to high", fn: (a: Property, b: Property) => a.price_total - b.price_total },
  price_desc: { label: "Price: high to low", fn: (a: Property, b: Property) => b.price_total - a.price_total },
} as const

/** All available properties (live data), searchable and filterable. */
export function PropertiesPage() {
  const { search } = useLocation()
  const [properties, setProperties] = useState<Property[] | null>(null)
  const [error, setError] = useState("")
  const [query, setQuery] = useState(search.get("q") ?? "")
  const [category, setCategory] = useState(search.get("category") ?? "")
  const [sort, setSort] = useState<keyof typeof SORTS>("newest")

  const load = useCallback(() => {
    requestJson<Property[]>(`${API_URL}/api/v1/public/properties`)
      .then((data) => {
        setProperties(data)
        setError("")
      })
      .catch((loadError: Error) => setError(loadError.message))
  }, [])
  useEffect(load, [load])
  const viewer = usePropertyViewer(load)

  // Keep the URL shareable as filters change.
  useEffect(() => {
    const params = new URLSearchParams()
    if (query.trim()) params.set("q", query.trim())
    if (category) params.set("category", category)
    navigate(`/properties${params.size ? `?${params}` : ""}`, { replace: true })
  }, [query, category])

  const categories = useMemo(
    () => [...new Set((properties ?? []).map((p) => p.category).filter((c): c is string => Boolean(c)))].sort(),
    [properties],
  )
  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (properties ?? [])
      .filter((p) => !category || (p.category ?? "").toLowerCase() === category.toLowerCase())
      .filter((p) => !needle || `${p.title} ${p.village_name ?? ""} ${p.category ?? ""}`.toLowerCase().includes(needle))
      .sort(SORTS[sort].fn)
  }, [properties, query, category, sort])

  return (
    <div className="flex min-h-dvh flex-col bg-ab-bg text-ab-text">
      <SiteHeader />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-10">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.22em] text-ab-accent">Properties</p>
            <h1 className="mt-1 text-3xl font-extrabold tracking-tight md:text-4xl">Available properties</h1>
            <p className="mt-1 text-ab-muted">
              {properties ? `${shown.length} of ${properties.length} available listing${properties.length === 1 ? "" : "s"}` : "Loading listings…"}
            </p>
          </div>
          <Link to="/map" className="inline-flex items-center gap-2 self-start rounded-xl border border-ab-border-strong px-4 py-2.5 text-sm font-semibold hover:bg-ab-hover md:self-auto">
            <MapPinned className="h-4 w-4 text-ab-accent" /> Open the property map
          </Link>
        </div>

        <div className="mt-6 grid gap-3 rounded-2xl border border-ab-border bg-ab-card p-3 md:grid-cols-[1fr_auto_auto]">
          <label className="flex items-center gap-2 rounded-xl border border-ab-border bg-ab-input px-3 focus-within:border-ab-accent">
            <Search className="h-4 w-4 text-ab-faint" />
            <span className="sr-only">Search</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by property, village or city"
              className="min-h-11 w-full bg-transparent text-sm focus:outline-none"
            />
          </label>
          <label className="sr-only" htmlFor="category">Category</label>
          <select id="category" value={category} onChange={(event) => setCategory(event.target.value)} className="min-h-11 rounded-xl border border-ab-border bg-ab-input px-3 text-sm capitalize">
            <option value="">All categories</option>
            {categories.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
          <label className="sr-only" htmlFor="sort">Sort</label>
          <select id="sort" value={sort} onChange={(event) => setSort(event.target.value as keyof typeof SORTS)} className="min-h-11 rounded-xl border border-ab-border bg-ab-input px-3 text-sm">
            {Object.entries(SORTS).map(([key, item]) => (
              <option key={key} value={key}>{item.label}</option>
            ))}
          </select>
        </div>

        {error && (
          <div role="alert" className="mt-8 rounded-2xl border border-ab-danger/40 bg-ab-danger/10 p-6 text-center text-ab-danger">
            <p>Unable to load properties: {error}</p>
            <button type="button" onClick={load} className="mt-3 inline-flex items-center gap-1.5 rounded-xl border border-ab-border-strong px-4 py-2 text-sm font-semibold text-ab-text">
              <RefreshCw className="h-4 w-4" /> Try again
            </button>
          </div>
        )}
        {!properties && !error && (
          <div className="mt-8">
            <PropertyGridSkeleton />
          </div>
        )}
        {properties && shown.length === 0 && (
          <p className="mt-8 rounded-2xl border border-dashed border-ab-border bg-ab-card p-10 text-center text-ab-muted">
            {properties.length === 0 ? "No properties are available right now." : "No properties match your search."}
          </p>
        )}
        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((property, index) => (
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
      </main>
      <SiteFooter />
      {viewer.element}
    </div>
  )
}
