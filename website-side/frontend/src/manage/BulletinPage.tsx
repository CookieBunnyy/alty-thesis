// The office bulletin board, online. Announcements: monthly meetings,
// updates and project flyers. Memos: sales targets, incentives and sales
// notices. The Administrator posts; everyone is notified of each new post.
import { useCallback, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react"
import { Archive, CalendarDays, ImagePlus, LoaderCircle, Megaphone, Pencil, Pin, Plus, StickyNote, Target, Trash2, Trophy, X } from "lucide-react"
import { date, dateTime, isManagement, peso, pesoShort } from "./format"
import { Button, Confirm, LoadState, PageHeader } from "./ui"
import { useStaffAuth } from "./staffContext"
import { useToast } from "./toastContext"
import { useApiData } from "./useApiData"
import { useBlobUrl } from "./useBlobUrl"
import { useBranchOptions } from "./branches"
import { t } from "./i18n"

type Tier = { label: string; minimum_sales: number; reward?: string | null }
type Sale = { date: string; buyer: string | null; agent: string | null; project: string | null; tcp: number; status: string; type: string }
type Progress = {
  period: { from: string | null; until: string | null }
  mine?: { sales: number; deals: number; reached?: string | null; next?: { label: string; missing: number } | null; reward_total?: number }
  company?: { sales: number; deals: number; percent: number | null }
  leaders?: { agent_id: string; name: string; sales: number; deals: number; reached: string | null; reward_total?: number }[]
}
type Post = {
  id: number; board: "ANNOUNCEMENT" | "MEMO"; category: string; title: string; body: string | null
  event_at: string | null; valid_from: string | null; valid_until: string | null
  target_amount: number | null; tiers: Tier[] | null; reward_amount: number | null
  branch_id: number | null; branch_name: string | null; partner_id: number | null; partner_name: string | null
  listing_id: number | null; transaction_id: string | null; sale: Sale | null
  has_image: boolean; image_url: string | null; pinned: boolean; archived: boolean
  created_by: string | null; created_at: string; progress: Progress | null
}

const CATEGORY_LABELS: Record<string, string> = {
  MEETING: "Monthly meeting", UPDATE: "Update", PROJECT: "Project / flyer", GENERAL: "General",
  TARGET: "Target sales", INCENTIVE: "Incentive", SALES_NOTICE: "Sales notice",
}
const CATEGORIES = { ANNOUNCEMENT: ["MEETING", "UPDATE", "PROJECT", "GENERAL"], MEMO: ["TARGET", "INCENTIVE", "SALES_NOTICE", "GENERAL"] }

export function BulletinPage() {
  const { api, user } = useStaffAuth()
  const manage = isManagement(user?.role)
  const [board, setBoard] = useState<"ANNOUNCEMENT" | "MEMO">("ANNOUNCEMENT")
  const [archived, setArchived] = useState(false)
  const [editing, setEditing] = useState<Post | "new" | null>(null)
  const load = useCallback(() => api<Post[]>(`/bulletin?board=${board}${archived ? "&include_archived=true" : ""}`), [api, board, archived])
  const { data, error, loading, reload } = useApiData(load, `bulletin:${board}:${archived}`)
  const posts = data ?? []

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageHeader
        title="Announcements and memos"
        subtitle="The office bulletin board: monthly meetings, updates and project flyers; sales targets, incentives and sales notices. Everyone is notified when something new is posted."
        actions={manage && <Button variant="primary" onClick={() => setEditing("new")}><Plus className="h-4 w-4" /> {t("New post")}</Button>}
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div role="tablist" aria-label={t("Board")} className="flex w-fit rounded-xl border border-ab-border bg-ab-card p-1">
          {([["ANNOUNCEMENT", "Announcements", Megaphone], ["MEMO", "Memos", StickyNote]] as const).map(([key, label, Icon]) => (
            <button key={key} type="button" role="tab" aria-selected={board === key} onClick={() => setBoard(key)}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold ${board === key ? "bg-ab-accent text-ab-ink" : "text-ab-muted hover:text-ab-text"}`}>
              <Icon className="h-4 w-4" /> {t(label)}
            </button>
          ))}
        </div>
        {manage && (
          <label className="flex items-center gap-2 text-sm text-ab-muted">
            <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} className="h-4 w-4 accent-[var(--color-ab-accent)]" /> {t("Show archived")}
          </label>
        )}
      </div>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && posts.length === 0 && (
        <div className="rounded-2xl border border-dashed border-ab-border px-4 py-14 text-center text-sm text-ab-muted">
          {t(board === "ANNOUNCEMENT" ? "No announcements yet." : "No memos yet.")}
          {manage && <p className="mt-1 text-xs text-ab-faint">{t("Use “New post” to put something on the board. Everyone gets a notification.")}</p>}
        </div>
      )}
      {posts.length > 0 && (
        <ul className="grid gap-4 md:grid-cols-2">
          {posts.map((post) => <PostCard key={post.id} post={post} manage={manage} onEdit={() => setEditing(post)} />)}
        </ul>
      )}
      {editing && <PostForm post={editing === "new" ? null : editing} board={board} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void reload() }} />}
    </div>
  )
}

function FlyerImage({ url, alt }: { url: string; alt: string }) {
  const { url: blob } = useBlobUrl(url.replace(/^\/api\/v1/, ""))
  return blob ? <img src={blob} alt={alt} className="max-h-80 w-full bg-ab-card-2 object-contain" /> : <div className="h-40 animate-pulse bg-ab-card-2" />
}

function PostCard({ post, manage, onEdit }: { post: Post; manage: boolean; onEdit: () => void }) {
  const memo = post.board === "MEMO"
  return (
    <li className={`relative overflow-hidden rounded-2xl border bg-ab-card ${post.pinned ? "border-ab-accent" : "border-ab-border"} ${post.archived ? "opacity-60" : ""} ${post.category === "SALES_NOTICE" ? "md:col-span-1" : ""}`}>
      {post.image_url && <FlyerImage url={post.image_url} alt={post.title} />}
      <div className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="flex flex-wrap items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-ab-accent">
              {post.pinned && <Pin className="h-3 w-3" aria-label={t("Pinned")} />}
              {t(CATEGORY_LABELS[post.category] ?? post.category)}
              {post.branch_name && <span className="rounded bg-ab-warning/20 px-1.5 py-0.5 text-ab-text">{post.branch_name}</span>}
              {post.archived && <span className="rounded bg-ab-hover px-1.5 py-0.5 text-ab-muted">{t("Archived")}</span>}
            </p>
            <h3 className="mt-0.5 text-lg font-extrabold leading-tight">{post.title}</h3>
          </div>
          {manage && <button type="button" onClick={onEdit} aria-label={t("Edit post")} className="rounded-lg p-1.5 text-ab-muted hover:bg-ab-hover"><Pencil className="h-4 w-4" /></button>}
        </div>
        {post.event_at && (
          <p className="flex items-center gap-1.5 rounded-xl bg-ab-card-2 px-3 py-2 text-sm font-semibold"><CalendarDays className="h-4 w-4 text-ab-accent" /> {dateTime(post.event_at)}</p>
        )}
        {memo && post.category === "TARGET" && <TargetMemo post={post} />}
        {memo && post.category === "INCENTIVE" && <IncentiveMemo post={post} />}
        {post.category === "SALES_NOTICE" && post.sale && <SalesNotice sale={post.sale} />}
        {post.body && <p className="whitespace-pre-line text-sm text-ab-muted">{post.body}</p>}
        {(post.valid_from || post.valid_until) && post.category !== "TARGET" && post.category !== "INCENTIVE" && (
          <p className="text-xs font-semibold text-ab-muted">{t("Valid {from} – {until}", { from: post.valid_from ? date(post.valid_from) : "…", until: post.valid_until ? date(post.valid_until) : "…" })}</p>
        )}
        {post.partner_name && <p className="text-xs text-ab-faint">{t("Developer: {name}", { name: post.partner_name })}</p>}
        <p className="border-t border-ab-border pt-2 text-[11px] text-ab-faint">{t("Posted by {name} · {when}", { name: post.created_by ?? "—", when: dateTime(post.created_at) })}</p>
      </div>
    </li>
  )
}

function Period({ post }: { post: Post }) {
  if (!post.valid_from && !post.valid_until) return null
  return <p className="text-xs font-semibold text-ab-muted">{t("Valid {from} – {until}", { from: post.valid_from ? date(post.valid_from) : "…", until: post.valid_until ? date(post.valid_until) : "…" })}</p>
}

function TargetMemo({ post }: { post: Post }) {
  const company = post.progress?.company
  const mine = post.progress?.mine
  const percent = Math.min(100, company?.percent ?? 0)
  return (
    <div className="rounded-xl border-2 border-ab-danger/30 bg-ab-danger/5 p-3 text-center">
      <p className="flex items-center justify-center gap-1.5 text-xs font-extrabold uppercase tracking-[0.2em] text-ab-danger"><Target className="h-4 w-4" /> {t("Target sales")}</p>
      <p className="text-3xl font-black text-ab-danger">{pesoShort(post.target_amount)}</p>
      <Period post={post} />
      {company && (
        <div className="mt-3 text-left">
          <div className="flex justify-between text-xs font-semibold"><span>{t("Recorded so far")}: {pesoShort(company.sales)}</span><span>{company.percent ?? 0}%</span></div>
          <div className="mt-1 h-2.5 overflow-hidden rounded-full bg-ab-hover" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-label={t("Progress toward the target")}>
            <div className="h-full rounded-full bg-ab-danger" style={{ width: `${percent}%` }} />
          </div>
          <p className="mt-1 text-[11px] text-ab-faint">{t("{n} reservations and sales on record (TCP), cancelled ones excluded.", { n: company.deals })}</p>
        </div>
      )}
      {mine && <p className="mt-2 text-xs font-semibold">{t("Your sales in this period: {amount} ({n} deals)", { amount: peso(mine.sales), n: mine.deals })}</p>}
    </div>
  )
}

function IncentiveMemo({ post }: { post: Post }) {
  const mine = post.progress?.mine
  const leaders = post.progress?.leaders
  return (
    <div className="space-y-3">
      <Period post={post} />
      {post.reward_amount && (
        <div className="rounded-xl border-2 border-ab-warning/50 bg-ab-warning/10 p-3 text-center">
          <p className="text-xs font-extrabold uppercase tracking-[0.2em]">{t("Seller's incentive per sale")}</p>
          <p className="text-3xl font-black">{peso(post.reward_amount)}</p>
          {mine && <p className="text-xs font-semibold">{t("You: {n} qualifying deals · {amount}", { n: mine.deals, amount: peso(mine.reward_total ?? 0) })}</p>}
        </div>
      )}
      {post.tiers && post.tiers.length > 0 && (
        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          {post.tiers.map((tier) => {
            const reached = mine?.reached && post.tiers!.findIndex((x) => x.label === mine.reached) >= post.tiers!.indexOf(tier)
            return (
              <li key={tier.label} className={`rounded-xl border p-2.5 text-center ${reached ? "border-ab-success bg-ab-success/10" : "border-ab-border bg-ab-card-2"}`}>
                <p className="text-base font-black uppercase">{tier.label}</p>
                <p className="text-[11px] font-bold uppercase text-ab-muted">{t("Minimum sales")}</p>
                <p className="text-sm font-extrabold">{pesoShort(tier.minimum_sales)}</p>
                {tier.reward && <p className="mt-1 text-[11px] text-ab-muted">{tier.reward}</p>}
                {reached && <p className="mt-1 text-[11px] font-bold text-ab-success">{t("Reached")}</p>}
              </li>
            )
          })}
        </ul>
      )}
      {mine && post.tiers && post.tiers.length > 0 && (
        <p className="rounded-xl bg-ab-card-2 px-3 py-2 text-xs">
          <Trophy className="mr-1 inline h-3.5 w-3.5 text-ab-warning" />
          {t("Your sales: {amount}.", { amount: peso(mine.sales) })}{" "}
          {mine.next ? t("{missing} more to reach {label}.", { missing: pesoShort(mine.next.missing), label: mine.next.label }) : t("You reached the top tier!")}
        </p>
      )}
      {leaders && leaders.length > 0 && (
        <table className="w-full text-left text-xs">
          <caption className="mb-1 text-left text-[11px] font-bold uppercase tracking-wide text-ab-faint">{t("Leading sellers this period")}</caption>
          <thead><tr className="text-ab-faint"><th className="py-1">{t("Seller")}</th><th className="text-right">{t("Sales")}</th><th className="text-right">{post.reward_amount ? t("Incentive") : t("Tier reached")}</th></tr></thead>
          <tbody>
            {leaders.map((row) => (
              <tr key={row.agent_id} className="border-t border-ab-border">
                <td className="py-1 font-semibold">{row.name}</td>
                <td className="text-right">{pesoShort(row.sales)}</td>
                <td className="text-right">{post.reward_amount ? peso(row.reward_total ?? 0) : row.reached ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

/** Like the memo on the whiteboard: date, buyer, agent, project, TCP. */
function SalesNotice({ sale }: { sale: Sale }) {
  const rows: [string, ReactNode][] = [["B", sale.buyer], ["A", sale.agent], ["P", sale.project], ["TCP", peso(sale.tcp)]]
  return (
    <div className="rounded-xl border border-ab-border bg-white p-3 font-mono text-sm text-[#111719] shadow-inner">
      <p className="font-bold">{date(sale.date)}</p>
      {rows.map(([key, value]) => <p key={key}><span className="inline-block w-10 font-bold">{key} –</span>{value ?? "—"}</p>)}
    </div>
  )
}

// ---- New / edit post (Administrator) -----------------------------------------

const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"
type SaleOption = Sale & { transaction_id: string }
type PartnerOption = { id: number; name: string; partner_type: string | null }

function PostForm({ post, board, onClose, onSaved }: { post: Post | null; board: "ANNOUNCEMENT" | "MEMO"; onClose: () => void; onSaved: () => void }) {
  const { api } = useStaffAuth()
  const toast = useToast()
  const branches = useBranchOptions()
  const picker = useRef<HTMLInputElement | null>(null)
  const loadOptions = useCallback(() => Promise.all([api<SaleOption[]>("/bulletin/sales-options"), api<PartnerOption[]>("/partners")]), [api])
  const options = useApiData(loadOptions, "bulletin-options")
  const [sales, partners] = options.data ?? [[], []]
  const [form, setForm] = useState({
    board: post?.board ?? board, category: post?.category ?? (board === "MEMO" ? "TARGET" : "MEETING"),
    title: post?.title ?? "", body: post?.body ?? "", event_at: post?.event_at?.slice(0, 16) ?? "",
    valid_from: post?.valid_from ?? "", valid_until: post?.valid_until ?? "",
    target_amount: post?.target_amount ? String(post.target_amount) : "", reward_amount: post?.reward_amount ? String(post.reward_amount) : "",
    branch_id: post?.branch_id ? String(post.branch_id) : "", partner_id: post?.partner_id ? String(post.partner_id) : "",
    transaction_id: post?.transaction_id ?? "", pinned: post?.pinned ?? false, archived: post?.archived ?? false,
  })
  const [tiers, setTiers] = useState<{ label: string; minimum_sales: string; reward: string }[]>(
    post?.tiers?.map((tier) => ({ label: tier.label, minimum_sales: String(tier.minimum_sales), reward: tier.reward ?? "" })) ?? [])
  const [image, setImage] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [deleting, setDeleting] = useState(false)
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }))
  const category = form.category
  const developerOptions = useMemo(() => partners.filter((p) => (p.partner_type ?? "").toUpperCase() === "DEVELOPER"), [partners])
  const amount = (value: string) => (value.trim() ? value.replace(/,/g, "").trim() : null)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError("")
    if (!form.title.trim()) return setError(t("Enter a title."))
    const cleanTiers = tiers.filter((tier) => tier.label.trim() || tier.minimum_sales.trim())
    if (cleanTiers.some((tier) => !tier.label.trim() || !(Number(amount(tier.minimum_sales)) > 0))) return setError(t("Each tier needs a name and a minimum sales amount."))
    const body = {
      board: form.board, category, title: form.title.trim(), body: form.body.trim() || null,
      event_at: category === "MEETING" && form.event_at ? form.event_at : null,
      valid_from: form.valid_from || null, valid_until: form.valid_until || null,
      target_amount: category === "TARGET" ? amount(form.target_amount) : null,
      reward_amount: category === "INCENTIVE" ? amount(form.reward_amount) : null,
      tiers: category === "INCENTIVE" && cleanTiers.length ? cleanTiers.map((tier) => ({ label: tier.label.trim(), minimum_sales: amount(tier.minimum_sales), reward: tier.reward.trim() || null })) : null,
      branch_id: form.branch_id ? Number(form.branch_id) : null, partner_id: form.partner_id ? Number(form.partner_id) : null,
      transaction_id: category === "SALES_NOTICE" ? form.transaction_id || null : null,
      pinned: form.pinned, archived: form.archived,
    }
    setBusy(true)
    try {
      const saved = await api<Post>(post ? `/bulletin/${post.id}` : "/bulletin", { method: post ? "PUT" : "POST", body: JSON.stringify(body) })
      if (image) {
        const data = new FormData()
        data.append("file", image)
        await api(`/bulletin/${saved.id}/image`, { method: "PUT", body: data })
      }
      toast(t(post ? "Post updated." : "Posted. Everyone has been notified."))
      onSaved()
    } catch (saveError) {
      setError(t((saveError as Error).message))
      setBusy(false)
    }
  }

  const remove = async () => {
    if (!post) return
    try {
      await api(`/bulletin/${post.id}`, { method: "DELETE" })
      toast(t("Post deleted."))
      onSaved()
    } catch (deleteError) {
      toast(t((deleteError as Error).message), "error")
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={t(post ? "Edit post" : "New post")}>
      <button type="button" aria-label={t("Cancel")} className="absolute inset-0 bg-black/55" onClick={onClose} />
      <form onSubmit={submit} noValidate className="ab-pop relative flex max-h-[94dvh] w-full max-w-2xl flex-col rounded-t-2xl border border-ab-border bg-ab-card shadow-2xl sm:rounded-2xl">
        <header className="flex items-center justify-between border-b border-ab-border px-5 py-4">
          <h2 className="text-lg font-bold">{t(post ? "Edit post" : "New post")}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close")} className="rounded-lg p-2 text-ab-muted hover:bg-ab-hover"><X className="h-4 w-4" /></button>
        </header>
        <div className="grid flex-1 gap-3 overflow-y-auto p-5 sm:grid-cols-2">
          <label className="block text-sm font-medium">{t("Board")}
            <select className={field} value={form.board} onChange={(e) => { const next = e.target.value as "ANNOUNCEMENT" | "MEMO"; setForm((f) => ({ ...f, board: next, category: CATEGORIES[next][0] })) }}>
              <option value="ANNOUNCEMENT">{t("Announcement")}</option>
              <option value="MEMO">{t("Memo")}</option>
            </select>
          </label>
          <label className="block text-sm font-medium">{t("Kind")}
            <select className={field} value={category} onChange={(e) => set("category", e.target.value)}>
              {CATEGORIES[form.board].map((c) => <option key={c} value={c}>{t(CATEGORY_LABELS[c])}</option>)}
            </select>
          </label>
          <label className="block text-sm font-medium sm:col-span-2">{t("Title *")}
            <input className={field} value={form.title} maxLength={200} onChange={(e) => set("title", e.target.value)}
              placeholder={t({ MEETING: "e.g. Monthly sales meeting", UPDATE: "e.g. New price list from Metrotowne", PROJECT: "e.g. Newtowne Dasmariñas Tower 1 rising soon", GENERAL: "e.g. Office closed on Monday", TARGET: "e.g. Target sales 2026", INCENTIVE: "e.g. 2026 travel incentives", SALES_NOTICE: "e.g. New reservation – Quezon City" }[category] ?? "")} />
          </label>
          {category === "MEETING" && <label className="block text-sm font-medium">{t("When *")}<input type="datetime-local" className={field} value={form.event_at} onChange={(e) => set("event_at", e.target.value)} /></label>}
          {category === "TARGET" && <label className="block text-sm font-medium">{t("Target sales (₱) *")}<input className={field} inputMode="decimal" value={form.target_amount} onChange={(e) => set("target_amount", e.target.value)} placeholder="1500000000" /></label>}
          {category === "INCENTIVE" && <label className="block text-sm font-medium">{t("Incentive per sale (₱)")}<input className={field} inputMode="decimal" value={form.reward_amount} onChange={(e) => set("reward_amount", e.target.value)} placeholder="22500" /></label>}
          {category === "SALES_NOTICE" && (
            <label className="block text-sm font-medium sm:col-span-2">{t("Recorded reservation or sale *")}
              <select className={field} value={form.transaction_id} onChange={(e) => set("transaction_id", e.target.value)}>
                <option value="">{t(options.loading && !options.data ? "Loading…" : "Choose")}</option>
                {sales.map((s) => <option key={s.transaction_id} value={s.transaction_id}>{date(s.date)} · {s.buyer} · {s.agent} · {s.project} · {peso(s.tcp)}</option>)}
              </select>
            </label>
          )}
          {(category === "TARGET" || category === "INCENTIVE" || category === "UPDATE" || category === "PROJECT" || category === "GENERAL") && (
            <>
              <label className="block text-sm font-medium">{t("Valid from")}<input type="date" className={field} value={form.valid_from} onChange={(e) => set("valid_from", e.target.value)} /></label>
              <label className="block text-sm font-medium">{t("Valid until")}<input type="date" className={field} value={form.valid_until} onChange={(e) => set("valid_until", e.target.value)} /></label>
            </>
          )}
          {category === "INCENTIVE" && (
            <fieldset className="space-y-2 rounded-xl border border-ab-border p-3 sm:col-span-2">
              <legend className="px-1 text-sm font-semibold">{t("Reward tiers (e.g. trips by minimum sales)")}</legend>
              {tiers.map((tier, index) => (
                <div key={index} className="grid grid-cols-[1fr_1fr_1.4fr_auto] gap-2">
                  <input aria-label={t("Reward")} className={field} value={tier.label} placeholder={t("e.g. Bohol")} onChange={(e) => setTiers((all) => all.map((x, i) => (i === index ? { ...x, label: e.target.value } : x)))} />
                  <input aria-label={t("Minimum sales")} className={field} inputMode="decimal" value={tier.minimum_sales} placeholder="75000000" onChange={(e) => setTiers((all) => all.map((x, i) => (i === index ? { ...x, minimum_sales: e.target.value } : x)))} />
                  <input aria-label={t("Details")} className={field} value={tier.reward} placeholder={t("e.g. 3 days 2 nights, for 2")} onChange={(e) => setTiers((all) => all.map((x, i) => (i === index ? { ...x, reward: e.target.value } : x)))} />
                  <button type="button" onClick={() => setTiers((all) => all.filter((_, i) => i !== index))} aria-label={t("Remove tier")} className="mt-1 rounded-lg p-2 text-ab-danger hover:bg-ab-hover"><Trash2 className="h-4 w-4" /></button>
                </div>
              ))}
              <Button onClick={() => setTiers((all) => [...all, { label: "", minimum_sales: "", reward: "" }])}><Plus className="h-4 w-4" /> {t("Add tier")}</Button>
            </fieldset>
          )}
          {(category === "TARGET" || category === "INCENTIVE" || category === "SALES_NOTICE" || category === "MEETING") && (
            <label className="block text-sm font-medium">{t("Team / Cluster or location")}
              <select className={field} value={form.branch_id} onChange={(e) => set("branch_id", e.target.value)}>
                <option value="">{t("Whole company")}</option>
                {branches.filter((b) => b.is_active || String(b.id) === form.branch_id).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </label>
          )}
          {(category === "PROJECT" || category === "INCENTIVE" || category === "UPDATE") && (
            <label className="block text-sm font-medium">{t("Developer")}
              <select className={field} value={form.partner_id} onChange={(e) => set("partner_id", e.target.value)}>
                <option value="">{t("Not set")}</option>
                {developerOptions.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
          )}
          <label className="block text-sm font-medium sm:col-span-2">{t("Message")}
            <textarea className={`${field} min-h-24`} value={form.body} maxLength={5000} onChange={(e) => set("body", e.target.value)} />
          </label>
          <div className="sm:col-span-2">
            <input ref={picker} type="file" accept=".png,.jpg,.jpeg,.webp" className="sr-only" aria-label={t("Flyer or poster")} onChange={(e) => setImage(e.target.files?.[0] ?? null)} />
            <Button onClick={() => picker.current?.click()}><ImagePlus className="h-4 w-4" /> {t(image ? "Change image" : post?.has_image ? "Replace flyer / poster" : "Add a flyer / poster")}</Button>
            {image && <span className="ml-2 text-xs text-ab-muted">{image.name}</span>}
          </div>
          <div className="flex flex-wrap gap-4 text-sm sm:col-span-2">
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.pinned} onChange={(e) => set("pinned", e.target.checked)} className="h-4 w-4 accent-[var(--color-ab-accent)]" /><Pin className="h-4 w-4" /> {t("Pin to the top")}</label>
            {post && <label className="flex items-center gap-2"><input type="checkbox" checked={form.archived} onChange={(e) => set("archived", e.target.checked)} className="h-4 w-4 accent-[var(--color-ab-accent)]" /><Archive className="h-4 w-4" /> {t("Archive (hide from the board)")}</label>}
          </div>
          {category === "TARGET" || category === "INCENTIVE" ? (
            <p className="text-xs text-ab-faint sm:col-span-2">{t("Progress is computed from recorded reservations and sales (TCP) in the period. Sellers see the target and their own figures only.")}</p>
          ) : null}
        </div>
        {error && <p role="alert" className="mx-5 mb-2 rounded-lg border border-ab-danger/40 bg-ab-danger/10 px-3 py-2 text-sm text-ab-danger">{error}</p>}
        <footer className="flex items-center justify-between gap-2 border-t border-ab-border px-5 py-3">
          {post ? <Button variant="danger" onClick={() => setDeleting(true)} disabled={busy}><Trash2 className="h-4 w-4" /> {t("Delete")}</Button> : <span />}
          <span className="flex gap-2">
            <Button onClick={onClose} disabled={busy}>{t("Cancel")}</Button>
            <Button type="submit" variant="primary" disabled={busy}>{busy && <LoaderCircle className="h-4 w-4 animate-spin" />} {t(post ? "Save" : "Post")}</Button>
          </span>
        </footer>
      </form>
      {deleting && <Confirm title="Delete post?" message={t("Delete “{title}”? Use Archive instead to keep it on record.", { title: post?.title ?? "" })} confirmLabel="Delete" onConfirm={() => void remove()} onCancel={() => setDeleting(false)} />}
    </div>
  )
}

