// Profile photos: agents (public photos, also shown on the website) and staff
// accounts (only for signed-in staff). Initials are shown until a photo is set.
import { useRef, useState } from "react"
import { Camera, LoaderCircle, Trash2 } from "lucide-react"
import { API_URL } from "@/config"
import { t } from "./i18n"
import { Button } from "./ui"
import { useBlobUrl } from "./useBlobUrl"

const SIZES = { sm: "h-9 w-9 text-xs", md: "h-12 w-12 text-sm", lg: "h-24 w-24 text-2xl" } as const
type Size = keyof typeof SIZES

const initials = (name: string) => name.split(/\s+/).filter(Boolean).map((part) => part[0]).slice(0, 2).join("").toUpperCase() || "?"

export function Avatar({ name, src, size = "sm" }: { name: string; src?: string | null; size?: Size }) {
  return src ? (
    <img src={src} alt="" className={`${SIZES[size]} shrink-0 rounded-full object-cover ring-1 ring-ab-border`} />
  ) : (
    <span aria-hidden className={`${SIZES[size]} flex shrink-0 items-center justify-center rounded-full bg-ab-accent-soft font-extrabold text-ab-accent`}>
      {initials(name)}
    </span>
  )
}

/** An agent's photo (public URL; the version refreshes it after a change). */
export function AgentAvatar({ agentId, name, version, size }: { agentId: string; name: string; version?: number | null; size?: Size }) {
  const src = version ? `${API_URL}/api/v1/public/agents/${encodeURIComponent(agentId)}/photo?v=${version}` : null
  return <Avatar name={name} src={src} size={size} />
}

/** A staff account's photo (loaded with the signed-in session). */
export function StaffAvatar({ userId, name, version, size }: { userId: number; name: string; version?: number | null; size?: Size }) {
  const { url } = useBlobUrl(version ? `/users/${userId}/photo?v=${version}` : null)
  return <Avatar name={name} src={version ? url : null} size={size} />
}

/** "Upload photo / Change photo" and "Remove" buttons with a hidden file picker. */
export function PhotoControls({ hasPhoto, onUpload, onRemove }: {
  hasPhoto: boolean; onUpload: (file: File) => Promise<void>; onRemove: () => Promise<void>
}) {
  const picker = useRef<HTMLInputElement | null>(null)
  const [busy, setBusy] = useState<"" | "upload" | "remove">("")
  const run = async (kind: "upload" | "remove", action: () => Promise<void>) => {
    setBusy(kind)
    try {
      await action()
    } finally {
      setBusy("")
      if (picker.current) picker.current.value = ""
    }
  }
  return (
    <div className="flex flex-wrap gap-2">
      <input ref={picker} type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" aria-label={t("Profile photo")}
        onChange={(e) => { const file = e.target.files?.[0]; if (file) void run("upload", () => onUpload(file)) }} />
      <Button onClick={() => picker.current?.click()} disabled={!!busy}>
        {busy === "upload" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />}
        {hasPhoto ? t("Change photo") : t("Upload photo")}
      </Button>
      {hasPhoto && (
        <Button variant="danger" onClick={() => void run("remove", onRemove)} disabled={!!busy}>
          {busy === "remove" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />} {t("Remove photo")}
        </Button>
      )}
    </div>
  )
}
