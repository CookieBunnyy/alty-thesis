import { API_URL } from "@/config"
import type { PublicPartner } from "@/types"

/** One partner: its logo, or its name as a wordmark when no logo is set. */
function PartnerMark({ partner, hidden }: { partner: PublicPartner; hidden: boolean }) {
  const mark = partner.logo_url ? (
    <img src={`${API_URL}${partner.logo_url}`} alt={partner.name} loading="lazy" decoding="async"
      className="partner-logo h-9 w-auto max-w-[150px] object-contain sm:h-10" />
  ) : (
    <span className="partner-wordmark whitespace-nowrap text-lg font-extrabold tracking-tight sm:text-xl">{partner.name}</span>
  )
  const className = "partner-item flex h-16 shrink-0 items-center justify-center px-2"
  if (partner.website) {
    return (
      <a href={partner.website} target="_blank" rel="noopener noreferrer" className={className}
        aria-label={hidden ? undefined : `${partner.name} (opens their website)`} tabIndex={hidden ? -1 : undefined}>
        {mark}
      </a>
    )
  }
  return <span className={className}>{mark}</span>
}

/** Home page: the developers and partners Abellar Realty works with, in a
 *  row that loops to the right (pauses while hovered or focused). */
export function PartnersStrip({ partners }: { partners: PublicPartner[] }) {
  if (partners.length === 0) return null
  // Enough copies that one lap is wider than the screen, then the lap twice:
  // moving by exactly one lap makes the loop seamless.
  const copies = Math.max(1, Math.ceil(10 / partners.length))
  const lap = Array.from({ length: copies }, () => partners).flat()
  const count = partners.length
  return (
    <div className="grid items-center gap-6 md:grid-cols-[minmax(0,280px)_minmax(0,1fr)] md:gap-10">
      <p className="text-base leading-relaxed text-ab-text">
        Working with {count} trusted {count === 1 ? "developer and partner" : "developers and partners"} on the homes we offer.
      </p>
      <div className="ab-marquee-wrap ab-marquee-mask min-w-0 overflow-hidden" aria-label="Our developers and partners" role="region">
        <div className="ab-marquee flex w-max items-center" style={{ ["--marquee-duration" as string]: `${Math.max(24, lap.length * 4)}s` }}>
          {[0, 1].map((half) => (
            <ul key={half} className="flex shrink-0 items-center gap-14 pr-14" aria-hidden={half === 1 || undefined}>
              {lap.map((partner, index) => (
                <li key={`${partner.id}-${index}`} aria-hidden={half === 1 || index >= count || undefined}>
                  <PartnerMark partner={partner} hidden={half === 1 || index >= count} />
                </li>
              ))}
            </ul>
          ))}
        </div>
      </div>
    </div>
  )
}
