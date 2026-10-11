// "Export PDF" for the Management System's tables. The PDF library is loaded
// only when someone exports (it is large), and the table is read exactly as
// shown: current search, filters and sort.
import { t } from "./i18n"

export type PdfTable = {
  /** Shown as the document title, e.g. "Transactions". */
  title: string
  /** Extra line under the title (e.g. the filters in use). */
  note?: string
  columns: string[]
  rows: string[][]
  /** Who exported it (shown in the header). */
  author?: string
}

// jsPDF's built-in fonts can't draw "₱" and a few other characters.
const pdfText = (value: string) =>
  value.replace(/₱\s?/g, "PHP ").replace(/→/g, "->").replace(/[“”]/g, '"').replace(/[‘’]/g, "'").replace(/\s+/g, " ").trim()

const stamp = () => {
  const now = new Date()
  const date = now.toLocaleDateString("en-CA", { timeZone: "Asia/Manila" })
  const time = now.toLocaleTimeString("en-US", { timeZone: "Asia/Manila", hour: "numeric", minute: "2-digit" })
  return { date, label: `${now.toLocaleDateString("en-US", { timeZone: "Asia/Manila", month: "short", day: "numeric", year: "numeric" })} · ${time}` }
}

export async function exportPdf({ title, note, columns, rows, author }: PdfTable): Promise<void> {
  const [{ jsPDF }, { default: autoTable }] = await Promise.all([import("jspdf"), import("jspdf-autotable")])
  const doc = new jsPDF({ orientation: columns.length > 5 ? "landscape" : "portrait", unit: "pt", format: "a4" })
  const width = doc.internal.pageSize.getWidth()
  const { date, label } = stamp()

  doc.setFont("helvetica", "bold").setFontSize(9).setTextColor(94, 126, 0)
  doc.text("ALTY · ABELLAR REALTY", 40, 40)
  doc.setFontSize(18).setTextColor(17, 22, 10)
  doc.text(pdfText(t(title)), 40, 62)
  doc.setFont("helvetica", "normal").setFontSize(9).setTextColor(110, 116, 104)
  const meta = [`${t("Generated")} ${label}`, `${rows.length} ${t(rows.length === 1 ? "row" : "rows")}`, author ? `${t("By")} ${author}` : ""]
    .filter(Boolean).join("   ·   ")
  doc.text(pdfText(meta), 40, 78)
  let top = 92
  if (note) {
    doc.text(doc.splitTextToSize(pdfText(note), width - 80), 40, 92)
    top = 106
  }

  autoTable(doc, {
    startY: top,
    head: [columns.map((c) => pdfText(t(c)))],
    body: rows.map((row) => row.map(pdfText)),
    margin: { left: 40, right: 40, bottom: 40 },
    styles: { font: "helvetica", fontSize: 8, cellPadding: 5, overflow: "linebreak", textColor: [33, 37, 30], lineColor: [226, 230, 220], lineWidth: 0.5 },
    headStyles: { fillColor: [94, 126, 0], textColor: [255, 255, 255], fontStyle: "bold" },
    alternateRowStyles: { fillColor: [246, 248, 242] },
    didDrawPage: () => {
      const height = doc.internal.pageSize.getHeight()
      doc.setFontSize(8).setTextColor(140, 146, 134)
      doc.text(`${t("Page")} ${doc.getCurrentPageInfo().pageNumber}`, width - 40, height - 20, { align: "right" })
    },
  })

  const slug = t(title).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "table"
  doc.save(`alty-${slug}-${date}.pdf`)
}

/** Read a rendered DataTable (<table>) as text: what the user sees, without
 *  avatars, icons and buttons. Works while the table is hidden (phone view). */
export function readTable(table: HTMLTableElement): { columns: string[]; rows: string[][] } {
  const wrapper = table.parentElement as HTMLElement
  const hidden = wrapper && getComputedStyle(wrapper).display === "none"
  if (hidden) wrapper.style.display = "block" // measured synchronously; nothing is painted
  try {
    // Header labels sit inside the sort buttons, so headers keep their buttons;
    // in body cells, buttons are actions (call, edit…) and are left out.
    const text = (cell: Element, header = false) => {
      // A copy of the cell's content, off screen, so its line breaks can be read.
      const copy = document.createElement("div")
      copy.innerHTML = cell.innerHTML
      copy.querySelectorAll(`[data-pdf-skip], svg, img, [aria-hidden='true'], [role='tooltip']${header ? "" : ", button"}`).forEach((node) => node.remove())
      // Text as written: the table shows headers in capitals with CSS only.
      copy.querySelectorAll<HTMLElement>("*").forEach((node) => { node.style.textTransform = "none" })
      copy.style.cssText = "position:absolute;left:-99999px;top:0;width:600px"
      document.body.appendChild(copy)
      const value = (copy.innerText || copy.textContent || "").split("\n").map((part) => part.trim()).filter(Boolean).join(" · ")
      copy.remove()
      return value
    }
    const columns = [...table.querySelectorAll("thead th")].map((th) => text(th, true))
    const rows = [...table.querySelectorAll("tbody tr")].map((tr) => [...tr.querySelectorAll("td")].map((td) => text(td)))
    // Drop columns that hold nothing (e.g. a column of action buttons).
    const keep = columns.map((label, index) => Boolean(label) || rows.some((row) => row[index]))
    return {
      columns: columns.filter((_, index) => keep[index]),
      rows: rows.map((row) => row.filter((_, index) => keep[index])),
    }
  } finally {
    if (hidden) wrapper.style.display = ""
  }
}
