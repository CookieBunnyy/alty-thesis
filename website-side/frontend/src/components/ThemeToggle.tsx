import { Moon, Sun } from "lucide-react"

type Props = { theme: "dark" | "light"; onToggle: () => void; overlay?: boolean }

export function ThemeToggle({ theme, onToggle, overlay = false }: Props) {
  const next = theme === "dark" ? "light" : "dark"
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border transition ${
        overlay
          ? "border-white/30 bg-white/10 text-white hover:bg-white/20"
          : "border-ab-border-strong bg-ab-card-2 text-ab-text hover:bg-ab-hover"
      }`}
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  )
}
