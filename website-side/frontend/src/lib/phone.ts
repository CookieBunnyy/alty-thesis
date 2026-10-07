// Phone numbers for tel: / sms: links.

/** "0917-321-8844" -> "+639173218844" (Philippine numbers); others keep their digits. */
export function telNumber(phone: string): string {
  const plus = phone.trim().startsWith("+")
  const digits = phone.replace(/\D/g, "")
  if (plus) return `+${digits}`
  if (digits.length === 11 && digits.startsWith("09")) return `+63${digits.slice(1)}`
  if (digits.length === 12 && digits.startsWith("639")) return `+${digits}`
  if (digits.length === 10 && digits.startsWith("9")) return `+63${digits}`
  return digits
}
