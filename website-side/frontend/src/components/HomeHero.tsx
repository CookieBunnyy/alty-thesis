import { ArrowRight, Home, MapPinned, MessageCircle, Star } from "lucide-react"
import { API_URL } from "@/config"
import { AgentPhoto } from "@/components/AgentPhoto"
import { Link } from "@/components/Link"
import { useCountUp } from "@/hooks/useReveal"
import { peso, propertyImage } from "@/lib/media"
import type { HomeData } from "@/types"

/* Home page hero: the headline in the middle of a soft panel, with the site's
   features as cards around it (map, chat assistant, a featured property,
   agents near the property, partners & developers). Wide screens float the
   cards in the corners; smaller screens list them in a grid under the text. */

const shell = "relative block rounded-2xl border border-ab-border bg-ab-card/95 p-4 text-left shadow-[0_18px_40px_-18px_rgba(0,0,0,0.45)] backdrop-blur transition hover:-translate-y-0.5 hover:border-ab-accent/60"
const tile = "flex h-14 w-14 items-center justify-center rounded-2xl border border-ab-border bg-ab-card shadow-[0_14px_30px_-12px_rgba(0,0,0,0.5)]"

/** A small folder tab on top of a card, like the reference's file cards. */
const Tab = () => <span aria-hidden className="absolute -top-2.5 left-5 h-3 w-16 rounded-t-lg border-x border-t border-ab-border bg-ab-card" />

function Stat({ value, label }: { value: number; label: string }) {
  const { ref, value: shown } = useCountUp(value)
  return (
    <div className="text-center">
      <p ref={ref as React.RefObject<HTMLParagraphElement>} className="text-3xl font-extrabold tabular-nums text-ab-text md:text-4xl">{shown.toLocaleString()}</p>
      <p className="mt-0.5 text-[11px] font-semibold uppercase tracking-wider text-ab-faint">{label}</p>
    </div>
  )
}

function MapCard() {
  return (
    <Link to="/map" className={shell} aria-label="Property map: find properties near your workplace">
      <Tab />
      <p className="text-sm font-bold">Property map</p>
      <svg viewBox="0 0 220 120" className="mt-2 h-auto w-full rounded-xl" aria-hidden>
        <rect width="220" height="120" rx="12" className="fill-ab-card-2" />
        <path d="M0 38 H220 M0 84 H220 M58 0 V120 M142 0 V120 M182 0 V120" className="stroke-ab-border" strokeWidth="6" />
        <rect x="150" y="48" width="26" height="28" rx="5" fill="var(--color-ab-accent)" opacity="0.18" />
        <path d="M30 38 H58 V84 H142 V62" fill="none" stroke="var(--color-ab-route)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="30" cy="38" r="8" className="fill-ab-text" stroke="var(--color-ab-accent)" strokeWidth="3" />
        <rect x="130" y="48" width="24" height="18" rx="5" fill="var(--color-ab-accent)" />
        <path d="M136 59 L142 54 L148 59 V63 H136 Z" fill="var(--color-ab-ink)" />
      </svg>
      <p className="mt-2 text-xs text-ab-muted">Road distance and travel time from your workplace.</p>
    </Link>
  )
}

function ChatCard() {
  return (
    <Link to="/map" className={`${shell} flex items-start gap-3`} aria-label="Chat assistance: ask about properties">
      <span className={`${tile} h-12 w-12 shrink-0 text-ab-accent`}><MessageCircle className="h-6 w-6" /></span>
      <span className="min-w-0 flex-1 space-y-1.5 text-xs">
        <span className="ml-auto block w-fit max-w-full rounded-2xl rounded-br-md bg-ab-accent px-3 py-1.5 font-semibold text-ab-ink">2-bedroom near my office?</span>
        <span className="block w-fit max-w-full rounded-2xl rounded-bl-md bg-ab-card-2 px-3 py-1.5 text-ab-text">Here are homes close to it, with travel times.</span>
      </span>
    </Link>
  )
}

function PropertyFeature({ data }: { data: HomeData | null }) {
  const property = data?.featured_properties[0]
  const photo = property ? propertyImage(property, 480) : null
  return (
    <Link to="/properties" className={shell} aria-label={property ? `Featured property: ${property.title}` : "Browse properties"}>
      <Tab />
      <p className="text-sm font-bold">Featured property</p>
      <div className="mt-2 aspect-[16/9] overflow-hidden rounded-xl bg-ab-card-2">
        {photo
          ? <img src={photo} alt="" loading="eager" className="h-full w-full object-cover" />
          : <div className={`flex h-full w-full items-center justify-center text-ab-faint ${data ? "" : "animate-pulse"}`}>{data && <Home className="h-8 w-8" />}</div>}
      </div>
      <p className="mt-2 truncate text-sm font-semibold">{property?.title ?? "Available properties"}</p>
      <div className="mt-1 flex items-center justify-between gap-2 text-xs">
        <span className="truncate text-ab-muted">{property?.village_name || "Abellar Realty"}</span>
        {property && <span className="shrink-0 rounded-full bg-ab-accent-soft px-2 py-0.5 font-bold text-ab-accent">{peso(property.price_total)}</span>}
      </div>
    </Link>
  )
}

function AgentsCard({ data }: { data: HomeData | null }) {
  const agents = (data?.agents ?? []).slice(0, 2)
  return (
    <Link to="/map" className={shell} aria-label="Agents near the property">
      <Tab />
      <p className="text-sm font-bold">Agents near the property</p>
      <ul className="mt-2 space-y-2">
        {agents.length === 0 && <li className="rounded-xl bg-ab-card-2 p-3 text-xs text-ab-muted">See the Abellar agents closest to any property.</li>}
        {agents.map((agent) => (
          <li key={agent.agent_id} className="flex items-center gap-2.5 rounded-xl bg-ab-card-2 p-2">
            <AgentPhoto name={agent.full_name} photoUrl={agent.photo_url} className="h-8 w-8 rounded-full text-[11px]" />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs font-semibold">{agent.full_name}</span>
              <span className="block truncate text-[11px] text-ab-faint">{agent.agent_location || "Abellar Realty"}</span>
            </span>
            {agent.client_rating != null && (
              <span className="flex shrink-0 items-center gap-0.5 text-[11px] font-bold"><Star className="h-3 w-3 fill-[#F5B83D] text-[#F5B83D]" />{agent.client_rating.toFixed(1)}</span>
            )}
          </li>
        ))}
      </ul>
    </Link>
  )
}

function PartnersCard({ data }: { data: HomeData | null }) {
  const partners = data?.partners ?? []
  const shown = partners.slice(0, 3)
  return (
    <a href="#partners" className={shell} aria-label="Partners and developers">
      <Tab />
      <p className="text-sm font-bold">{partners.length > 0 ? `${partners.length} Partners & developers` : "Partners & developers"}</p>
      <div className="mt-3 flex items-center">
        {shown.length === 0 && <span className="text-xs text-ab-muted">The developers behind our homes.</span>}
        {shown.map((partner, index) => (
          <span key={partner.id} className={`flex h-14 w-[76px] items-center justify-center overflow-hidden rounded-2xl border border-ab-border bg-white p-2 shadow-md ${index ? "-ml-2" : ""}`}
            style={{ transform: `rotate(${(index - 1) * 5}deg)` }}>
            {partner.logo_url
              ? <img src={`${API_URL}${partner.logo_url}`} alt={partner.name} className="max-h-full max-w-full object-contain" />
              : <span className="text-sm font-black text-[#2E2E2E]">{partner.name.split(/\s+/).map((w) => w[0]).slice(0, 2).join("")}</span>}
          </span>
        ))}
      </div>
    </a>
  )
}

export function HomeHero({ data }: { data: HomeData | null }) {
  const enter = (ms: number) => ({ className: "hero-in", style: { animationDelay: `${ms}ms` } })
  return (
    <section className="px-3 pb-8 pt-2 sm:px-4" aria-label="Abellar Realty">
      <div className="hero-panel relative overflow-hidden rounded-[2rem] border border-ab-border xl:min-h-[780px]">
        {/* ---- the middle: brand tile, headline, actions, numbers ---- */}
        <div className="relative z-10 mx-auto flex max-w-[680px] flex-col items-center px-5 pt-12 xl:max-w-[800px] text-center sm:pt-16 xl:pt-[86px]">
          <img src="/icons/site-192.png" alt="" width={72} height={72} {...enter(0)}
            className="hero-in h-16 w-16 rounded-2xl shadow-[0_18px_36px_-14px_rgba(0,0,0,0.6)] sm:h-[72px] sm:w-[72px]" />
          <h1 className="hero-in mt-7 text-4xl font-extrabold leading-[1.05] tracking-tight text-ab-text sm:text-5xl xl:text-6xl" style={{ animationDelay: "100ms" }}>
            Real Estate Property
            <span className="mt-1 block text-ab-faint">Discovery and Services</span>
          </h1>
          <p {...enter(200)} className="hero-in mt-5 max-w-xl text-base text-ab-muted md:text-lg">
            Browse Abellar Realty's available properties, see how far each one is from your workplace by road, and
            contact an Abellar agent near the property.
          </p>
          <div {...enter(300)} className="hero-in mt-7 flex flex-wrap justify-center gap-3">
            <Link to="/properties" className="inline-flex items-center gap-2 rounded-xl bg-ab-accent px-5 py-3 font-bold text-ab-ink transition hover:-translate-y-0.5 hover:bg-ab-accent-hover">
              Explore Properties <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/map" className="inline-flex items-center gap-2 rounded-xl border border-ab-border-strong bg-ab-card px-5 py-3 font-bold text-ab-text transition hover:-translate-y-0.5 hover:bg-ab-hover">
              <MapPinned className="h-4 w-4" /> View Property Map
            </Link>
          </div>
          <div {...enter(400)} className="hero-in mt-8 flex min-h-[64px] items-start justify-center gap-10 sm:gap-14">
            {data ? (
              <>
                <Stat value={data.stats.available_properties} label="Available properties" />
                <Stat value={data.stats.active_agents} label="Active agents" />
              </>
            ) : (
              [0, 1].map((index) => (
                <div key={index} className="flex flex-col items-center gap-2" aria-hidden>
                  <div className="h-9 w-14 animate-pulse rounded-lg bg-ab-card-2" />
                  <div className="h-3 w-28 animate-pulse rounded bg-ab-card-2" />
                </div>
              ))
            )}
          </div>
        </div>

        {/* ---- the features: a grid on smaller screens, corner cards on wide ones ---- */}
        <div className="grid grid-cols-1 gap-5 px-4 pb-6 pt-10 min-[480px]:grid-cols-2 sm:px-6 md:grid-cols-3 xl:contents">
          <div {...enter(500)} className="hero-in xl:absolute xl:left-[3%] xl:top-[7%] xl:w-[250px]">
            <div className="hero-float xl:-rotate-3"><MapCard /></div>
          </div>
          <div {...enter(620)} className="hero-in xl:absolute xl:left-[2.5%] xl:top-[45%] xl:z-20 xl:w-[235px]">
            <div className="hero-float hero-float-slow xl:rotate-2"><ChatCard /></div>
          </div>
          <div {...enter(560)} className="hero-in xl:absolute xl:right-[2.5%] xl:top-[6%] xl:w-[250px]">
            <div className="hero-float hero-float-slow xl:rotate-2"><PropertyFeature data={data} /></div>
          </div>
          <div {...enter(680)} aria-hidden className="hero-in hidden xl:absolute xl:right-[21%] xl:top-[13%] xl:z-20 xl:block">
            <div className={`${tile} hero-float -rotate-6 text-ab-accent`}><Home className="h-7 w-7" /></div>
          </div>
          <div {...enter(740)} className="hero-in xl:absolute xl:-bottom-3 xl:left-[3%] xl:w-[280px]">
            <div className="hero-float"><AgentsCard data={data} /></div>
          </div>
          <div {...enter(800)} className="hero-in xl:absolute xl:-bottom-3 xl:right-[3%] xl:w-[270px]">
            <div className="hero-float hero-float-slow"><PartnersCard data={data} /></div>
          </div>
        </div>
      </div>
    </section>
  )
}
