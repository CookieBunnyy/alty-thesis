import { publicUrl } from "@/config"

/** An agent's profile photo, or their initials until one is set. */
export function AgentPhoto({ name, photoUrl, className }: { name: string; photoUrl?: string | null; className: string }) {
  if (photoUrl) return <img src={publicUrl(photoUrl)} alt="" loading="lazy" className={`${className} shrink-0 object-cover`} />
  const letters = name.split(/\s+/).filter(Boolean).map((part) => part[0]).slice(0, 2).join("").toUpperCase()
  return <span aria-hidden className={`${className} flex shrink-0 items-center justify-center bg-ab-accent font-black text-ab-ink`}>{letters}</span>
}
