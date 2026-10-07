import { useState } from "react"
import { CloudDownload, LoaderCircle } from "lucide-react"
import { Button } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { t } from "./i18n"

type SyncResult = { total?: number; inserted?: number; updated?: number; skipped_pending?: number; errors?: number; error_messages?: string[] }

/** "Sync from Supabase" (management roles): the same endpoint as the desktop. */
export function SyncButton({ path, what, onDone }: { path: string; what: string; onDone: () => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const run = async () => {
    setBusy(true)
    try {
      const r = await api<SyncResult>(path, { method: "POST" })
      const parts = [t("{n} new", { n: r.inserted ?? 0 }), t("{n} updated", { n: r.updated ?? 0 })]
      if (r.skipped_pending) parts.push(t("{n} kept (local changes pending)", { n: r.skipped_pending }))
      if (r.errors) parts.push(t("{n} failed", { n: r.errors }))
      toast(`${t("{what} synced from Supabase:", { what: t(what) })} ${parts.join(", ")}.${r.error_messages?.length ? ` ${r.error_messages[0]}` : ""}`, r.errors ? "error" : "success")
      onDone()
    } catch (error) {
      toast(t("{what} sync failed: {error}", { what: t(what), error: (error as Error).message }), "error")
    } finally {
      setBusy(false)
    }
  }
  return (
    <Button onClick={run} disabled={busy} title={t("Pull {what} from the central database", { what: t(what).toLowerCase() })}>
      {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <CloudDownload className="h-4 w-4" />} {t("Sync from Supabase")}
    </Button>
  )
}
