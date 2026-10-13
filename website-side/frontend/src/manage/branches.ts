// Branch choices for pickers (any staff role can read the list).
import { useCallback } from "react"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"

export type BranchOption = { id: number; name: string; code: string | null; is_active: boolean }

export function useBranchOptions() {
  const { api } = useStaffAuth()
  const load = useCallback(() => api<BranchOption[]>("/branches"), [api])
  return useApiData(load, "branch-options").data ?? []
}
