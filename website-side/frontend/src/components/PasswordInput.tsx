// A password field with a show / hide button, so people can check what they
// typed. Same props as <input>; the button never submits the form.
import { useState, type InputHTMLAttributes } from "react"
import { Eye, EyeOff } from "lucide-react"

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  showLabel?: string
  hideLabel?: string
}

export function PasswordInput({ className = "", showLabel = "Show password", hideLabel = "Hide password", ...props }: Props) {
  const [shown, setShown] = useState(false)
  return (
    <span className="relative block">
      <input {...props} type={shown ? "text" : "password"} className={`${className} pr-11`} />
      <button type="button" onClick={() => setShown((value) => !value)} aria-label={shown ? hideLabel : showLabel}
        aria-pressed={shown} title={shown ? hideLabel : showLabel}
        className="absolute right-1.5 top-1/2 mt-0.5 -translate-y-1/2 rounded-lg p-1.5 text-ab-muted hover:bg-ab-hover hover:text-ab-text focus-visible:outline-2 focus-visible:outline-ab-accent">
        {shown ? <EyeOff className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
      </button>
    </span>
  )
}
