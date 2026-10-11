import { t } from "./i18n"

// Screenshots of the Management System itself (public/manage-showcase),
// arranged as one main window with cards floating over it.
const SHOTS = {
  dashboard: { src: "/manage-showcase/dashboard.webp", width: 1343, height: 683 },
  recommendations: { src: "/manage-showcase/recommendations.webp", width: 1050, height: 450 },
  agent: { src: "/manage-showcase/agent.webp", width: 672, height: 400 },
  property: { src: "/manage-showcase/property.webp", width: 665, height: 600 },
} as const

const card = "absolute overflow-hidden rounded-2xl bg-ab-card ring-1 ring-black/10 shadow-[0_28px_60px_-24px_rgba(0,0,0,0.55)]"

function Shot({ name, label }: { name: keyof typeof SHOTS; label: string }) {
  const shot = SHOTS[name]
  return (
    <>
      <img src={shot.src} width={shot.width} height={shot.height} alt="" className="block h-auto w-full" loading="eager" decoding="async" />
      <span className="sr-only">{label}</span>
    </>
  )
}

/** Phones: the same windows, smaller, filling the top of the sign-in page. */
function CompactShowcase() {
  return (
    <div className="absolute inset-0 overflow-hidden bg-ab-accent-soft" aria-label={t("A look at the Management System")} role="img">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,color-mix(in_oklab,var(--color-ab-accent)_40%,transparent),transparent_60%)]" aria-hidden />
      <div className={`${card} left-[9%] top-[25%] w-[120%] rounded-xl sm:left-[14%] sm:w-[95%]`}>
        <div className="hero-in" style={{ animationDelay: "80ms" }}>
          <div className="flex items-center gap-1 border-b border-ab-border bg-ab-card-2 px-2 py-1.5" aria-hidden>
            <span className="h-2 w-2 rounded-full bg-[#FF5F57]" />
            <span className="h-2 w-2 rounded-full bg-[#FEBC2E]" />
            <span className="h-2 w-2 rounded-full bg-[#28C840]" />
            <span className="ml-2 truncate text-[9px] font-medium text-ab-faint">Alty MSA · {t("Dashboard")}</span>
          </div>
          <Shot name="dashboard" label={t("Dashboard")} />
        </div>
      </div>
      <div className={`${card} left-[3%] top-[50%] z-20 w-[42%] rounded-xl sm:w-[32%]`}>
        <div className="hero-in" style={{ animationDelay: "220ms" }}><Shot name="agent" label={t("Agents")} /></div>
      </div>
      <div className={`${card} right-[4%] top-[38%] z-30 w-[34%] rounded-xl sm:w-[26%]`}>
        <div className="hero-in" style={{ animationDelay: "340ms" }}><Shot name="property" label={t("Properties")} /></div>
      </div>
    </div>
  )
}

/** Sign-in panel: the system's own pages, stacked like a collage
 *  (`compact`: the phone version at the top of the page). */
export function SystemShowcase({ compact = false }: { compact?: boolean }) {
  if (compact) return <CompactShowcase />
  return (
    <aside className="relative min-h-[560px] overflow-hidden rounded-[2rem] bg-ab-accent-soft" aria-label={t("A look at the Management System")}>
      {/* soft light behind the windows */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_85%_15%,color-mix(in_oklab,var(--color-ab-accent)_38%,transparent),transparent_55%),radial-gradient(circle_at_10%_95%,color-mix(in_oklab,var(--color-ab-accent)_22%,transparent),transparent_50%)]" aria-hidden />

      {/* Narrower screens: the headline uses the width the top card leaves free on wide ones. */}
      <div className="hero-in relative max-w-[88%] p-9 xl:max-w-[46%]">
        <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-ab-accent">ALTY · Abellar Realty</p>
        <p className="mt-3 text-xl font-extrabold leading-snug text-ab-text xl:text-2xl">
          {t("Listings, clients, documents and deals — managed in one place.")}
        </p>
      </div>

      {/* main window: the dashboard */}
      <div className={`${card} right-[-9%] top-[31%] w-[92%]`}>
        <div className="hero-in" style={{ animationDelay: "120ms" }}>
          <div className="flex items-center gap-1.5 border-b border-ab-border bg-ab-card-2 px-3 py-2" aria-hidden>
            <span className="h-2.5 w-2.5 rounded-full bg-[#FF5F57]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#FEBC2E]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#28C840]" />
            <span className="ml-3 truncate text-[10px] font-medium text-ab-faint">Alty MSA · {t("Dashboard")}</span>
          </div>
          <Shot name="dashboard" label={t("Dashboard")} />
        </div>
      </div>

      {/* floating cards */}
      <div className={`${card} right-[5%] top-[14%] z-10 hidden w-[44%] xl:block`}>
        <div className="hero-in" style={{ animationDelay: "260ms" }}><Shot name="recommendations" label={t("Recommendations")} /></div>
      </div>
      <div className={`${card} left-[4%] top-[47%] z-20 w-[31%]`}>
        <div className="hero-in" style={{ animationDelay: "380ms" }}><Shot name="agent" label={t("Agents")} /></div>
      </div>
      <div className={`${card} bottom-[4%] left-[29%] z-30 w-[29%]`}>
        <div className="hero-in" style={{ animationDelay: "500ms" }}><Shot name="property" label={t("Properties")} /></div>
      </div>
    </aside>
  )
}
