import { useEffect, useState } from "react"
import { useStaffAuth } from "./staffContext"

/** An object URL for an authenticated API file (photo, PDF preview).
 *  Revoked when the component unmounts or the path changes. */
export function useBlobUrl(path: string | null) {
  const { apiBlob } = useStaffAuth()
  const [state, setState] = useState<{ url: string | null; error: string; type: string }>({ url: null, error: "", type: "" })
  useEffect(() => {
    if (!path) return
    let current = true
    let url: string | null = null
    apiBlob(path)
      .then((blob) => {
        if (!current) return
        url = URL.createObjectURL(blob)
        setState({ url, error: "", type: blob.type })
      })
      .catch((error: Error) => current && setState({ url: null, error: error.message, type: "" }))
    return () => {
      current = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [path, apiBlob])
  return state
}

/** Save an authenticated API file to the user's computer. */
export async function downloadBlob(apiBlob: (path: string) => Promise<Blob>, path: string, filename: string) {
  const blob = await apiBlob(path)
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
