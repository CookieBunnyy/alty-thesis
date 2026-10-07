import { useCallback, useState } from "react"
import { CloudUpload, LoaderCircle, Moon, Sun } from "lucide-react"
import { useTheme } from "@/hooks/useTheme"
import { statusLabel } from "./format"
import { Button, LoadState, PageHeader, Section } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData } from "./useApiData"
import { useLanguage } from "./languageContext"
import { LANGUAGES, t, type Lang } from "./i18n"
import { photoBody } from "./photoBody"
import { PhotoControls, StaffAvatar } from "./avatars"

type Sync = { enabled: boolean; counts: Record<string, Record<string, number>> }
type PushReport = { reason?: string; tables?: Record<string, { pushed: number; failed: number; errors: string[] }>; warnings?: string[] }

/** Everyone: appearance and language. Administrator: system configuration and
 *  pushing pending records to the central database (same rules as the desktop). */
export function SettingsPage() {
  const { user, api, reloadUser } = useStaffAuth()
  const toast = useToast()
  const { theme, setTheme } = useTheme()
  const { lang, setLang } = useLanguage()
  const isAdmin = user?.role === "Administrator"
  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <PageHeader title="How ALTY looks and works for you" subtitle={isAdmin ? "Appearance, language, system configuration and synchronization." : "Choose how the Management System looks and which language it uses."} />
      {user && (
        <Section title="Profile picture">
          <div className="flex flex-wrap items-center gap-4">
            <StaffAvatar userId={user.id} name={user.full_name} version={user.photo_version} size="lg" />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{user.full_name}</p>
              <p className="mb-2 text-xs text-ab-faint">{t("Shown in the top bar and to other staff. JPG, PNG or WEBP; it's cropped to a square.")}</p>
              <PhotoControls
                hasPhoto={Boolean(user.photo_version)}
                onUpload={async (file) => {
                  try {
                    await api("/users/me/photo", { method: "PUT", body: photoBody(file) })
                    await reloadUser()
                    toast(t("Profile picture updated."))
                  } catch (uploadError) { toast(t((uploadError as Error).message), "error") }
                }}
                onRemove={async () => {
                  try {
                    await api("/users/me/photo", { method: "DELETE" })
                    await reloadUser()
                    toast(t("Profile picture removed."))
                  } catch (removeError) { toast(t((removeError as Error).message), "error") }
                }}
              />
            </div>
          </div>
        </Section>
      )}
      <Section title="Appearance">
        <div className="flex flex-wrap items-center gap-2">
          {([["dark", "Dark mode", Moon], ["light", "Light mode", Sun]] as const).map(([mode, label, Icon]) => (
            <button key={mode} type="button" aria-pressed={theme === mode} onClick={() => setTheme(mode)}
              className={`inline-flex min-h-10 items-center gap-2 rounded-xl border px-4 text-sm font-semibold transition ${theme === mode ? "border-ab-accent bg-ab-accent text-ab-ink" : "border-ab-border-strong hover:bg-ab-hover"}`}>
              <Icon className="h-4 w-4" /> {t(label)}
            </button>
          ))}
          <p className="text-xs text-ab-faint sm:ml-3">{t("Saved on this browser. The desktop app keeps its own setting.")}</p>
        </div>
      </Section>
      <Section title="Language">
        <div className="flex flex-wrap items-center gap-2" role="radiogroup" aria-label={t("Language")}>
          {(Object.entries(LANGUAGES) as [Lang, string][]).map(([code, name]) => (
            <button key={code} type="button" role="radio" aria-checked={lang === code} onClick={() => setLang(code)}
              className={`inline-flex min-h-10 items-center gap-2 rounded-xl border px-4 text-sm font-semibold transition ${lang === code ? "border-ab-accent bg-ab-accent text-ab-ink" : "border-ab-border-strong hover:bg-ab-hover"}`}>
              <span className="text-[11px] font-bold uppercase tracking-wide opacity-70">{code === "fil" ? "FIL" : "EN"}</span> {name}
            </button>
          ))}
          <p className="text-xs text-ab-faint sm:ml-3">{t("Changes every page of the Management System. Names, addresses and other record details stay as they were entered.")}</p>
        </div>
      </Section>
      {isAdmin ? <AdminSettings /> : <p className="text-xs text-ab-faint">{t("System configuration is available to the Administrator.")}</p>}
    </div>
  )
}

function AdminSettings() {
  const { api } = useStaffAuth()
  const toast = useToast()
  const [pushing, setPushing] = useState(false)
  const load = useCallback(() => Promise.all([api<Record<string, Record<string, unknown>>>("/system/settings"), api<Sync>("/system/sync")]), [api])
  const { data, error, loading, reload } = useApiData(load, "settings")
  const [config, sync] = data ?? [null, null]
  const pending = sync ? Object.values(sync.counts).reduce((s, c) => s + (c.PENDING ?? 0), 0) : 0

  const push = async () => {
    setPushing(true)
    try {
      const report = await api<PushReport>("/system/sync/push", { method: "POST" })
      const tables = Object.entries(report.tables ?? {})
      const failed = tables.reduce((s, [, r]) => s + r.failed, 0)
      toast(report.reason ? t(report.reason) : tables.length ? tables.map(([name, r]) => `${statusLabel(name)}: ${t("{n} pushed", { n: r.pushed })}${r.failed ? `, ${t("{n} failed", { n: r.failed })}` : ""}`).join(" · ") : t("Nothing to push."), failed ? "error" : "success")
      void reload()
    } catch (pushError) {
      toast((pushError as Error).message, "error")
    } finally {
      setPushing(false)
    }
  }

  const show = (value: unknown): string =>
    value === null || value === undefined ? "—" : typeof value === "boolean" ? t(value ? "Yes" : "No")
      : Array.isArray(value) ? value.join(", ") : typeof value === "object" ? Object.entries(value as Record<string, unknown>).map(([k, v]) => `${statusLabel(k)}: ${show(v)}`).join(" · ") : String(value)

  return (
    <>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {sync && (
        <Section title="Synchronization with the central database (Supabase)"
          action={<Button variant="primary" onClick={push} disabled={pushing || !sync.enabled}>{pushing ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <CloudUpload className="h-4 w-4" />} {t("Push pending records")}</Button>}>
          <p className="mb-3 text-sm text-ab-muted">{t(sync.enabled ? "Cloud sync is enabled." : "Cloud sync is disabled or not configured.")} {pending ? t("{n} record(s) are waiting to be pushed.", { n: pending }) : t("Nothing is waiting to be pushed.")}</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {Object.entries(sync.counts).map(([table, counts]) => (
              <div key={table} className="rounded-xl border border-ab-border p-3">
                <p className="text-xs font-semibold text-ab-muted">{statusLabel(table)}</p>
                {Object.entries(counts).map(([state, n]) => <p key={state} className="text-sm tabular-nums">{statusLabel(state)} <span className="font-bold">{n}</span></p>)}
                {!Object.keys(counts).length && <p className="text-sm text-ab-faint">{t("None")}</p>}
              </div>
            ))}
          </div>
        </Section>
      )}
      {config && (
        <Section title="System configuration (read-only)">
          <p className="mb-3 text-xs text-ab-faint">{t("Values the API server is running with. Secrets are never shown; settings are changed in the server's environment (Render), not here.")}</p>
          <dl className="divide-y divide-ab-border text-sm">
            {Object.entries(config).flatMap(([section, values]) => Object.entries(values).map(([key, value]) => (
              <div key={`${section}.${key}`} className="grid gap-1 py-2 sm:grid-cols-[180px_200px_1fr]">
                <dt className="text-xs font-semibold uppercase tracking-wide text-ab-faint">{statusLabel(section)}</dt>
                <dt className="text-ab-muted">{statusLabel(key)}</dt>
                <dd className="break-words font-medium">{show(value)}</dd>
              </div>
            )))}
          </dl>
        </Section>
      )}
    </>
  )
}
