// Amenities: pick common ones from a dropdown (shown as removable chips);
// "Other…" opens a text field for anything not in the list.
import { useId, useState } from "react"
import { X } from "lucide-react"
import { AMENITY_GROUPS, isCondo } from "./amenityOptions"
import { t } from "./i18n"

const OTHER = "__other__"
const field = "mt-1 block w-full rounded-xl border border-ab-border bg-ab-input px-3 py-2 text-sm focus:border-ab-accent focus:outline-none"

export function AmenitiesPicker({ value, onChange, other, onOtherChange, category = "", hint }: {
  value: string[]; onChange: (amenities: string[]) => void
  other: string; onOtherChange: (text: string) => void
  /** House-and-lot or condominium amenities first. */
  category?: string
  hint?: string
}) {
  const id = useId()
  const [showOther, setShowOther] = useState(Boolean(other.trim()))
  const condo = isCondo(category)
  const groups = [...AMENITY_GROUPS].sort((a, b) => rank(a.for, condo) - rank(b.for, condo))
  const chosen = new Set(value.map((v) => v.toLowerCase()))

  const pick = (name: string) => {
    if (name === OTHER) setShowOther(true)
    else if (name && !chosen.has(name.toLowerCase())) onChange([...value, name])
  }

  return (
    <div className="sm:col-span-2">
      <label htmlFor={id} className="block text-sm font-medium">{t("Amenities")}</label>
      {value.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1.5" aria-label={t("Chosen amenities")}>
          {value.map((name) => (
            <li key={name} className="inline-flex items-center gap-1 rounded-full border border-ab-accent/40 bg-ab-accent-soft py-1 pl-2.5 pr-1 text-xs font-medium">
              {t(name)}
              <button type="button" onClick={() => onChange(value.filter((v) => v !== name))} aria-label={t("Remove {name}", { name: t(name) })}
                className="rounded-full p-0.5 text-ab-muted hover:bg-ab-hover hover:text-ab-text">
                <X className="h-3 w-3" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {/* Resets to the prompt after each pick, so it works as "add another". */}
      <select id={id} className={field} value="" onChange={(e) => pick(e.target.value)}>
        <option value="">{t(value.length ? "Add another amenity…" : "Choose an amenity…")}</option>
        {groups.map((group) => (
          <optgroup key={group.label} label={t(group.label)}>
            {group.items.filter((name) => !chosen.has(name.toLowerCase())).map((name) => <option key={name} value={name}>{t(name)}</option>)}
          </optgroup>
        ))}
        <option value={OTHER}>{t("Other (type it in)…")}</option>
      </select>
      {hint && <p className="mt-1 text-xs text-ab-faint">{hint}</p>}
      {showOther && (
        <label className="mt-3 block text-sm font-medium">
          {t("Other amenities")}
          <input className={field} value={other} onChange={(e) => onOtherChange(e.target.value)} autoFocus={!other}
            placeholder={t("e.g. Koi pond, Rooftop garden, Pet park")} />
          <span className="mt-1 block text-xs font-normal text-ab-faint">{t("Separate several with commas.")}</span>
        </label>
      )}
    </div>
  )
}

function rank(group: "house" | "condo" | "both", condo: boolean) {
  if (group === "both") return 1
  return (group === "condo") === condo ? 0 : 2
}
