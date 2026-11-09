// A buyer's site trippings (site visits) and the schedule messages from their
// agent. Checks for changes every 15 seconds, so a reschedule shows up live.
import { useEffect, useState } from "react"
import { BellRing, Bus, Clock, MapPin, Phone } from "lucide-react"
import { useAuth } from "@/lib/auth"

type ClientTrip = {
  id: number; trip_date: string; pickup_time: string; pickup_point: string; subdivision: string; status: string
  agent: { full_name: string; phone_number: string | null } | null; updated_at: string
  notices: { id: number; message: string; sent_by: string | null; created_at: string; read: boolean }[]
}
type Reply = { unread: number; trips: ClientTrip[] }

const STATUS: Record<string, string> = {
  SCHEDULED: "bg-ab-warning/15 text-ab-warning", CONFIRMED: "bg-ab-success/15 text-ab-success",
  ONGOING: "bg-ab-accent-soft text-ab-accent", DONE: "bg-ab-hover text-ab-muted", CANCELLED: "bg-ab-danger/15 text-ab-danger",
}
const day = (iso: string) => new Intl.DateTimeFormat("en-PH", { weekday: "long", month: "long", day: "numeric", year: "numeric" }).format(new Date(`${iso}T00:00:00`))
const clock = (hhmm: string) => {
  const [h, m] = hhmm.split(":").map(Number)
  return new Date(2000, 0, 1, h, m).toLocaleTimeString("en-PH", { hour: "numeric", minute: "2-digit" })
}
const when = (iso: string) => new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso.endsWith("Z") ? iso : `${iso}Z`))

export function MyTrips() {
  const { authed } = useAuth()
  const [data, setData] = useState<Reply | null>(null)

  useEffect(() => {
    let alive = true
    const check = async () => {
      if (document.hidden) return
      try {
        const reply = await authed<Reply>("/trips")
        if (!alive) return
        setData(reply)
        if (reply.unread) void authed("/trips/read", { method: "POST" }).catch(() => {})
      } catch { /* keep the last schedule shown */ }
    }
    void check()
    const timer = window.setInterval(check, 15000)
    return () => { alive = false; window.clearInterval(timer) }
  }, [authed])

  if (!data || data.trips.length === 0) return null
  return (
    <section id="trips" className="scroll-mt-24">
      <h2 className="flex items-center gap-2 text-xl font-bold">
        My site trippings {data.unread > 0 && <span className="rounded-full bg-ab-accent px-2 py-0.5 text-xs text-ab-ink">{data.unread} new</span>}
      </h2>
      <p className="text-sm text-ab-muted">Your scheduled site visits. Changes from your agent show up here right away.</p>
      <ul className="mt-4 grid gap-4 md:grid-cols-2">
        {data.trips.map((trip) => (
          <li key={trip.id} className={`rounded-2xl border bg-ab-card p-5 ${trip.status === "CANCELLED" ? "border-ab-danger/40" : "border-ab-border"}`}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-ab-accent"><Bus className="h-4 w-4" /> Site tripping</p>
                <h3 className="text-lg font-bold">{trip.subdivision}</h3>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS[trip.status] ?? STATUS.SCHEDULED}`}>{trip.status.charAt(0) + trip.status.slice(1).toLowerCase()}</span>
            </div>
            <dl className="mt-3 space-y-1.5 text-sm">
              <div className="flex gap-2"><Clock className="mt-0.5 h-4 w-4 shrink-0 text-ab-faint" /><dt className="sr-only">When</dt><dd className="font-semibold">{day(trip.trip_date)} · {clock(trip.pickup_time)}</dd></div>
              <div className="flex gap-2"><MapPin className="mt-0.5 h-4 w-4 shrink-0 text-ab-faint" /><dt className="sr-only">Pick-up</dt><dd>Pick-up: {trip.pickup_point}</dd></div>
              {trip.agent && (
                <div className="flex gap-2"><Phone className="mt-0.5 h-4 w-4 shrink-0 text-ab-faint" /><dt className="sr-only">Agent</dt>
                  <dd>Agent: {trip.agent.full_name}{trip.agent.phone_number && <> · <a href={`tel:${trip.agent.phone_number.replace(/\s/g, "")}`} className="font-semibold text-ab-accent hover:underline">{trip.agent.phone_number}</a></>}</dd>
                </div>
              )}
            </dl>
            {trip.notices.length > 0 && (
              <div className="mt-3 space-y-2 border-t border-ab-border pt-3">
                {trip.notices.slice(0, 3).map((notice) => (
                  <p key={notice.id} className={`rounded-xl px-3 py-2 text-xs ${notice.read ? "bg-ab-card-2" : "bg-ab-accent-soft"}`}>
                    <BellRing className="mr-1 inline h-3.5 w-3.5 text-ab-accent" />{notice.message}
                    <span className="mt-0.5 block text-[10px] text-ab-faint">{notice.sent_by} · {when(notice.created_at)}</span>
                  </p>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
