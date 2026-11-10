// Photos / scans of the recruitment form an applicant filled in.

export type ApplicantFormFile = {
  id: number; file_name: string; mime_type: string; size_bytes: number
  uploaded_by: string | null; uploaded_at: string; url: string
}

export const FORM_ACCEPT = ".png,.jpg,.jpeg,.webp,.pdf"

/** Upload each page; returns the names of the files that failed. */
export async function uploadForms(api: <T>(path: string, init?: RequestInit) => Promise<T>, applicantId: number, files: File[]) {
  const failed: string[] = []
  for (const file of files) {
    const data = new FormData()
    data.append("file", file)
    try {
      await api(`/recruitment/applicants/${applicantId}/forms`, { method: "POST", body: data })
    } catch {
      failed.push(file.name)
    }
  }
  return failed
}
