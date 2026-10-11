import { useEffect, useState } from "react"
import { ArrowRight, Home, MapPinned, Star } from "lucide-react"
import { AgentPhoto } from "@/components/AgentPhoto"
import { API_URL } from "@/config"
import { requestJson } from "@/lib/auth"
import { Link } from "@/components/Link"
import { useCountUp } from "@/hooks/useReveal"
import { peso, propertyImage } from "@/lib/media"
import type { HomeData } from "@/types"
import { ChatBotIcon } from "@/components/icons/ChatBotIcon"

/* Home page hero: the headline in the middle of a soft panel, with the site's
   features as cards around it (map, chat assistant, a featured property,
   agents near the property). Wide screens float full cards on both sides;
   smaller screens tuck small versions around the text. */

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
      <span className={`${tile} h-12 w-12 shrink-0 text-ab-accent`}><ChatBotIcon className="h-7 w-7" /></span>
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

/* ---- phones and tablets: small versions of the cards, around the text ---- */

const mini = "block rounded-xl border border-ab-border bg-ab-card/95 p-1.5 shadow-[0_12px_26px_-12px_rgba(0,0,0,0.55)] backdrop-blur"

function MapMini() {
  return (
    <Link to="/map" className={`${mini} w-[100px] sm:w-[140px]`} aria-label="Property map">
      <svg viewBox="0 0 220 120" className="h-auto w-full rounded-lg" aria-hidden>
        <rect width="220" height="120" rx="14" className="fill-ab-card-2" />
        <path d="M0 38 H220 M0 84 H220 M58 0 V120 M142 0 V120" className="stroke-ab-border" strokeWidth="8" />
        <path d="M30 38 H58 V84 H142 V62" fill="none" stroke="var(--color-ab-route)" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="30" cy="38" r="11" className="fill-ab-text" stroke="var(--color-ab-accent)" strokeWidth="4" />
        <rect x="128" y="46" width="28" height="22" rx="6" fill="var(--color-ab-accent)" />
      </svg>
      <span className="mt-1 block px-0.5 text-[10px] font-bold">Property map</span>
    </Link>
  )
}

function PropertyMini({ data }: { data: HomeData | null }) {
  const property = data?.featured_properties[0]
  const photo = property ? propertyImage(property, 320) : null
  return (
    <Link to="/properties" className={`${mini} w-[100px] sm:w-[140px]`} aria-label={property ? `Featured property: ${property.title}` : "Browse properties"}>
      <span className="block aspect-[4/3] overflow-hidden rounded-lg bg-ab-card-2">
        {photo
          ? <img src={photo} alt="" className="h-full w-full object-cover" />
          : <span className="flex h-full w-full items-center justify-center text-ab-faint"><Home className="h-5 w-5" /></span>}
      </span>
      <span className="mt-1 block truncate px-0.5 text-[10px] font-bold">{property ? peso(property.price_total) : "Properties"}</span>
    </Link>
  )
}

function ChatMini() {
  return (
    <Link to="/map" className={`${mini} w-[80px] space-y-1 p-2 sm:w-[96px]`} aria-label="Chat assistance">
      <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-ab-accent text-ab-ink"><ChatBotIcon className="h-5 w-5" /></span>
      <span className="block rounded-lg rounded-bl-sm bg-ab-card-2 px-1.5 py-1 text-[9px] leading-tight text-ab-text">Ask about any property</span>
    </Link>
  )
}

function AgentsMini({ data }: { data: HomeData | null }) {
  const agents = (data?.agents ?? []).slice(0, 3)
  return (
    <Link to="/map" className={`${mini} w-[80px] p-2 sm:w-[96px]`} aria-label="Agents near the property">
      <span className="flex">
        {agents.length === 0 && <span className="h-7 w-7 rounded-full bg-ab-card-2" />}
        {agents.map((agent, index) => (
          <AgentPhoto key={agent.agent_id} name={agent.full_name} photoUrl={agent.photo_url}
            className={`h-7 w-7 rounded-full text-[9px] ring-2 ring-ab-card ${index ? "-ml-2" : ""}`} />
        ))}
      </span>
      <span className="mt-1 block text-[9px] font-bold leading-tight">Agents near the property</span>
    </Link>
  )
}

export function HomeHero({ data }: { data: HomeData | null }) {
  const enter = (ms: number) => ({ className: "hero-in", style: { animationDelay: `${ms}ms` } })
  return (
    <section className="px-3 pb-8 pt-2 sm:px-4" aria-label="Abellar Realty">
      <div className="hero-panel relative overflow-hidden rounded-[2rem] border border-ab-border pb-6 xl:min-h-[680px] xl:pb-0">
        {/* ---- phones and tablets: small cards beside the brand tile ---- */}
        <div {...enter(500)} className="hero-in absolute left-3 top-4 z-20 sm:left-6 sm:top-6 xl:hidden">
          <div className="hero-float -rotate-6"><MapMini /></div>
        </div>
        <div {...enter(560)} className="hero-in absolute right-3 top-4 z-20 sm:right-6 sm:top-6 xl:hidden">
          <div className="hero-float hero-float-slow rotate-6"><PropertyMini data={data} /></div>
        </div>

        {/* ---- the middle: brand tile, headline, actions, numbers ---- */}
        <div className="relative z-10 mx-auto flex max-w-[680px] flex-col items-center px-5 pt-12 text-center sm:pt-16 xl:max-w-[800px] xl:pt-[86px]">
          <img src="/icons/site-192.png" alt="" width={72} height={72} {...enter(0)}
            className="hero-in h-16 w-16 rounded-2xl shadow-[0_18px_36px_-14px_rgba(0,0,0,0.6)] sm:h-[72px] sm:w-[72px]" />
          <h1 className="hero-in mt-12 text-4xl font-extrabold leading-[1.05] tracking-tight text-ab-text sm:mt-10 sm:text-5xl xl:mt-7 xl:text-6xl" style={{ animationDelay: "100ms" }}>
            Real Estate Property
            <span className="mt-1 block text-ab-faint">Discovery and Services</span>
          </h1>
          <p {...enter(200)} className="hero-in mt-5 max-w-xl text-base text-ab-muted md:text-lg">
            Browse Abellar Realty's available properties, see how far each one is from your workplace by road, and
            contact an Abellar agent near the property.
          </p>
          {/* the buttons, with the chat and agents cards peeking in at the sides on small screens */}
          <div className="relative mt-7 w-full">
            <div {...enter(620)} className="hero-in absolute -left-10 top-1/2 min-[380px]:-left-7 z-20 -translate-y-1/2 sm:left-0 xl:hidden">
              <div className="hero-float hero-float-slow rotate-6"><ChatMini /></div>
            </div>
            <div {...enter(680)} className="hero-in absolute -right-10 top-1/2 min-[380px]:-right-7 z-20 -translate-y-1/2 sm:right-0 xl:hidden">
              <div className="hero-float -rotate-6"><AgentsMini data={data} /></div>
            </div>
            <div {...enter(300)} className="hero-in mx-auto flex max-w-[200px] flex-col items-stretch gap-3 min-[560px]:max-w-none min-[560px]:flex-row min-[560px]:justify-center">
              <Link to="/properties" className="inline-flex items-center justify-center gap-2 rounded-xl bg-ab-accent px-4 py-3 text-sm font-bold sm:px-5 sm:text-base text-ab-ink transition hover:-translate-y-0.5 hover:bg-ab-accent-hover">
                Explore Properties <ArrowRight className="h-4 w-4" />
              </Link>
              <Link to="/map" className="inline-flex items-center justify-center gap-2 rounded-xl border border-ab-border-strong bg-ab-card px-4 py-3 text-sm font-bold sm:px-5 sm:text-base text-ab-text transition hover:-translate-y-0.5 hover:bg-ab-hover">
                <MapPinned className="h-4 w-4" /> View Property Map
              </Link>
            </div>
          </div>
          <div {...enter(400)} className="hero-in mt-8 flex min-h-[64px] items-start justify-center gap-8 sm:gap-14">
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
          {/* phones and tablets: the house tile under the numbers */}
          <div {...enter(740)} aria-hidden className="hero-in mt-6 xl:hidden">
            <div className={`${tile} hero-float h-12 w-12 -rotate-6 text-ab-accent`}><Home className="h-6 w-6" /></div>
          </div>
        </div>

        {/* ---- wide screens: full cards on both sides ---- */}
        <div {...enter(500)} className="hero-in absolute left-[3%] top-[7%] hidden w-[250px] xl:block">
          <div className="hero-float -rotate-3"><MapCard /></div>
        </div>
        <div {...enter(620)} className="hero-in absolute left-[2.5%] top-[45%] z-20 hidden w-[235px] xl:block">
          <div className="hero-float hero-float-slow rotate-2"><ChatCard /></div>
        </div>
        <div {...enter(560)} className="hero-in absolute right-[2.5%] top-[6%] hidden w-[250px] xl:block">
          <div className="hero-float hero-float-slow rotate-2"><PropertyFeature data={data} /></div>
        </div>
        <div {...enter(680)} aria-hidden className="hero-in absolute right-[21%] top-[13%] z-20 hidden xl:block">
          <div className={`${tile} hero-float -rotate-6 text-ab-accent`}><Home className="h-7 w-7" /></div>
        </div>
        <div {...enter(740)} className="hero-in absolute right-[2.5%] top-[47%] z-20 hidden w-[265px] xl:block">
          <div className="hero-float -rotate-2"><AgentsCard data={data} /></div>
        </div>
      </div>
    </section>
  )
}

/** The same feature cards as a decoration behind another page (the client
 *  sign-in): not clickable, not focusable and hidden from screen readers. */
export function FeatureBackdrop() {
  const [data, setData] = useState<HomeData | null>(null)
  useEffect(() => {
    let alive = true
    requestJson<HomeData>(`${API_URL}/api/v1/public/home`).then((home) => alive && setData(home)).catch(() => {})
    return () => { alive = false }
  }, [])
  return (
    <div className="pointer-events-none absolute inset-0 select-none overflow-hidden" aria-hidden="true" inert>
      {/* phones and tablets: small cards in the four corners */}
      <div className="absolute left-3 top-4 opacity-90 sm:left-8 sm:top-8 xl:hidden"><div className="hero-float -rotate-6"><MapMini /></div></div>
      <div className="absolute right-3 top-4 opacity-90 sm:right-8 sm:top-8 xl:hidden"><div className="hero-float hero-float-slow rotate-6"><PropertyMini data={data} /></div></div>
      <div className="absolute bottom-4 left-3 opacity-90 sm:bottom-8 sm:left-8 xl:hidden"><div className="hero-float hero-float-slow rotate-6"><ChatMini /></div></div>
      <div className="absolute bottom-4 right-3 opacity-90 sm:bottom-8 sm:right-8 xl:hidden"><div className="hero-float -rotate-6"><AgentsMini data={data} /></div></div>
      {/* wide screens: the full cards on both sides */}
      <div className="absolute left-[4%] top-[8%] hidden w-[250px] xl:block"><div className="hero-float -rotate-3"><MapCard /></div></div>
      <div className="absolute bottom-[10%] left-[6%] hidden w-[235px] xl:block"><div className="hero-float hero-float-slow rotate-2"><ChatCard /></div></div>
      <div className="absolute right-[4%] top-[7%] hidden w-[250px] xl:block"><div className="hero-float hero-float-slow rotate-2"><PropertyFeature data={data} /></div></div>
      <div className="absolute right-[22%] top-[14%] hidden xl:block"><div className={`${tile} hero-float -rotate-6 text-ab-accent`}><Home className="h-7 w-7" /></div></div>
      <div className="absolute bottom-[9%] right-[5%] hidden w-[265px] xl:block"><div className="hero-float -rotate-2"><AgentsCard data={data} /></div></div>
    </div>
  )
}
