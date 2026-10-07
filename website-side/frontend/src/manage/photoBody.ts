/** multipart body for a profile photo upload. */
export function photoBody(file: File): FormData {
  const body = new FormData()
  body.append("file", file)
  return body
}
