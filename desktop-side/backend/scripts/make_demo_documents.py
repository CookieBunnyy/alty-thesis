"""Write the sample documents for the live walkthrough as PDFs, laid out like
the real papers (docs/demo-documents): the buyer's information sheet, a
valid ID photocopy, a certificate of employment (proof of income), the
reservation agreement, official receipts, a letter of guarantee, the deed of
absolute sale, Abellar's cash / check (commission) voucher and a filled-in
recruitment form. Then, for listing a new property (ABR-26-0901): the owner's
real estate listing agreement and that property's information sheet.

They describe the property kept AVAILABLE by scripts/seed_demo_flow.py
(ABR-26-0101, Lumina Tanza, Blk 7 Lot 5, handled by Andrea Villanueva) and a
new buyer, Carlo M. Mendoza. Upload them in order as the Filing Manager (see
the README written next to them).

    pip install reportlab            # only needed to run this script
    python scripts/make_demo_documents.py                   # dated today
    python scripts/make_demo_documents.py --date 2026-11-20 # dated for the presentation day

Everything in them is fictitious and every page is marked SAMPLE. Each
detail the system reads is printed once, as "Label" then its value, so the
pages read like real forms and still process.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from scripts.seed_demo_flow import DEMO, PROJECTS  # noqa: E402

OUT = BACKEND.parents[1] / "docs" / "demo-documents"
INK = colors.HexColor("#1f2a44")      # handwriting: blue-black ballpen
GREEN = colors.HexColor("#3f5f00")
RED = colors.HexColor("#c0262d")
GREY = colors.HexColor("#6b6b6b")
LIGHT = colors.HexColor("#e9e9e9")

PROJECT = PROJECTS[DEMO["project"]]
DEVELOPER, PROJECT_NAME, ADDRESS = PROJECT[0], PROJECT[1], PROJECT[2]
MODEL, TCP, DP_PERCENT, MONTHLY = PROJECT[6], PROJECT[7], PROJECT[8], PROJECT[9]
LOT_AREA, FLOOR_AREA = PROJECT[10], PROJECT[11]
FEE, EQUITY_MONTHS = PROJECT[16], PROJECT[17]
TITLE = f"{PROJECT_NAME} - {MODEL}, Blk {DEMO['block']} Lot {DEMO['lot']}"
DOWN = TCP * DP_PERCENT // 100
NET_EQUITY = DOWN - FEE
MONTHLY_EQUITY = round(NET_EQUITY / EQUITY_MONTHS, 2)
LOAN = TCP - DOWN
RATE = 5
COMMISSION = TCP * RATE // 100
WITHHOLDING = round(COMMISSION * 0.05, 2)       # 5% expanded withholding tax on the agent's commission
NET_COMMISSION = COMMISSION - WITHHOLDING
# Typed forms often spell "Dasmarinas" without the tilde; the standard PDF
# fonts here don't carry it reliably through text extraction.
BUYER = {key: value.replace("ñ", "n").replace("Ñ", "N") for key, value in DEMO["buyer"].items()}
ADDRESS = ADDRESS.replace("ñ", "n")
AGENT = "Andrea Villanueva"
LENDER = "Sample Housing Finance Corporation"    # fictitious lender
EMPLOYER = "Sample Tech Solutions Inc."          # fictitious employer
BROKER_ADDRESS = "Blk 2 Lot 1, Sample Business Park, Salitran II, Dasmarinas City, Cavite"

# A handwriting-like font when Windows has one; otherwise an oblique.
HAND = "Helvetica-Oblique"
for candidate in ("C:/Windows/Fonts/segoepr.ttf", "C:/Windows/Fonts/comic.ttf"):
    if Path(candidate).exists():
        pdfmetrics.registerFont(TTFont("Hand", candidate))
        HAND = "Hand"
        break


def peso(value: float) -> str:
    return f"PHP {value:,.2f}"


def long_date(day: date) -> str:
    return f"{day:%B} {day.day}, {day.year}"


ONES = ["", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", "TEN", "ELEVEN", "TWELVE",
        "THIRTEEN", "FOURTEEN", "FIFTEEN", "SIXTEEN", "SEVENTEEN", "EIGHTEEN", "NINETEEN"]
TENS = ["", "", "TWENTY", "THIRTY", "FORTY", "FIFTY", "SIXTY", "SEVENTY", "EIGHTY", "NINETY"]


def words(n: int) -> str:
    """1850000 -> ONE MILLION EIGHT HUNDRED FIFTY THOUSAND."""
    def below_thousand(x: int) -> str:
        parts = []
        if x >= 100:
            parts.append(f"{ONES[x // 100]} HUNDRED")
            x %= 100
        if x >= 20:
            parts.append(TENS[x // 10] + (f"-{ONES[x % 10]}" if x % 10 else ""))
        elif x:
            parts.append(ONES[x])
        return " ".join(parts)
    out = []
    for value, name in ((1_000_000, "MILLION"), (1_000, "THOUSAND"), (1, "")):
        if n >= value:
            out.append(f"{below_thousand(n // value)} {name}".strip())
            n %= value
    return " ".join(out) or "ZERO"


def sample_marks(c: canvas.Canvas, width: float, height: float) -> None:
    """Footer note and a faint diagonal SAMPLE (drawn last on each page)."""
    c.saveState()
    c.setFont("Helvetica", 7)
    c.setFillColor(GREY)
    c.drawCentredString(width / 2, 14, "SAMPLE DOCUMENT FOR THESIS DEMONSTRATION ONLY - NOT A VALID RECORD")
    c.setFillColor(colors.Color(0.85, 0.1, 0.1, alpha=0.08))
    c.setFont("Helvetica-Bold", 90)
    c.translate(width / 2, height / 2)
    c.rotate(35)
    c.drawCentredString(0, 0, "SAMPLE")
    c.restoreState()


def letterhead(c: canvas.Canvas, x: float, y: float, width: float, *, centred: bool = True, size: float = 18) -> float:
    """ABELLAR REALTY / REAL ESTATE BROKER / address lines. Returns the y below it."""
    draw = (lambda text, yy: c.drawCentredString(x + width / 2, yy, text)) if centred else (lambda text, yy: c.drawString(x, yy, text))
    c.setFillColor(GREEN)
    c.setFont("Times-Bold", size)
    draw("ABELLAR REALTY", y)
    c.setFont("Times-Roman", size * 0.6)
    draw("REAL ESTATE BROKER", y - size * 0.75)
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 7)
    draw(BROKER_ADDRESS, y - size * 1.25)
    draw("Tel. No. (046) 000-0000  |  Broker's License No. SAMPLE-0000  |  TIN 000-000-000-000 (sample)", y - size * 1.25 - 9)
    return y - size * 1.25 - 22


def hand(c: canvas.Canvas, x: float, y: float, text: str, size: float = 11) -> None:
    c.setFillColor(INK)
    c.setFont(HAND, size)
    c.drawString(x, y, text)
    c.setFillColor(colors.black)


def field(c: canvas.Canvas, x: float, y: float, width: float, label: str, value: str, *, size: float = 10.5) -> None:
    """A form field: small printed label above a line, the entry written on it."""
    c.setFont("Helvetica", 6.8)
    c.setFillColor(GREY)
    c.drawString(x, y + 13, label)
    hand(c, x + 2, y + 2.5, value, size)
    c.setStrokeColor(colors.HexColor("#9a9a9a"))
    c.setLineWidth(0.5)
    c.line(x, y, x + width, y)


def section(c: canvas.Canvas, x: float, y: float, width: float, title: str) -> None:
    c.setFillColor(LIGHT)
    c.rect(x, y - 3, width, 13, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 4, y + 0.5, title)


# ---- documents ---------------------------------------------------------------------------

def buyers_information_sheet(day: date) -> str:
    name = "01-buyers-information-sheet.pdf"
    c = canvas.Canvas(str(OUT / name), pagesize=A4)
    w, h = A4
    left, right = 18 * mm, w - 18 * mm
    y = letterhead(c, left, h - 22 * mm, right - left)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(w / 2, y - 4, "BUYER'S INFORMATION SHEET")
    c.setFont("Helvetica", 8)
    c.drawCentredString(w / 2, y - 16, f"{PROJECT_NAME} by {DEVELOPER}  -  please print legibly")
    y -= 44
    half = (right - left - 12) / 2
    section(c, left, y, right - left, "I. BUYER")
    y -= 30
    field(c, left, y, half, "Client ID", BUYER["client_id"])
    field(c, left + half + 12, y, half, "Full Name", BUYER["name"])
    y -= 32
    field(c, left, y, half, "Date of Birth", "June 2, 1991")
    field(c, left + half + 12, y, half, "Civil Status", BUYER["civil_status"])
    y -= 32
    field(c, left, y, right - left, "Address", BUYER["address"])
    y -= 32
    field(c, left, y, half, "Contact Number", BUYER["phone"])
    field(c, left + half + 12, y, half, "Email Address", BUYER["email"])
    y -= 32
    field(c, left, y, half, "Preferred Contact", "Mobile")
    field(c, left + half + 12, y, half, "Purpose of Purchase", "Residential")
    y -= 36
    section(c, left, y, right - left, "II. EMPLOYMENT / SOURCE OF FUNDS")
    y -= 30
    field(c, left, y, half, "Occupation", BUYER["occupation"])
    field(c, left + half + 12, y, half, "Employer / Business", EMPLOYER)
    y -= 32
    field(c, left, y, half, "Gross Monthly Income", "48,000.00")
    field(c, left + half + 12, y, half, "Years Employed", "7")
    y -= 36
    section(c, left, y, right - left, "III. PROPERTY APPLIED FOR")
    y -= 30
    field(c, left, y, half, "Listing ID", DEMO["code"])
    field(c, left + half + 12, y, half, "Agent Name", AGENT)
    y -= 32
    field(c, left, y, right - left, "Property Title", TITLE)
    y -= 32
    field(c, left, y, half, "Mode of Financing", "Pag-IBIG Housing Loan")
    field(c, left + half + 12, y, half, "Equity Terms", f"{EQUITY_MONTHS} months")
    y -= 40
    c.setFont("Helvetica", 7.5)
    for line in ("I certify that the information above is true and correct, and I allow Abellar Realty and the developer",
                 "to process it for the reservation and purchase of the property, in line with the Data Privacy Act of 2012."):
        c.drawString(left, y, line)
        y -= 10
    y -= 34
    hand(c, left + 20, y + 4, BUYER["name"], 13)
    c.line(left, y, left + 70 * mm, y)
    c.setFont("Helvetica", 7)
    c.drawString(left, y - 9, "Signature over printed name of buyer")
    hand(c, right - 55 * mm, y + 4, long_date(day), 11)
    c.line(right - 60 * mm, y, right, y)
    c.setFont("Helvetica", 7)
    c.drawString(right - 60 * mm, y - 9, "Signed on")
    sample_marks(c, w, h)
    c.showPage()
    c.save()
    return name


def valid_id_photocopy(day: date) -> str:
    name = "02-buyers-document-valid-id.pdf"
    c = canvas.Canvas(str(OUT / name), pagesize=A4)
    w, h = A4
    left = 22 * mm
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(GREEN)
    c.drawString(left, h - 20 * mm, "ABELLAR REALTY - BUYER'S DOCUMENT (FILE COPY)")
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(left, h - 30 * mm, "PHOTOCOPY OF VALID ID")
    c.setFont("Helvetica", 9)
    c.drawString(left, h - 40 * mm, "Client ID")
    c.drawString(left + 32 * mm, h - 40 * mm, BUYER["client_id"])
    c.drawString(left, h - 46 * mm, "Full Name")
    c.drawString(left + 32 * mm, h - 46 * mm, BUYER["name"])
    # The photocopied card (a generic specimen; no government ID is imitated).
    x, y, cw, ch = left, h - 120 * mm, 95 * mm, 60 * mm
    c.setFillColor(colors.HexColor("#f1f1f1"))
    c.roundRect(x, y, cw, ch, 4 * mm, stroke=1, fill=1)
    c.setFillColor(colors.HexColor("#cfcfcf"))
    c.rect(x + 5 * mm, y + 12 * mm, 24 * mm, 30 * mm, stroke=0, fill=1)
    c.setFillColor(GREY)
    c.setFont("Helvetica", 6)
    c.drawCentredString(x + 17 * mm, y + 26 * mm, "PHOTO")
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 34 * mm, y + ch - 10 * mm, "SPECIMEN IDENTIFICATION CARD")
    rows = [("Surname", "MENDOZA"), ("Given Names", "CARLO M."), ("Birth Date", "1991-06-02"),
            ("ID Number", "SPECIMEN-0000-0000"), ("Valid Until", "2031-06-01")]
    yy = y + ch - 18 * mm
    for label, value in rows:
        c.setFont("Helvetica", 6)
        c.drawString(x + 34 * mm, yy, label)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x + 34 * mm, yy - 7, value)
        yy -= 15
    c.setFont("Helvetica", 7.5)
    c.drawString(left, y - 12 * mm, "Certified true copy of the original presented. Two (2) government-issued IDs are required.")
    hand(c, left, y - 26 * mm, BUYER["name"], 12)
    c.line(left, y - 28 * mm, left + 65 * mm, y - 28 * mm)
    c.drawString(left, y - 32 * mm, "Signature of buyer")
    c.setFont("Helvetica", 7)
    c.drawString(left, y - 44 * mm, "SPECIMEN ONLY: not a real identification document.")
    sample_marks(c, w, h)
    c.showPage()
    c.save()
    return name


def styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName="Times-Roman", fontSize=11, leading=15, alignment=TA_JUSTIFY)
    return {
        "body": base,
        "title": ParagraphStyle("title", parent=base, fontName="Times-Bold", fontSize=15, alignment=TA_CENTER, spaceAfter=10),
        "center": ParagraphStyle("center", parent=base, alignment=TA_CENTER),
        "small": ParagraphStyle("small", parent=base, fontSize=8.5, leading=11),
        "stamp": ParagraphStyle("stamp", parent=base, fontName="Helvetica-Bold", fontSize=8.5, textColor=GREEN),
        "item": ParagraphStyle("item", parent=base, leftIndent=18, firstLineIndent=-14, spaceAfter=5),
    }


def pages_with_marks(width: float, height: float):
    def draw(c, _doc):
        sample_marks(c, width, height)
    return draw


def table(rows: list[tuple[str, str]], widths=(55 * mm, 105 * mm)) -> Table:
    t = Table([[label, value] for label, value in rows], colWidths=widths)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9), ("FONT", (1, 0), (1, -1), "Helvetica", 9.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def signatures(pairs: list[tuple[str, str]], s) -> Table:
    cells = [[Paragraph(f"<br/><br/>______________________________<br/><b>{name}</b><br/>{role}", s["center"]) for name, role in pairs]]
    t = Table(cells, colWidths=[170 * mm / len(pairs)] * len(pairs))
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def proof_of_income(day: date) -> str:
    name = "03-buyers-document-proof-of-income.pdf"
    s = styles()
    doc = SimpleDocTemplate(str(OUT / name), pagesize=A4, leftMargin=25 * mm, rightMargin=25 * mm, topMargin=18 * mm)
    story = [
        Paragraph("ABELLAR REALTY - BUYER'S DOCUMENT (FILE COPY)", s["stamp"]),
        Spacer(1, 6),
        Paragraph(f"<b>{EMPLOYER.upper()}</b><br/>Unit 801, Sample Tower, Ortigas Center, Pasig City (fictitious)", s["center"]),
        Spacer(1, 16),
        Paragraph("CERTIFICATE OF EMPLOYMENT AND COMPENSATION", s["title"]),
        table([("Client ID", BUYER["client_id"]), ("Full Name", BUYER["name"]), ("Occupation", BUYER["occupation"])]),
        Spacer(1, 14),
        Paragraph(long_date(day), s["body"]),
        Spacer(1, 10),
        Paragraph("TO WHOM IT MAY CONCERN", s["body"]),
        Spacer(1, 8),
        Paragraph(f"This is to certify that <b>MR. {BUYER['name'].upper()}</b> has been employed by {EMPLOYER} as "
                  f"<b>{BUYER['occupation']}</b> on a regular, full-time basis since March 4, 2019 up to the present.", s["body"]),
        Spacer(1, 8),
        Paragraph("He receives a gross monthly compensation of <b>FORTY-EIGHT THOUSAND PESOS (PHP 48,000.00)</b>, "
                  "exclusive of allowances and the thirteenth month pay.", s["body"]),
        Spacer(1, 8),
        Paragraph("This certification is issued upon his request in support of his housing loan application and "
                  "for whatever legal purpose it may serve.", s["body"]),
        Spacer(1, 30),
        Paragraph("<b>MARIA L. SANTOS</b><br/>Human Resources Manager", s["body"]),
        Spacer(1, 20),
        Paragraph("Not valid without the company dry seal. Fictitious employer, for demonstration only.", s["small"]),
    ]
    doc.build(story, onFirstPage=pages_with_marks(*A4), onLaterPages=pages_with_marks(*A4))
    return name


def reservation_agreement(day: date) -> str:
    name = "04-reservation-agreement.pdf"
    s = styles()
    doc = SimpleDocTemplate(str(OUT / name), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm)
    terms = [
        f"The total contract price (TCP) of the Reserved Property is <b>{words(TCP)} PESOS (PHP {TCP:,.2f})</b>.",
        "The Reservation Fee is absolutely <b>NON-REFUNDABLE</b>; provided, however, that if I decide to purchase the "
        "Reserved Property, the Reservation Fee shall be applied as payment of an equivalent portion of the TCP.",
        "I have thirty (30) calendar days from the date of this Agreement (the Reservation Period) within which to "
        "complete the documentary requirements and to signify in writing my intention to purchase.",
        f"I shall pay the down payment of {DP_PERCENT}% of the TCP (PHP {DOWN:,.2f}), less the Reservation Fee, in "
        f"{EQUITY_MONTHS} equal monthly installments of PHP {MONTHLY_EQUITY:,.2f}, starting one month after this date.",
        f"The balance of PHP {LOAN:,.2f} shall be paid through my Pag-IBIG housing loan upon loan takeout. The "
        f"estimated monthly amortization is PHP {MONTHLY:,.2f}, subject to the lender's approval.",
        "I agree to issue and deliver postdated checks covering the monthly equity, if so required.",
        "I shall submit the Buyer's Information Sheet, two (2) valid IDs and proof of income within fifteen (15) days. "
        "Falsified or misrepresented documents shall cause the automatic cancellation of this Agreement.",
        f"Only payments acknowledged by official receipts of {DEVELOPER} or of Abellar Realty, its accredited broker, "
        "shall be valid.",
    ]
    story = [
        Paragraph(f"<font color='#3f5f00'><b>ABELLAR REALTY</b></font> - Real Estate Broker, accredited by {DEVELOPER}", s["center"]),
        Paragraph(BROKER_ADDRESS, ParagraphStyle("addr", parent=s["center"], fontSize=8)),
        Spacer(1, 10),
        Paragraph("RESERVATION AGREEMENT", s["title"]),
        Paragraph(f"DATE OF RESERVATION: <u><b>{long_date(day)}</b></u>", s["body"]),
        Spacer(1, 8),
        Paragraph(f"I, <b><u>{BUYER['name'].upper()}</u></b>, {BUYER['civil_status'].lower()}, of legal age, Filipino, "
                  f"with postal address at <b><u>{BUYER['address'].upper()}</u></b>, hereby make a firm offer to reserve and "
                  f"purchase the following property of <b><u>{DEVELOPER.upper()}</u></b> located at "
                  f"<b><u>{ADDRESS.upper()}</u></b>.", s["body"]),
        Spacer(1, 8),
        table([("Reservation ID", DEMO["reservation_id"]), ("Listing ID", DEMO["code"]), ("Property Title", TITLE),
               ("Lot Area", f"{LOT_AREA} sqm"), ("Floor Area", f"{FLOOR_AREA} sqm")]),
        Spacer(1, 4),
        Paragraph('(The above-described property shall hereinafter be referred to as the "Reserved Property".)', s["small"]),
        Spacer(1, 8),
        Paragraph(f"As and by way of Reservation Fee, I am remitting herewith the sum of <b><u>{words(FEE)} PESOS ONLY</u></b> "
                  f"(PHP {FEE:,.2f}) in ( / ) Cash  (   ) Check No. ________  Bank ____________.", s["body"]),
        Spacer(1, 8),
        table([("Client ID", BUYER["client_id"]), ("Buyer Name", BUYER["name"]), ("Email", BUYER["email"]),
               ("Contact Number", BUYER["phone"]), ("Agent Name", AGENT), ("Reservation Amount", peso(FEE))]),
        Spacer(1, 10),
        Paragraph("I acknowledge that -", s["body"]),
        Spacer(1, 4),
        *[Paragraph(f"{index}.&nbsp;&nbsp;{text}", s["item"]) for index, text in enumerate(terms, start=1)],
        Spacer(1, 16),
        KeepTogether([
            Paragraph("CONFORME", ParagraphStyle("conf", parent=s["body"], fontName="Times-Bold")),
            signatures([(BUYER["name"].upper(), "Buyer"), (AGENT.upper(), "Abellar Realty seller"),
                        ("AUTHORIZED SIGNATORY", DEVELOPER)], s),
        ]),
    ]
    doc.build(story, onFirstPage=pages_with_marks(*A4), onLaterPages=pages_with_marks(*A4))
    return name


def official_receipt(day: date, name: str, number: str, amount: float, purpose: str, how: str) -> str:
    size = landscape((A4[0] * 0.62, A4[1]))
    c = canvas.Canvas(str(OUT / name), pagesize=size)
    w, h = size
    # Right side first, so the title is among the first lines read.
    x0 = 82 * mm
    y = letterhead(c, x0, h - 14 * mm, w - x0 - 10 * mm, size=15)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x0, y - 8, "OFFICIAL RECEIPT")
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(w - 52 * mm, y - 8, f"No. {number}")
    c.setFillColor(colors.black)
    y -= 30
    c.setFont("Helvetica", 9.5)
    c.drawString(w - 70 * mm, y, "Date")
    hand(c, w - 58 * mm, y, long_date(day), 10.5)
    c.line(w - 58 * mm, y - 2, w - 10 * mm, y - 2)
    y -= 20
    entries = [("Received from", BUYER["name"]), ("with TIN", "N/A"), ("and address at", BUYER["address"]),
               ("the sum of", f"{words(int(amount))} PESOS" + (f" AND {round(amount % 1 * 100):02d}/100" if amount % 1 else " ONLY")),
               ("in partial/full payment for", purpose)]
    for label, value in entries:
        c.setFont("Helvetica", 9.5)
        c.drawString(x0, y, label)
        start = x0 + c.stringWidth(label, "Helvetica", 9.5) + 6
        hand(c, start, y, value, 10 if len(value) < 70 else 8.5)
        c.line(start, y - 2, w - 10 * mm, y - 2)
        y -= 19
    c.setFont("Helvetica", 9.5)
    c.drawString(x0, y, "BY")
    hand(c, x0 + 20, y, "R. Lacson", 11)
    c.line(x0 + 18, y - 2, x0 + 80 * mm, y - 2)
    c.setFont("Helvetica", 7.5)
    c.drawString(x0 + 18, y - 11, "Cashier / Authorized Representative")
    c.setFont("Helvetica", 6.5)
    c.drawString(x0, 22, "BIR Authority to Print No. SAMPLE-0000  |  Printer's Accreditation No. SAMPLE-0000  |  50 Bklts (50x2) 0001-2500")
    # Left: in settlement of the following.
    rows = [("IN SETTLEMENT OF THE FOLLOWING", ""), ("Reservation ID", DEMO["reservation_id"]), ("Listing ID", DEMO["code"]),
            ("Total Sales", f"{amount:,.2f}"), ("Less: SC/PWD Discount", "-"), ("Less: Withholding Tax", "-"),
            ("Total Amount", f"{amount:,.2f}"), ("FORM OF PAYMENT", ""), ("Cash", "( / )" if how == "Cash" else "(   )"),
            ("Check / Bank Transfer", "( / ) " + how if how != "Cash" else "(   )")]
    t = Table([list(row) for row in rows], colWidths=[40 * mm, 27 * mm])
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 7.5), ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                           ("SPAN", (0, 0), (1, 0)), ("SPAN", (0, 7), (1, 7)), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7),
                           ("FONT", (0, 7), (-1, 7), "Helvetica-Bold", 7), ("TEXTCOLOR", (1, 1), (1, -1), INK),
                           ("ALIGN", (0, 0), (-1, 0), "CENTER")]))
    t.wrapOn(c, 0, 0)
    t.drawOn(c, 10 * mm, h - 14 * mm - t._height)
    sample_marks(c, w, h)
    c.showPage()
    c.save()
    return name


def letter_of_guarantee(day: date) -> str:
    name = "07-letter-of-guarantee.pdf"
    s = styles()
    doc = SimpleDocTemplate(str(OUT / name), pagesize=A4, leftMargin=25 * mm, rightMargin=25 * mm, topMargin=16 * mm)
    story = [
        Paragraph("ABELLAR REALTY - BUYER'S DOCUMENT (FILE COPY)", s["stamp"]),
        Spacer(1, 4),
        Paragraph(f"<b>{LENDER.upper()}</b><br/>Housing Loan Department, Sample Avenue, Makati City (fictitious)", s["center"]),
        Spacer(1, 14),
        Paragraph("LETTER OF GUARANTEE", s["title"]),
        table([("Client ID", BUYER["client_id"]), ("Buyer Name", BUYER["name"]), ("Listing ID", DEMO["code"]),
               ("Approved Loan Amount", peso(LOAN)), ("LOG Number", "LOG-SAMPLE-2026-0101")]),
        Spacer(1, 12),
        Paragraph(long_date(day), s["body"]),
        Spacer(1, 10),
        Paragraph(f"RE&nbsp;&nbsp;&nbsp;&nbsp;LETTER OF GUARANTEE IN FAVOR OF {DEVELOPER.upper()}", s["body"]),
        Spacer(1, 8),
        Paragraph(f"TO&nbsp;&nbsp;&nbsp;&nbsp;<b>The Collection Department</b><br/>"
                  f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{DEVELOPER}<br/>"
                  f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{ADDRESS}", s["body"]),
        Spacer(1, 12),
        Paragraph("Gentlemen,", s["body"]),
        Spacer(1, 8),
        Paragraph(f"This letter will serve as your notification that the housing loan application of <b>{BUYER['name'].upper()}</b> "
                  f"for the purchase of <b>{TITLE}</b> has been approved in the amount of "
                  f"<b>{words(LOAN)} PESOS (PHP {LOAN:,.2f})</b>, payable in thirty (30) years.", s["body"]),
        Spacer(1, 8),
        Paragraph(f"{LENDER} guarantees the release of the loan proceeds directly to {DEVELOPER} within sixty (60) days "
                  "from the date of this letter, upon submission of the Deed of Absolute Sale, the transfer of the title "
                  f"in the name of the borrower with the mortgage annotated in favor of {LENDER}, and the other "
                  "post-approval requirements.", s["body"]),
        Spacer(1, 8),
        Paragraph("This guarantee is valid for ninety (90) days from its date and is subject to the terms of the "
                  "approved loan.", s["body"]),
        Spacer(1, 18),
        Paragraph("Sincerely,", s["body"]),
        Spacer(1, 30),
        Paragraph(f"<b>JOSE R. DELA PAZ</b><br/>Head, Housing Loan Department<br/>{LENDER}", s["body"]),
        Spacer(1, 16),
        Paragraph("Fictitious lender and letter, for demonstration only.", s["small"]),
    ]
    doc.build(story, onFirstPage=pages_with_marks(*A4), onLaterPages=pages_with_marks(*A4))
    return name


def deed_of_absolute_sale(day: date) -> str:
    name = "08-deed-of-absolute-sale.pdf"
    s = styles()
    doc = SimpleDocTemplate(str(OUT / name), pagesize=A4, leftMargin=25 * mm, rightMargin=25 * mm, topMargin=18 * mm)
    ordinal = {1: "st", 2: "nd", 3: "rd"}.get(day.day % 10 if day.day not in (11, 12, 13) else 0, "th")
    story = [
        Paragraph("<u>DEED OF ABSOLUTE SALE</u>", s["title"]),
        Spacer(1, 8),
        Paragraph("<b>KNOW ALL MEN BY THESE PRESENTS</b>", s["body"]),
        Spacer(1, 8),
        Paragraph("This DEED is made and entered into by and between", s["body"]),
        Spacer(1, 6),
        Paragraph(f"<b>{DEVELOPER.upper()}</b>, a corporation duly organized under Philippine law, with principal office at "
                  f"{ADDRESS}, represented herein by its authorized signatory, hereinafter referred to as the <b>VENDOR</b>;", s["body"]),
        Paragraph("- and -", s["center"]),
        Paragraph(f"<b>{BUYER['name'].upper()}</b>, of legal age, Filipino, married to <b>ANA R. MENDOZA</b>, and a resident of "
                  f"{BUYER['address']}, hereinafter referred to as the <b>VENDEE</b>.", s["body"]),
        Spacer(1, 8),
        Paragraph("<b>W I T N E S S E T H</b>", s["center"]),
        Spacer(1, 6),
        Paragraph(f"<b>WHEREAS</b>, the VENDOR is the absolute owner in fee simple of that certain house and lot situated in "
                  f"{ADDRESS}, Philippines, known as Lot {DEMO['lot']}, Block {DEMO['block']} of {PROJECT_NAME}, covered by "
                  "Transfer Certificate of Title No. T-000000 (sample) issued by the Registry of Deeds for the Province of "
                  f"Cavite, containing an area of EIGHTY-EIGHT ({LOT_AREA}) SQUARE METERS, more or less;", s["body"]),
        Spacer(1, 6),
        Paragraph("<b>WHEREAS</b>, the VENDEE has offered to buy and the VENDOR has agreed to sell the above-described "
                  "property for the price and under the terms and conditions set forth herein;", s["body"]),
        Spacer(1, 6),
        Paragraph(f"<b>NOW THEREFORE</b>, for and in consideration of the sum of <b>{words(TCP)} PESOS (PHP {TCP:,.2f})</b>, "
                  "Philippine currency, the receipt whereof is hereby acknowledged by the VENDOR to its entire satisfaction, "
                  "the VENDOR does hereby sell, transfer and convey in a manner absolute and irrevocable, in favor of the "
                  "VENDEE, his heirs and assigns, the above-described property;", s["body"]),
        Spacer(1, 6),
        Paragraph("That the VENDOR covenants that the property is free from all liens and encumbrances, that it has a "
                  "perfect right to convey the same, and that it will defend the title against the lawful claims of all "
                  "persons whomsoever;", s["body"]),
        Spacer(1, 6),
        Paragraph("That the VENDEE shall shoulder the expenses for the transfer of the title, documentary stamp tax and "
                  "registration fees, while the VENDOR shall shoulder the capital gains tax and the real estate taxes "
                  "accrued up to the date of this Deed.", s["body"]),
        Spacer(1, 10),
        Paragraph(f"<b>IN WITNESS WHEREOF</b>, the parties have hereunto set their hands this {day.day}{ordinal} day of "
                  f"{day:%B} {day.year} at Dasmarinas City, Philippines.", s["body"]),
        Spacer(1, 6),
        signatures([("AUTHORIZED SIGNATORY", f"{DEVELOPER} - VENDOR"), (BUYER["name"].upper(), "VENDEE")], s),
        Spacer(1, 8),
        Paragraph("With marital consent of", s["body"]),
        signatures([("ANA R. MENDOZA", "Wife")], s),
        Spacer(1, 8),
        Paragraph("SIGNED IN THE PRESENCE OF", s["body"]),
        signatures([("WITNESS", ""), ("WITNESS", "")], s),
        PageBreak(),
        Paragraph("<b>ACKNOWLEDGMENT</b>", s["center"]),
        Spacer(1, 8),
        Paragraph("REPUBLIC OF THE PHILIPPINES )<br/>CITY OF DASMARINAS&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;) S.S.", s["body"]),
        Spacer(1, 8),
        Paragraph(f"BEFORE ME, a Notary Public for and in the City of Dasmarinas, this {day.day}{ordinal} day of {day:%B} "
                  f"{day.year}, personally appeared the above-named parties, known to me and to me known to be the same persons "
                  "who executed the foregoing instrument, and they acknowledged to me that the same is their free and "
                  "voluntary act and deed.", s["body"]),
        Spacer(1, 8),
        Paragraph("This instrument, consisting of two (2) pages including this page, refers to a Deed of Absolute Sale "
                  "of real property.", s["body"]),
        Spacer(1, 8),
        Paragraph("WITNESS MY HAND AND SEAL on the date and place first above written.", s["body"]),
        Spacer(1, 24),
        Paragraph("<b>NOTARY PUBLIC (sample)</b><br/>Doc. No. ____<br/>Page No. ____<br/>Book No. ____<br/>"
                  f"Series of {day.year}", s["body"]),
        Spacer(1, 24),
        Paragraph("ANNEX A - TRANSACTION SUMMARY (Abellar Realty file copy)", ParagraphStyle("annex", parent=s["body"], fontName="Times-Bold")),
        Spacer(1, 4),
        table([("Transaction ID", DEMO["sale_id"]), ("Reservation ID", DEMO["reservation_id"]), ("Sale Date", long_date(day)),
               ("Client ID", BUYER["client_id"]), ("Buyer Name", BUYER["name"]), ("Listing ID", DEMO["code"]),
               ("Property Title", TITLE), ("Agent Name", AGENT), ("Sale Amount", peso(TCP))]),
    ]
    doc.build(story, onFirstPage=pages_with_marks(*A4), onLaterPages=pages_with_marks(*A4))
    return name


def commission_voucher(day: date) -> str:
    """Abellar's CASH / CHECK VOUCHER, as on the office's own pad."""
    name = "09-commission-voucher.pdf"
    size = (A4[0] * 0.78, A4[1] * 0.62)
    c = canvas.Canvas(str(OUT / name), pagesize=size)
    w, h = size
    left, right = 10 * mm, w - 10 * mm
    y = letterhead(c, left, h - 14 * mm, right - left, size=16)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(w / 2 - 10 * mm, y - 10, "CASH / CHECK VOUCHER")
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(right - 30 * mm, y - 10, "No. 47247")
    c.setFillColor(colors.black)
    y -= 34

    def line_field(x, yy, label, value, end):
        c.setFont("Helvetica", 9)
        c.drawString(x, yy, f"{label}:")
        start = x + c.stringWidth(f"{label}:", "Helvetica", 9) + 5
        hand(c, start, yy, value, 11)
        c.line(start, yy - 2, end, yy - 2)

    line_field(left, y, "Payee", AGENT, right - 62 * mm)
    line_field(right - 58 * mm, y, "Date", day.strftime("%m/%d/%Y"), right)
    y -= 18
    line_field(left, y, "Address", "Dasmarinas City, Cavite", right - 62 * mm)
    line_field(right - 58 * mm, y, "Tel. No.", "0917 555 0201", right)
    y -= 14
    # Particulars | Amount grid.
    top, bottom, split = y, y - 62 * mm, right - 58 * mm
    c.rect(left, bottom, right - left, top - bottom)
    c.line(split, top, split, bottom)
    c.line(left, top - 14, right, top - 14)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString((left + split) / 2, top - 10, "PARTICULARS:")
    hand(c, left + 4, top - 30, f"100% release of comm. - {PROJECT_NAME}", 10.5)
    hand(c, left + 4, top - 44, f"Blk {DEMO['block']} Lot {DEMO['lot']}, buyer {BUYER['name']}", 10.5)
    hand(c, left + 4, top - 58, f"{RATE}% of TCP, financing Pag-IBIG", 10.5)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString((split + right) / 2, top - 10, "AMOUNT")
    amounts = [("TCP", f"{TCP:,.2f}"), ("Commission", f"{COMMISSION:,.2f}"), ("Less 5% W/Tax", f"{WITHHOLDING:,.2f}"),
               ("Amount", f"{NET_COMMISSION:,.2f}")]
    yy = top - 30
    for label, value in amounts:
        c.setFont("Helvetica", 8)
        c.drawString(split + 4, yy, f"{label}:")
        hand(c, split + 4 + c.stringWidth(f"{label}:", "Helvetica", 8) + 4, yy, value, 10.5)
        yy -= 14
    y = bottom - 14
    c.setFont("Helvetica", 9)
    c.drawString(left, y, "PESOS:")
    hand(c, left + 36, y, f"{words(int(NET_COMMISSION))} PESOS & {round(NET_COMMISSION % 1 * 100):02d}/100", 8.5)
    c.line(left + 34, y - 2, right, y - 2)
    y -= 17
    line_field(left, y, "Mode of Payment", "ATM", left + 70 * mm)
    line_field(left + 74 * mm, y, "Bank Name", "BDO", right)
    y -= 17
    line_field(left, y, "Check No.", "N/A", left + 70 * mm)
    line_field(left + 74 * mm, y, "Received By", AGENT, right)
    y -= 26
    for label, x in (("Prepared By", left), ("Certified Correct", left + 52 * mm), ("Approved By", left + 104 * mm)):
        c.line(x, y, x + 45 * mm, y)
        c.setFont("Helvetica", 7)
        c.drawString(x, y - 8, label)
    hand(c, left + 4, y + 3, "R. A. Lacson", 10)
    sample_marks(c, w, h)
    c.showPage()
    c.save()
    return name


def recruitment_form(day: date) -> str:
    name = "10-recruitment-form-patricia-lim.pdf"
    c = canvas.Canvas(str(OUT / name), pagesize=A4)
    w, h = A4
    left, right = 18 * mm, w - 18 * mm
    y = letterhead(c, left, h - 22 * mm, right - left)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(w / 2, y - 4, "SELLER / AGENT RECRUITMENT FORM")
    y -= 40
    half = (right - left - 12) / 2
    section(c, left, y, right - left, "APPLICANT")
    y -= 30
    field(c, left, y, right - left, "Full name", "Patricia Anne Lim", size=12)
    y -= 32
    field(c, left, y, half, "Date of birth", "March 14, 1996")
    field(c, left + half + 12, y, half, "Mobile number", "0917 555 0177")
    y -= 32
    field(c, left, y, right - left, "Home address", "Blk 4 Lot 9, Brgy. Salitran II, Dasmarinas, Cavite")
    y -= 32
    field(c, left, y, right - left, "Email address", "patricia.lim@example.com")
    y -= 38
    section(c, left, y, right - left, "RECRUITMENT")
    y -= 30
    field(c, left, y, half, "Recruited by", AGENT)
    field(c, left + half + 12, y, half, "Team / cluster", "Team Pinyas")
    y -= 32
    field(c, left, y, half, "Real estate experience", "1 year (property consultant)")
    field(c, left + half + 12, y, half, "PRC license no.", "None yet")
    y -= 32
    field(c, left, y, half, "How you heard about us", "Referral")
    y -= 40
    section(c, left, y, right - left, "DECLARATION")
    y -= 22
    c.rect(left, y - 2, 9, 9)
    hand(c, left + 1, y - 1, "x", 11)
    c.setFont("Helvetica", 8.5)
    c.drawString(left + 16, y, "I declare that I am not actively bound to another real estate broker, and that the details")
    c.drawString(left + 16, y - 11, "above are true and correct.")
    y -= 52
    hand(c, left + 10, y + 4, "Patricia A. Lim", 14)
    c.line(left, y, left + 70 * mm, y)
    c.setFont("Helvetica", 7)
    c.drawString(left, y - 9, "Signature of applicant")
    hand(c, right - 55 * mm, y + 4, long_date(day), 11)
    c.line(right - 60 * mm, y, right, y)
    c.setFont("Helvetica", 7)
    c.drawString(right - 60 * mm, y - 9, "Signed on")
    y -= 40
    c.setStrokeColor(colors.HexColor("#9a9a9a"))
    c.rect(left, y - 30, right - left, 34)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(left + 4, y - 6, "FOR OFFICE USE")
    c.setFont("Helvetica", 7.5)
    c.drawString(left + 4, y - 18, "Received by the Filing Manager. To be recorded in ALTY > Recruitment.")
    sample_marks(c, w, h)
    c.showPage()
    c.save()
    return name


# ---------------------------------------------------------------------------
# Listing a new property: the owner's listing agreement, then the property
# information sheet for the same property (ABR-26-0901). Both are new: the
# agreement lists the property, the sheet fills in every detail.
# ---------------------------------------------------------------------------

LISTED_PROJECT = PROJECTS[1]   # Amaia Scapes General Trias (developer: Amaia)
LISTED = {
    "code": "ABR-26-0901",
    "title": f"{LISTED_PROJECT[1]} - {LISTED_PROJECT[6]}, Blk 3 Lot 12",
    "address": f"Blk 3 Lot 12, {LISTED_PROJECT[1]}, {LISTED_PROJECT[2]}",
    "developer": LISTED_PROJECT[0], "development": LISTED_PROJECT[1], "model": LISTED_PROJECT[6],
    "category": LISTED_PROJECT[5], "price": 3_600_000, "down_percent": 10, "monthly": 25_900,
    "lot": LISTED_PROJECT[10], "floor": LISTED_PROJECT[11], "beds": LISTED_PROJECT[12], "baths": LISTED_PROJECT[13],
    "readiness": "RFO (ready for occupancy)", "financing": "Bank, Pag-IBIG, Cash",
    "fee": 20_000, "equity_months": 12, "team": LISTED_PROJECT[18],
    "lat": LISTED_PROJECT[3], "lng": LISTED_PROJECT[4],
    "owner": "Ricardo T. Bautista", "owner_address": "Unit 5B, Sample Residences, Kalayaan Ave., Makati City",
    "owner_phone": "0918 555 0377", "broker": "Juan Paolo Reyes",
    "tct": "T-123-2019004512", "tax_dec": "TD-GT-2025-08812",
}


def listing_agreement(day: date) -> str:
    """Laid out like the Real Estate Listing Agreement reference (sections 1-29),
    with every blank filled in and Philippine terms (pesos, province, TCT)."""
    name = "11-listing-agreement.pdf"
    s = styles()
    doc = SimpleDocTemplate(str(OUT / name), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm,
                            bottomMargin=22 * mm)
    start = day
    end = date(day.year + (1 if day.month > 6 else 0), (day.month + 5) % 12 + 1, min(day.day, 28))
    head = ParagraphStyle("head", parent=s["body"], fontName="Times-Bold", spaceBefore=8, spaceAfter=4)
    box = "<font name='ZapfDingbats'>&#110;</font>"   # filled square: the option chosen
    empty = "<font name='ZapfDingbats'>&#111;</font>"  # empty square

    def clause(number: int, title: str, text: str) -> list:
        return [Paragraph(f"{number}. {title.upper()}", head), Paragraph(text, s["body"])]

    def choice(chosen: bool, label: str, text: str) -> Paragraph:
        return Paragraph(f"{box if chosen else empty}&nbsp; <b>{label}</b>: {text}", s["item"])

    permissions = ["Advertise the property", "Use the street address", "Publish online and in print",
                   "For Sale sign", "Photos and videos"]
    story = [
        Paragraph(f"<font color='#3f5f00'><b>ABELLAR REALTY</b></font> - Real Estate Broker", s["center"]),
        Paragraph(BROKER_ADDRESS, ParagraphStyle("addr", parent=s["center"], fontSize=8)),
        Spacer(1, 8),
        Paragraph("REAL ESTATE LISTING AGREEMENT", s["title"]),
        Paragraph(f'This Real Estate Listing Agreement (the "Agreement") is made on {long_date(day)} between the '
                  'Seller (the property owner) and the Agency below. If the Broker cannot fulfil their duties, '
                  'another broker of the Agency may be appointed for the rest of the Listing Period.', s["body"]),
        Paragraph("1. THE PARTIES", head),
        table([("Agreement Date", day.strftime("%m/%d/%Y")), ("Seller Name", LISTED["owner"]),
               ("Seller Address", LISTED["owner_address"]), ("Seller Contact Number", LISTED["owner_phone"]),
               ("Broker Name", LISTED["broker"]), ("Agency", "Abellar Realty"),
               ("Agency Address", "Salitran II, Dasmarinas City, Cavite")], widths=(50 * mm, 120 * mm)),
        Paragraph("2. REAL PROPERTY", head),
        table([("Listing ID", LISTED["code"]), ("Property Title", LISTED["title"]),
               ("Property Address", LISTED["address"].replace("ñ", "n")),
               ("TCT No.", LISTED["tct"]), ("Tax Declaration No.", LISTED["tax_dec"]),
               ("Fixtures Excluded", "Wall-mounted TV and the dining chandelier"),
               ("Personal Property Included", "Two split-type aircon units and kitchen cabinets")],
              widths=(50 * mm, 120 * mm)),
        Paragraph('The real property, the included personal property and fixtures are hereinafter the "Property".',
                  s["small"]),
        Paragraph("3. RIGHTS TO SELL", head),
        choice(True, "Exclusive Right-to-Sell", "the sole and exclusive right to sell the Property during the Listing "
               "Period; all inquiries are referred to the Agency, and the Commission is due whoever sells it."),
        choice(False, "Exclusive Agency", "the Agency is the exclusive agent, but the Seller may sell the Property "
               "directly with no commission due."),
        choice(False, "Open Listing", "a non-exclusive right; the Seller may sell directly or list with other agencies."),
        table([("Rights to Sell", "Exclusive Right-to-Sell")], widths=(50 * mm, 120 * mm)),
        Paragraph("4. PURCHASE PRICE", head),
        Paragraph(f"The Seller authorizes the Agency to sell the Property for <b>{words(LISTED['price'])} PESOS</b>.",
                  s["body"]),
        table([("Listing Price", peso(LISTED["price"]))], widths=(50 * mm, 120 * mm)),
        Paragraph("5. PERIOD OF AGREEMENT", head),
        Paragraph("The Commission is also due if, within the Extension Period after the Listing Period ends, the "
                  "Property is sold to anyone the Agency negotiated with, unless it is listed in good faith with "
                  "another agency.", s["body"]),
        table([("Listing Start", start.strftime("%m/%d/%Y")), ("Listing End", end.strftime("%m/%d/%Y")),
               ("Extension Period", "90 days")], widths=(50 * mm, 120 * mm)),
        Paragraph("6. COMMISSION", head),
        choice(True, "Percentage (%) Commission", "a percentage of the sales price in the purchase contract."),
        choice(False, "Fixed Payment Commission", "a fixed amount."),
        Paragraph("The Commission is due and payable at closing. Commission rates are not fixed by law and are "
                  "negotiable between the Seller and the Broker. If the Agency finds a tenant, the leasing "
                  "commission below applies to the total rent for the lease term.", s["body"]),
        table([("Commission Type", "Percentage"), ("Commission Rate", "5%"), ("Leasing Commission", "8%"),
               ("Deed Type", "Deed of Absolute Sale")], widths=(50 * mm, 120 * mm)),
        Paragraph("7. COOPERATION WITH OTHER BROKERS", head),
        Paragraph("The Agency may engage other licensed brokers to help market the Property and share its "
                  "Commission. A cooperating broker whose buyer completes the purchase receives the commission "
                  "offered below.", s["body"]),
        table([("Cooperating Commission", "2%")], widths=(50 * mm, 120 * mm)),
        Paragraph("8. DISCLOSED DUAL AGENCY", head),
        choice(True, "ALLOW", "Disclosed Dual Agency"),
        choice(False, "NOT ALLOW", "Disclosed Dual Agency"),
        table([("Disclosed Dual Agency", "Allow")], widths=(50 * mm, 120 * mm)),
        Paragraph("9. MARKETING THE PROPERTY", head),
        Paragraph("The Seller grants the Agency these permissions (initialed by the Seller): "
                  + "; ".join(f"<b>RTB</b> {p}" for p in permissions) + ".", s["body"]),
        table([("Marketing Permissions", "; ".join(permissions))], widths=(50 * mm, 120 * mm)),
        *clause(10, "Agency disclosure", "The Agency cooperates with and shares compensation with other brokers "
                "acting for buyers."),
        *clause(11, "Non-refundable payments", "Non-refundable payments forfeited by a buyer who does not complete "
                "the purchase are shared equally between the Seller and the Agency, up to the Commission."),
        *clause(12, "Fair housing", "The Agency presents the Property to all prospective buyers without "
                "discrimination."),
        *clause(13, "Ownership", "The Seller warrants that they own the Property and may sell it."),
        *clause(14, "Seller acknowledgments", "The Seller knows of no recorded default, delinquency, insolvency or "
                "pending case affecting the Property, and will tell the Agency at once if one arises."),
        *clause(15, "Broker's duties", "The Broker will use all reasonable efforts to market the Property and "
                "obtain the best price for the Seller."),
        *clause(16, "Seller's duties", "The Seller will accommodate viewings and inspections and consider every "
                "offer in good faith. Only the Seller sets the selling price."),
        *clause(17, "Earnest money", "Buyers' deposits are held in trust and released only as the law and both "
                "parties allow."),
        *clause(18, "Insurance", "The Seller keeps the Property insured until it is sold."),
        *clause(19, "Dispute resolution", "Disputes are settled by arbitration, each party choosing one arbitrator "
                "and both choosing a third."),
        Paragraph("20. GOVERNING LAW", head),
        table([("Governing Law", "Republic of the Philippines")], widths=(50 * mm, 120 * mm)),
        Paragraph("21. ADDITIONAL TERMS AND CONDITIONS", head),
        table([("Additional Terms", "Viewings by appointment only, weekends 9 AM to 5 PM")], widths=(50 * mm, 120 * mm)),
        *clause(22, "Entire agreement", "This is the entire agreement between the Seller and the Agency. Both "
                "acknowledge receiving a signed copy."),
        Spacer(1, 14),
        KeepTogether([
            Paragraph(f"Signed on {long_date(day)} at Dasmarinas City, Cavite.", s["body"]),
            signatures([(LISTED["owner"].upper(), "Property owner"),
                        (LISTED["broker"].upper(), "Broker, Abellar Realty")], s),
        ]),
    ]

    def footer(c, _doc):
        c.saveState()
        c.setFont("Helvetica", 8)
        c.drawString(20 * mm, 12 * mm + 8, f"Seller's initials: RTB     Broker's initials: JPR     Page {c.getPageNumber()}")
        c.restoreState()
        sample_marks(c, *A4)

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return name


def property_information_sheet(day: date) -> str:
    """Every detail of the property listed in the agreement above."""
    name = "12-property-information-sheet.pdf"
    s = styles()
    doc = SimpleDocTemplate(str(OUT / name), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm)
    down = LISTED["price"] * LISTED["down_percent"] // 100
    widths = (55 * mm, 115 * mm)
    head = ParagraphStyle("head", parent=s["body"], fontName="Times-Bold", spaceBefore=8, spaceAfter=4)
    story = [
        Paragraph(f"<font color='#3f5f00'><b>ABELLAR REALTY</b></font> - Real Estate Broker", s["center"]),
        Paragraph(BROKER_ADDRESS, ParagraphStyle("addr", parent=s["center"], fontSize=8)),
        Spacer(1, 8),
        Paragraph("PROPERTY INFORMATION SHEET", s["title"]),
        Paragraph(f"Prepared {long_date(day)} from the listing agreement with {LISTED['owner']}.", s["center"]),
        Paragraph("PROPERTY", head),
        table([("Listing ID", LISTED["code"]), ("Property Title", LISTED["title"]), ("Category", LISTED["category"]),
               ("Property Status", "AVAILABLE"), ("Developer", LISTED["developer"]),
               ("Development", LISTED["development"]), ("Village", LISTED["development"]),
               ("Property Location", LISTED["address"].replace("ñ", "n")), ("Team / Cluster", LISTED["team"]),
               ("Latitude", f"{LISTED['lat']:.4f}"), ("Longitude", f"{LISTED['lng']:.4f}")], widths=widths),
        Paragraph("UNIT", head),
        table([("Layout Type", LISTED["model"]), ("Bedrooms", str(LISTED["beds"])), ("Bathrooms", str(LISTED["baths"])),
               ("Floor Area", f"{LISTED['floor']} sqm"), ("Lot Area", f"{LISTED['lot']} sqm"),
               ("Has Balcony", "No"), ("Has Kitchen", "Yes"), ("Has Backyard", "Yes"), ("Has Garage", "Yes"),
               ("Garage Spaces", "1")], widths=widths),
        Paragraph("PRICE AND TERMS", head),
        table([("Total Contract Price", peso(LISTED["price"])), ("Down Payment", peso(down)),
               ("Monthly Amortization", peso(LISTED["monthly"])), ("Reservation Fee", peso(LISTED["fee"])),
               ("Equity Terms", f"{LISTED['equity_months']} months"), ("Turnover Status", LISTED["readiness"]),
               ("Financing Options", LISTED["financing"])], widths=widths),
        Paragraph("AMENITIES AND SURROUNDINGS", head),
        table([("Amenities", ", ".join(LISTED_PROJECT[19])),
               ("Other Amenities", "Pocket garden; Bike lanes"),
               ("Nearby Places", "SM City General Trias, Lyceum of the Philippines, General Trias Doctors Hospital"),
               ("Description", "Corner-lot single attached house, ready for occupancy, near CALAX")], widths=widths),
        Spacer(1, 16),
        signatures([(LISTED["broker"].upper(), "Broker, Abellar Realty"), (LISTED["owner"].upper(), "Property owner")], s),
    ]
    doc.build(story, onFirstPage=pages_with_marks(*A4), onLaterPages=pages_with_marks(*A4))
    return name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", help="the reservation / presentation date (YYYY-MM-DD); default today")
    args = parser.parse_args()
    day = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in list(OUT.glob("*.docx")) + list(OUT.glob("*.jpg")):
        try:
            old.unlink()   # earlier formats of the same documents
        except PermissionError:
            print(f"Close {old.name} (open in another program) and delete it; it is replaced by the PDF.")
    files = [
        buyers_information_sheet(day), valid_id_photocopy(day), proof_of_income(day), reservation_agreement(day),
        official_receipt(day, "05-official-receipt-reservation-fee.pdf", "0501", FEE,
                         f"Reservation fee - {PROJECT_NAME} Blk {DEMO['block']} Lot {DEMO['lot']}", "Cash"),
        official_receipt(day, "06-official-receipt-equity-1.pdf", "0502", MONTHLY_EQUITY,
                         f"Equity 1 of {EQUITY_MONTHS} (advance) - {PROJECT_NAME} Blk {DEMO['block']} Lot {DEMO['lot']}", "BDO"),
        letter_of_guarantee(day), deed_of_absolute_sale(day), commission_voucher(day), recruitment_form(day),
        listing_agreement(day), property_information_sheet(day),
    ]
    for file in files:
        print(f"docs/demo-documents/{file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
