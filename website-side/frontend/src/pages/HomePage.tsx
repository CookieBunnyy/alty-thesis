import { useEffect, useRef, useState } from "react"
import {
  ArrowRight,
  Briefcase,
  ChevronLeft,
  ChevronRight,
  FileCheck2,
  MapPinned,
  Navigation,
  Route,
  Search,
  ShieldCheck,
  Star,
  UserRound,
  Users,
} from "lucide-react"
import { API_URL } from "@/config"
import { requestJson } from "@/lib/auth"
import { Link } from "@/components/Link"
import { navigate } from "@/lib/router"
import { propertyImage, sizedImage } from "@/lib/media"
import { prefersReducedMotion, useCountUp, useReveal } from "@/hooks/useReveal"
import { usePropertyViewer } from "@/hooks/usePropertyViewer"
import { SiteHeader } from "@/components/SiteHeader"
import { SiteFooter } from "@/components/SiteFooter"
import { PropertyCard } from "@/components/PropertyCard"
import { ReviewCard } from "@/components/ReviewCard"
import { RatingSummary } from "@/components/Stars"
import { PropertyGridSkeleton, Skeleton } from "@/components/Skeleton"
import type { HomeData } from "@/types"

function Reveal({ children, className = "", delay = 0, as: Tag = "div" }: {
  children: React.ReactNode
  className?: string
  delay?: number
  as?: "div" | "section"
}) {
  const ref = useReveal<HTMLDivElement>()
  return (
    <Tag ref={ref} className={`reveal ${className}`} style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </Tag>
  )
}

function SectionHeading({ eyebrow, title, text, action }: { eyebrow: string; title: string; text?: string; action?: React.ReactNode }) {
  return (
    <Reveal className="mb-8 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div className="max-w-2xl">
        <p className="text-xs font-bold uppercase tracking-[0.22em] text-ab-accent">{eyebrow}</p>
        <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-ab-text md:text-4xl">{title}</h2>
        {text && <p className="mt-2 text-ab-muted">{text}</p>}
      </div>
      {action}
    </Reveal>
  )
}

function Stat({ value, label, suffix = "" }: { value: number; label: string; suffix?: string }) {
  const { ref, value: shown } = useCountUp(value)
  return (
    <div>
      <p ref={ref as React.RefObject<HTMLParagraphElement>} className="text-3xl font-extrabold tabular-nums text-white md:text-4xl">
        {shown.toLocaleString()}
        {suffix}
      </p>
      <p className="text-xs font-medium uppercase tracking-wider text-white/70">{label}</p>
    </div>
  )
}

function EmptyState({ text }: { text: string }) {
  return <p className="rounded-2xl border border-dashed border-ab-border bg-ab-card p-8 text-center text-ab-muted">{text}</p>
}

const WHY = [
  { icon: FileCheck2, title: "Listings from real records", text: "Every property on this site comes from Abellar Realty's own documented listings — no placeholders." },
  { icon: Route, title: "Commute-aware search", text: "Set your workplace and compare real road distance and travel time by car, motorcycle, bicycle or on foot." },
  { icon: Users, title: "Agents near the property", text: "See which Abellar agents are closest to a property, with their client reviews, before you reserve." },
  { icon: ShieldCheck, title: "Secure reservations", text: "Reserve or purchase from your own client account, then follow every transaction in one place." },
]

export function HomePage() {
  const [data, setData] = useState<HomeData | null>(null)
  const [error, setError] = useState("")
  const [query, setQuery] = useState("")
  const [slide, setSlide] = useState(0)
  const viewer = usePropertyViewer()
  const reviewTrack = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    requestJson<HomeData>(`${API_URL}/api/v1/public/home`)
      .then(setData)
      .catch((loadError: Error) => setError(loadError.message))
  }, [])

  const heroImages = (data?.featured_properties ?? [])
    .map((property) => property.photos?.[0])
    .filter((url): url is string => Boolean(url))
    .slice(0, 4)

  // Slow crossfade between real featured-property photos.
  useEffect(() => {
    if (heroImages.length < 2 || prefersReducedMotion()) return
    const timer = window.setInterval(() => setSlide((index) => (index + 1) % heroImages.length), 6500)
    return () => window.clearInterval(timer)
  }, [heroImages.length])

  const scrollReviews = (direction: 1 | -1) => {
    const track = reviewTrack.current
    if (!track) return
    track.scrollBy({ left: direction * Math.min(track.clientWidth * 0.9, 420), behavior: prefersReducedMotion() ? "auto" : "smooth" })
  }

  const reviewStats = data?.stats.client_reviews

  return (
    <div className="min-h-dvh bg-ab-bg text-ab-text">
      {/* ---------------- HERO ---------------- */}
      <section className="relative isolate flex min-h-[92dvh] flex-col overflow-hidden bg-[#0b120e]">
        <div className="absolute inset-0 -z-10" aria-hidden="true">
          {heroImages.length > 0 ? (
            heroImages.map((url, index) => (
              <img
                key={url}
                src={sizedImage(url, 1600)}
                alt=""
                loading={index === 0 ? "eager" : "lazy"}
                fetchPriority={index === 0 ? "high" : "low"}
                decoding="async"
                className={`hero-slide absolute inset-0 h-full w-full object-cover ${index === slide ? "is-active" : ""}`}
              />
            ))
          ) : (
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,#3d5a0a_0%,#0b120e_60%)]" />
          )}
          <div className="absolute inset-0 bg-gradient-to-b from-black/70 via-black/45 to-[#0b120e]" />
        </div>

        <div className="absolute inset-x-0 top-0">
          <SiteHeader overlay />
        </div>

        <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col justify-center px-4 pb-16 pt-28 md:pt-32">
          <p className="hero-in text-xs font-bold uppercase tracking-[0.3em] text-[#C7F000]" style={{ animationDelay: "60ms" }}>
            Abellar Realty
          </p>
          <h1 className="hero-in mt-4 max-w-4xl text-4xl font-extrabold leading-[1.05] tracking-tight text-white sm:text-5xl md:text-7xl" style={{ animationDelay: "160ms" }}>
            Real Estate Property Discovery <span className="text-[#C7F000]">and Services</span>
          </h1>
          <p className="hero-in mt-5 max-w-2xl text-base text-white/80 md:text-lg" style={{ animationDelay: "280ms" }}>
            Browse Abellar Realty's available properties, see how far each one is from your workplace by road, and
            reserve with an Abellar agent near the property.
          </p>

          <form
            role="search"
            onSubmit={(event) => {
              event.preventDefault()
              navigate(`/properties${query.trim() ? `?q=${encodeURIComponent(query.trim())}` : ""}`)
            }}
            className="hero-in mt-8 flex w-full max-w-2xl items-center gap-2 rounded-2xl bg-white/95 p-2 shadow-2xl ring-1 ring-black/5"
            style={{ animationDelay: "400ms" }}
          >
            <Search className="ml-2 h-5 w-5 shrink-0 text-[#566158]" />
            <label htmlFor="home-search" className="sr-only">Search properties</label>
            <input
              id="home-search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by property, village or city"
              className="min-w-0 flex-1 bg-transparent py-2 text-base text-[#111719] placeholder:text-[#879087] focus:outline-none"
            />
            <button type="submit" className="rounded-xl bg-[#C7F000] px-4 py-2.5 text-sm font-bold text-[#0B0F10] transition hover:bg-[#D6FF33]">
              Search
            </button>
          </form>

          <div className="hero-in mt-5 flex flex-wrap gap-3" style={{ animationDelay: "500ms" }}>
            <Link to="/properties" className="inline-flex items-center gap-2 rounded-xl bg-[#C7F000] px-5 py-3 font-bold text-[#0B0F10] transition hover:-translate-y-0.5 hover:bg-[#D6FF33]">
              Explore Properties <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/map" className="inline-flex items-center gap-2 rounded-xl border border-white/40 bg-white/10 px-5 py-3 font-bold text-white backdrop-blur transition hover:-translate-y-0.5 hover:bg-white/20">
              <MapPinned className="h-4 w-4" /> View Property Map
            </Link>
          </div>

          {!data && !error && (
            <div className="mt-12 grid max-w-2xl grid-cols-2 gap-6 border-t border-white/15 pt-6 sm:grid-cols-3" aria-hidden="true">
              {[0, 1].map((index) => (
                <div key={index} className="space-y-2">
                  <div className="h-9 w-16 animate-pulse rounded-lg bg-white/15" />
                  <div className="h-3 w-28 animate-pulse rounded bg-white/10" />
                </div>
              ))}
            </div>
          )}
          {data && (
            <div className="hero-in mt-12 grid max-w-2xl grid-cols-2 gap-6 border-t border-white/15 pt-6 sm:grid-cols-3" style={{ animationDelay: "620ms" }}>
              <Stat value={data.stats.available_properties} label="Available properties" />
              <Stat value={data.stats.active_agents} label="Active agents" />
              {reviewStats && reviewStats.count > 0 && reviewStats.average != null && (
                <div>
                  <p className="flex items-center gap-1 text-3xl font-extrabold text-white md:text-4xl">
                    {reviewStats.average.toFixed(1)} <Star className="h-6 w-6 fill-[#F5B83D] text-[#F5B83D]" />
                  </p>
                  <p className="text-xs font-medium uppercase tracking-wider text-white/70">
                    From {reviewStats.count} client review{reviewStats.count === 1 ? "" : "s"}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {heroImages.length > 1 && (
          <div className="absolute bottom-6 right-6 hidden gap-1.5 md:flex" aria-hidden="true">
            {heroImages.map((url, index) => (
              <span key={url} className={`h-1.5 rounded-full transition-all duration-500 ${index === slide ? "w-8 bg-[#C7F000]" : "w-3 bg-white/40"}`} />
            ))}
          </div>
        )}
      </section>

      {error && (
        <p role="alert" className="mx-auto mt-8 max-w-7xl px-4 text-center text-ab-danger">
          Unable to load the latest listings: {error}
        </p>
      )}
      {!data && !error && (
        <section className="mx-auto max-w-7xl px-4 py-20">
          <div className="mb-8 space-y-3" aria-hidden="true">
            <Skeleton className="h-3 w-36" />
            <Skeleton className="h-9 w-64" />
            <Skeleton className="h-4 w-80 max-w-full" />
          </div>
          <PropertyGridSkeleton label="Loading featured properties…" />
        </section>
      )}

      {data && (
        <main>
          {/* ---------------- FEATURED ---------------- */}
          <section className="mx-auto max-w-7xl px-4 py-20">
            <SectionHeading
              eyebrow="Featured properties"
              title="Available now"
              text="The newest available listings from Abellar Realty."
              action={
                <Link to="/properties" className="inline-flex items-center gap-1.5 font-semibold text-ab-accent hover:underline">
                  View all properties <ArrowRight className="h-4 w-4" />
                </Link>
              }
            />
            {data.featured_properties.length === 0 ? (
              <EmptyState text="No featured properties available." />
            ) : (
              <div className="-mx-4 flex snap-x snap-mandatory gap-5 overflow-x-auto px-4 pb-2 sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:px-0 lg:grid-cols-3">
                {data.featured_properties.map((property, index) => (
                  <Reveal key={property.listing_id} delay={(index % 3) * 90} className="w-[82%] shrink-0 snap-start sm:w-auto">
                    <PropertyCard property={property} onOpen={viewer.open} onMap={viewer.showOnMap} className="h-full" />
                  </Reveal>
                ))}
              </div>
            )}
          </section>

          {/* ---------------- MAP CTA ---------------- */}
          <section className="bg-ab-sidebar py-20">
            <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 md:grid-cols-2">
              <Reveal>
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-ab-accent">Interactive property map</p>
                <h2 className="mt-2 text-3xl font-extrabold tracking-tight md:text-4xl">Find a property near your workplace</h2>
                <ol className="mt-6 space-y-3">
                  {[
                    [Briefcase, "Set your workplace"],
                    [MapPinned, "Explore nearby properties"],
                    [Route, "Compare road distance"],
                    [Navigation, "View travel time by mode"],
                    [UserRound, "Find agents near the property"],
                  ].map(([Icon, text], index) => {
                    const StepIcon = Icon as typeof Briefcase
                    return (
                      <li key={text as string} className="flex items-center gap-3">
                        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-ab-accent-soft text-ab-accent">
                          <StepIcon className="h-4 w-4" />
                        </span>
                        <span className="font-medium text-ab-text">
                          <span className="mr-2 text-ab-faint">{index + 1}.</span>
                          {text as string}
                        </span>
                      </li>
                    )
                  })}
                </ol>
                <Link to="/map" className="mt-8 inline-flex items-center gap-2 rounded-xl bg-ab-accent px-5 py-3 font-bold text-ab-ink transition hover:-translate-y-0.5 hover:bg-ab-accent-hover">
                  Explore Property Map <ArrowRight className="h-4 w-4" />
                </Link>
              </Reveal>
              <Reveal delay={120}>
                <div className="relative overflow-hidden rounded-3xl border border-ab-border bg-ab-card p-6 shadow-xl" aria-hidden="true">
                  {/* Decorative: a road-following route, not data. */}
                  <svg viewBox="0 0 400 260" className="h-auto w-full">
                    <defs>
                      <pattern id="grid" width="26" height="26" patternUnits="userSpaceOnUse">
                        <path d="M26 0H0V26" fill="none" stroke="currentColor" strokeOpacity="0.08" />
                      </pattern>
                    </defs>
                    <rect width="400" height="260" fill="url(#grid)" className="text-ab-text" />
                    <path d="M40 60 H150 V120 H230 V190 H350" fill="none" stroke="var(--color-ab-route-casing)" strokeWidth="12" strokeLinecap="round" strokeLinejoin="round" />
                    <path className="route-draw" d="M40 60 H150 V120 H230 V190 H350" fill="none" stroke="var(--color-ab-route)" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
                    <circle cx="40" cy="60" r="11" fill="var(--color-ab-text)" stroke="var(--color-ab-accent)" strokeWidth="3" />
                    <rect x="330" y="172" width="44" height="34" rx="10" fill="var(--color-ab-accent)" />
                  </svg>
                  <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
                    <p className="rounded-xl bg-ab-card-2 p-3"><span className="block text-xs text-ab-faint">Start</span>Your workplace</p>
                    <p className="rounded-xl bg-ab-card-2 p-3"><span className="block text-xs text-ab-faint">Destination</span>The property you choose</p>
                  </div>
                </div>
              </Reveal>
            </div>
          </section>

          {/* ---------------- WHY ---------------- */}
          <section className="mx-auto max-w-7xl px-4 py-20">
            <SectionHeading eyebrow="Why Abellar Realty" title="Property search built around your day" />
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {WHY.map((item, index) => (
                <Reveal key={item.title} delay={index * 80}>
                  <div className="h-full rounded-2xl border border-ab-border bg-ab-card p-6 transition hover:-translate-y-1 hover:border-ab-accent/50 hover:shadow-lg">
                    <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-ab-accent-soft text-ab-accent">
                      <item.icon className="h-5 w-5" />
                    </span>
                    <h3 className="mt-4 font-bold text-ab-text">{item.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-ab-muted">{item.text}</p>
                  </div>
                </Reveal>
              ))}
            </div>
          </section>

          {/* ---------------- CATEGORIES ---------------- */}
          {data.categories.length > 0 && (
            <section className="mx-auto max-w-7xl px-4 pb-20">
              <SectionHeading eyebrow="Browse by type" title="Property categories" />
              <Reveal className="flex flex-wrap gap-3">
                {data.categories.map((item) => (
                  <Link
                    key={item.category}
                    to={`/properties?category=${encodeURIComponent(item.category)}`}
                    className="group flex items-center gap-3 rounded-2xl border border-ab-border bg-ab-card px-5 py-4 transition hover:-translate-y-0.5 hover:border-ab-accent"
                  >
                    <span className="text-lg font-bold capitalize text-ab-text">{item.category}</span>
                    <span className="rounded-full bg-ab-accent-soft px-2.5 py-0.5 text-sm font-bold text-ab-accent">{item.count}</span>
                    <ArrowRight className="h-4 w-4 text-ab-faint transition group-hover:translate-x-1 group-hover:text-ab-accent" />
                  </Link>
                ))}
              </Reveal>
            </section>
          )}

          {/* ---------------- AGENTS ---------------- */}
          <section className="bg-ab-sidebar py-20">
            <div className="mx-auto max-w-7xl px-4">
              <SectionHeading eyebrow="Meet our agents" title="Abellar Realty agents" text="Active agents, with ratings from their clients' reviews." />
              {data.agents.length === 0 ? (
                <EmptyState text="No agents found." />
              ) : (
                <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                  {data.agents.map((agent, index) => (
                    <Reveal key={agent.agent_id} delay={(index % 3) * 80}>
                      <div className="flex h-full items-start gap-4 rounded-2xl border border-ab-border bg-ab-card p-5 transition hover:-translate-y-1 hover:shadow-lg">
                        <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-ab-accent text-xl font-black text-ab-ink">
                          {agent.full_name.split(" ").map((part) => part[0]).slice(0, 2).join("")}
                        </span>
                        <div className="min-w-0 flex-1">
                          <h3 className="font-bold text-ab-text">{agent.full_name}</h3>
                          <p className="text-sm text-ab-muted">{agent.agent_location ?? "Abellar Realty"}</p>
                          <div className="mt-2">
                            <RatingSummary rating={agent.client_rating} count={agent.review_count} compact />
                          </div>
                          <Link to={`/agents/${encodeURIComponent(agent.agent_id)}`} className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-ab-accent hover:underline">
                            View Agent <ArrowRight className="h-3.5 w-3.5" />
                          </Link>
                        </div>
                      </div>
                    </Reveal>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* ---------------- REVIEWS ---------------- */}
          <section className="mx-auto max-w-7xl px-4 py-20">
            <SectionHeading
              eyebrow="Client reviews"
              title="What our clients say"
              text={
                reviewStats && reviewStats.count > 0 && reviewStats.average != null
                  ? `Average ${reviewStats.average.toFixed(1)} out of 5 from ${reviewStats.count} verified client review${reviewStats.count === 1 ? "" : "s"}.`
                  : undefined
              }
              action={
                data.reviews.length > 1 ? (
                  <div className="flex gap-2">
                    <button type="button" onClick={() => scrollReviews(-1)} aria-label="Previous reviews" className="flex h-10 w-10 items-center justify-center rounded-full border border-ab-border bg-ab-card hover:bg-ab-hover">
                      <ChevronLeft className="h-5 w-5" />
                    </button>
                    <button type="button" onClick={() => scrollReviews(1)} aria-label="Next reviews" className="flex h-10 w-10 items-center justify-center rounded-full border border-ab-border bg-ab-card hover:bg-ab-hover">
                      <ChevronRight className="h-5 w-5" />
                    </button>
                  </div>
                ) : undefined
              }
            />
            {data.reviews.length === 0 ? (
              <EmptyState text="No client reviews yet." />
            ) : (
              <div ref={reviewTrack} className="-mx-4 flex snap-x snap-mandatory gap-5 overflow-x-auto scroll-smooth px-4 pb-4" aria-label="Client reviews">
                {data.reviews.map((review, index) => (
                  <Reveal key={review.id} delay={Math.min(index, 3) * 90} className="w-[85%] shrink-0 snap-start sm:w-[380px]">
                    <ReviewCard review={review} />
                  </Reveal>
                ))}
              </div>
            )}
          </section>

          {/* ---------------- MORE PROPERTIES SHOWCASE ---------------- */}
          {data.featured_properties.some((property) => propertyImage(property)) && (
            <section className="mx-auto max-w-7xl px-4 pb-20">
              <Reveal className="grid auto-rows-[180px] grid-cols-2 gap-3 md:auto-rows-[220px] md:grid-cols-4">
                {data.featured_properties
                  .filter((property) => propertyImage(property))
                  .slice(0, 5)
                  .map((property, index) => (
                    <button
                      key={property.listing_id}
                      type="button"
                      onClick={() => viewer.open(property)}
                      className={`group relative overflow-hidden rounded-2xl text-left ${index === 0 ? "col-span-2 row-span-2" : ""}`}
                    >
                      <img src={propertyImage(property, index === 0 ? 1000 : 500)!} alt="" loading="lazy" decoding="async" className="h-full w-full object-cover transition duration-700 group-hover:scale-105" />
                      <span className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/10 to-transparent" />
                      <span className="absolute inset-x-0 bottom-0 p-4 text-white">
                        <span className="block text-sm font-bold">{property.title}</span>
                        <span className="block text-xs text-white/80">{property.village_name}</span>
                      </span>
                    </button>
                  ))}
              </Reveal>
            </section>
          )}

          {/* ---------------- CTA ---------------- */}
          <section className="px-4 pb-20">
            <Reveal className="mx-auto max-w-7xl overflow-hidden rounded-3xl bg-[#0E1512] p-8 text-white shadow-2xl md:p-14">
              <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
                <div>
                  <h2 className="text-3xl font-extrabold tracking-tight md:text-4xl">Ready to find your next home?</h2>
                  <p className="mt-2 max-w-xl text-white/75">
                    Create a free client account to reserve properties, follow your transactions and rate your agent.
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <Link to="/signup" className="rounded-xl bg-[#C7F000] px-5 py-3 font-bold text-[#0B0F10] transition hover:bg-[#D6FF33]">Create account</Link>
                  <Link to="/properties" className="rounded-xl border border-white/30 px-5 py-3 font-bold transition hover:bg-white/10">Browse properties</Link>
                </div>
              </div>
            </Reveal>
          </section>
        </main>
      )}

      <SiteFooter />
      {viewer.element}
    </div>
  )
}
