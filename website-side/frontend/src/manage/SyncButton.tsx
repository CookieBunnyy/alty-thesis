import { useState } from "react"
import { CloudDownload, LoaderCircle } from "lucide-react"
import { Button } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"

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
      const parts = [`${r.inserted ?? 0} new`, `${r.updated ?? 0} updated`]
      if (r.skipped_pending) parts.push(`${r.skipped_pending} kept (local changes pending)`)
      if (r.errors) parts.push(`${r.errors} failed`)
      toast(`${what} synced from Supabase: ${parts.join(", ")}.${r.error_messages?.length ? ` ${r.error_messages[0]}` : ""}`, r.errors ? "error" : "success")
      onDone()
    } catch (error) {
      toast(`${what} sync failed: ${(error as Error).message}`, "error")
    } finally {
      setBusy(false)
    }
  }
  return (
    <Button onClick={run} disabled={busy} title={`Pull ${what.toLowerCase()} from the central database`}>
      {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <CloudDownload className="h-4 w-4" />} Sync from Supabase
    </Button>
  )
}
