import { useEffect, useState } from "react"
import { CheckCircle2, ExternalLink, LoaderCircle, LogIn, MapPin, MessageSquareText, Phone, UserRound } from "lucide-react"
import { getNearbyAgents } from "@/lib/mapApi"
import { useAuth } from "@/lib/auth"
import { useLocation } from "@/lib/router"
import { SignInToContact } from "./SignInToContact"
import { RatingSummary } from "./Stars"
import type { NearbyAgentsResult } from "@/types"
import { CallButton } from "@/components/CallButton"

type Props = {
  listingId: number | string
  selectedAgentId?: string
  onSelect?: (agentId: string) => void
  onLoaded?: (result: NearbyAgentsResult) => void
}

/** Agents near the property, from the agents table. Ranked by geographic
 *  (straight-line) proximity; road distance and car travel time are shown
 *  only when the routing provider supplied them. */
export function NearbyAgents({ listingId, selectedAgentId, onSelect, onLoaded }: Props) {
  const [data, setData] = useState<NearbyAgentsResult | null>(null)
  const [error, setError] = useState("")
  const { token, isReady } = useAuth()
  // On the map, come back to this property after signing in.
  const { pathname } = useLocation()
  const returnTo = pathname === "/map" ? `/map?property=${encodeURIComponent(String(listingId))}` : undefined

  useEffect(() => {
    if (!isReady) return // wait until a saved sign-in has been restored
    let current = true
    getNearbyAgents(listingId, token)
      .then((result) => {
        if (!current) return
        setData(result)
        onLoaded?.(result)
      })
      .catch((loadError: Error) => current && setError(loadError.message))
    return () => {
      current = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listingId, token, isReady])

  return (
    <section aria-labelledby="nearby-agents-title" className="space-y-2">
      <div className="flex items-end justify-between gap-2">
        <h3 id="nearby-agents-title" className="text-sm font-semibold text-ab-text">
          Agents near this property
        </h3>
        {data && <span className="text-[10px] text-ab-faint">Nearest first (straight-line)</span>}
      </div>

      {!data && !error && (
        <p className="flex items-center gap-2 text-sm text-ab-muted" role="status">
          <LoaderCircle className="h-4 w-4 animate-spin text-ab-accent" /> Finding nearby agents…
        </p>
      )}
      {error && <p className="rounded-lg border border-ab-warning/40 bg-ab-warning/10 px-3 py-2 text-xs text-ab-warning">{error}</p>}
      {data && data.agents.length === 0 && <p className="text-sm text-ab-muted">No active agents are available right now.</p>}
      {data && data.agents.some((agent) => agent.contact_requires_sign_in) && <SignInToContact returnTo={returnTo} />}

      {data && data.agents.length > 0 && (
        <ul className="space-y-2">
          {data.agents.map((agent) => {
            const isSelected = selectedAgentId === agent.agent_id
            return (
              <li
                key={agent.agent_id}
                className={`rounded-xl border p-3 transition ${isSelected ? "border-ab-accent bg-ab-accent-soft" : "border-ab-border bg-ab-card-2"}`}
              >
                <div className="flex items-start gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ab-hover text-ab-accent">
                    <UserRound className="h-5 w-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-x-2 text-sm font-semibold text-ab-text">
                      {agent.full_name}
                      <a
                        href={`/agents/${encodeURIComponent(agent.agent_id)}`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-0.5 text-[11px] font-medium text-ab-accent hover:underline"
                      >
                        Profile <ExternalLink className="h-3 w-3" />
                      </a>
                    </p>
                    <RatingSummary rating={agent.client_rating} count={agent.review_count} compact />
                    {agent.agent_location && (
                      <p className="flex items-center gap-1 text-xs text-ab-muted">
                        <MapPin className="h-3 w-3 shrink-0" /> {agent.agent_location}
                      </p>
                    )}
                    <p className="mt-1 text-xs tabular-nums text-ab-muted">
                      {agent.road_distance_km != null && agent.travel_time_min != null ? (
                        <>
                          <strong className="text-ab-text">{agent.road_distance_km.toFixed(1)} km by road</strong> · ~
                          {Math.max(1, agent.travel_time_min)} min by car
                        </>
                      ) : agent.straight_line_km != null ? (
                        <>{agent.straight_line_km.toFixed(1)} km away (straight-line)</>
                      ) : (
                        <>Location not on the map</>
                      )}
                    </p>
                  </div>
                </div>
                <div className="mt-2.5 flex flex-wrap gap-2">
                  {agent.contact_requires_sign_in && agent.has_phone && (
                    <SignInToContact compact returnTo={returnTo}>
                      <LogIn className="h-3.5 w-3.5 text-ab-accent" /> Sign in to call or text
                    </SignInToContact>
                  )}
                  {agent.phone_number && (
                    <>
                      <CallButton
                        phone={agent.phone_number}
                        name={agent.full_name}
                        className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-ab-border bg-ab-card px-3 text-xs font-semibold text-ab-text transition hover:bg-ab-hover"
                      >
                        <Phone className="h-3.5 w-3.5 text-ab-accent" /> Call
                      </CallButton>
                      <CallButton
                        kind="text"
                        phone={agent.phone_number}
                        name={agent.full_name}
                        className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-ab-border bg-ab-card px-3 text-xs font-semibold text-ab-text transition hover:bg-ab-hover"
                      >
                        <MessageSquareText className="h-3.5 w-3.5 text-ab-accent" /> Text
                      </CallButton>
                    </>
                  )}
                  {onSelect && (
                    <button
                      type="button"
                      onClick={() => onSelect(agent.agent_id)}
                      aria-pressed={isSelected}
                      className={`ml-auto inline-flex min-h-10 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold transition ${
                        isSelected ? "bg-ab-accent text-ab-ink" : "border border-ab-border-strong bg-ab-card text-ab-text hover:bg-ab-hover"
                      }`}
                    >
                      {isSelected && <CheckCircle2 className="h-3.5 w-3.5" />}
                      {isSelected ? "Selected" : "Request this agent"}
                    </button>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {data && <p className="text-[10px] leading-snug text-ab-faint">{data.routing.message}</p>}
    </section>
  )
}
