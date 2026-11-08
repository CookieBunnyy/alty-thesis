// Branch choices for pickers (any staff role can read the list).
import { useCallback } from "react"
import { useStaffAuth } from "./staffContext"
import { useApiData } from "./useApiData"

export type BranchOption = { id: number; name: string; code: string | null; is_active: boolean }

export type SellerOption = { agent_id: string; full_name: string; status: string }

/** Active sellers for pickers (management pages). */
export function useSellerOptions() {
  const { api } = useStaffAuth()
  const load = useCallback(() => api<SellerOption[]>("/agents"), [api])
  return (useApiData(load, "seller-options").data ?? []).filter((s) => s.status === "ACTIVE")
}

/** Teams / clusters (stored as branches) for pickers. */
export function useBranchOptions() {
  const { api } = useStaffAuth()
  const load = useCallback(() => api<BranchOption[]>("/branches"), [api])
  return useApiData(load, "branch-options").data ?? []
}
