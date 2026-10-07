// Staff session context (provider in staffAuth.tsx).
import { createContext, useContext } from "react"

export interface StaffUser {
  id: number
  username: string
  full_name: string
  role: string
  /** Page keys this role may open (same list the desktop uses). */
  permissions: string[]
  branch_id: number | null
  is_active: boolean
  last_login_at: string | null
  /** The agent record this account belongs to (agent accounts), if linked. */
  agent_id?: string | null
  /** Changes when the profile photo changes; null without a photo. */
  photo_version?: number | null
}

export type StaffAuthValue = {
  token: string | null
  user: StaffUser | null
  isReady: boolean
  signIn: (username: string, password: string, remember: boolean) => Promise<void>
  signOut: () => void
  /** GET/POST to /api/v1/<path> as the signed-in staff user. */
  api: <T>(path: string, init?: RequestInit) => Promise<T>
  /** A file from /api/v1/<path> (downloads, previews, photos), with the staff token. */
  apiBlob: (path: string) => Promise<Blob>
  can: (page: string) => boolean
  /** Re-read the signed-in account (e.g. after changing your own photo). */
  reloadUser: () => Promise<void>
}

/** Set when a session ended on its own, so the sign-in page can say why. */
export const EXPIRED_KEY = "alty-staff-session-expired"

export const StaffAuthContext = createContext<StaffAuthValue | null>(null)

export function useStaffAuth(): StaffAuthValue {
  const value = useContext(StaffAuthContext)
  if (!value) throw new Error("useStaffAuth must be used inside <StaffAuthProvider>")
  return value
}
