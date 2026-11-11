"""Write the sample documents for the live walkthrough (docs/demo-documents):
the buyer's papers, the reservation agreement, official receipts, the
letter of guarantee, the deed of absolute sale, the commission voucher and
a filled-in recruitment form.

They describe the property kept AVAILABLE by scripts/seed_demo_flow.py
(ABR-26-0101, Lumina Tanza, Blk 7 Lot 5, handled by Andrea Villanueva) and a
new buyer, Carlo M. Mendoza. Upload them in order as the Filing Manager in the
Document Repository; the system reads each one (see the README it writes).

    python scripts/make_demo_documents.py                   # dated today
    python scripts/make_demo_documents.py --date 2026-11-20 # dated for the presentation day

All names, numbers and IDs are fictitious and marked SAMPLE.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from scripts.seed_demo_flow import DEMO, PROJECTS  # noqa: E402

OUT = BACKEND.parents[1] / "docs" / "demo-documents"
GREEN = RGBColor(0x4A, 0x6B, 0x00)
GREY = RGBColor(0x66, 0x66, 0x66)

PROJECT = PROJECTS[DEMO["project"]]
DEVELOPER, PROJECT_NAME, ADDRESS = PROJECT[0], PROJECT[1], PROJECT[2]
MODEL, TCP, DP_PERCENT, MONTHLY = PROJECT[6], PROJECT[7], PROJECT[8], PROJECT[9]
FEE, EQUITY_MONTHS = PROJECT[16], PROJECT[17]
TITLE = f"{PROJECT_NAME} - {MODEL}, Blk {DEMO['block']} Lot {DEMO['lot']}"
DOWN = TCP * DP_PERCENT // 100
NET_EQUITY = DOWN - FEE
MONTHLY_EQUITY = round(NET_EQUITY / EQUITY_MONTHS, 2)
LOAN = TCP - DOWN
RATE = 5
COMMISSION = TCP * RATE // 100
BUYER = DEMO["buyer"]
AGENT = "Andrea Villanueva"


def peso(value: float) -> str:
    return f"PHP {value:,.2f}"


def long_date(day: date) -> str:
    return f"{day:%B} {day.day}, {day.year}"


class Doc:
    """A one-document builder: letterhead, title, "Label: value" lines (what
    the system reads), prose paragraphs and signature lines."""

    def __init__(self, title: str, subtitle: str | None = None):
        self.doc = Document()
        style = self.doc.styles["Normal"]
        style.font.name, style.font.size = "Calibri", Pt(10.5)
        for section in self.doc.sections:
            section.left_margin = section.right_margin = Pt(60)
            section.top_margin = section.bottom_margin = Pt(48)
        head = self.doc.add_paragraph()
        run = head.add_run("ABELLAR REALTY")
        run.bold, run.font.size, run.font.color.rgb = True, Pt(16), GREEN
        line = self.doc.add_paragraph()
        line_run = line.add_run("Real estate brokerage · Dasmariñas, Cavite · SAMPLE DOCUMENT FOR DEMONSTRATION")
        line_run.font.size, line_run.font.color.rgb = Pt(8.5), GREY
        heading = self.doc.add_paragraph()
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        heading_run = heading.add_run(title.upper())
        heading_run.bold, heading_run.font.size = True, Pt(14)
        if subtitle:
            sub = self.doc.add_paragraph()
            sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
            sub_run = sub.add_run(subtitle)
            sub_run.italic, sub_run.font.size, sub_run.font.color.rgb = True, Pt(9), GREY

    def section(self, name: str) -> "Doc":
        paragraph = self.doc.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(8)
        run = paragraph.add_run(name.upper())
        run.bold, run.font.size, run.font.color.rgb = True, Pt(9.5), GREEN
        return self

    def fields(self, rows: list[tuple[str, str]]) -> "Doc":
        for label, value in rows:
            paragraph = self.doc.add_paragraph()
            paragraph.paragraph_format.space_after = Pt(1)
            label_run = paragraph.add_run(f"{label}: ")
            label_run.bold = True
            paragraph.add_run(value)
        return self

    def text(self, *paragraphs: str) -> "Doc":
        for body in paragraphs:
            assert ":" not in body, "prose must not contain colons (they read as fields)"
            paragraph = self.doc.add_paragraph(body)
            paragraph.paragraph_format.space_after = Pt(4)
        return self

    def signatures(self, *names: str) -> "Doc":
        self.doc.add_paragraph()
        for name in names:
            self.doc.add_paragraph("______________________________")
            signer = self.doc.add_paragraph(name)
            signer.paragraph_format.space_after = Pt(10)
        return self

    def save(self, name: str) -> Path:
        path = OUT / name
        self.doc.save(path)
        return path


def recruitment_form(day: date) -> Path:
    """A filled-in recruitment form, as a phone photo / scan would look."""
    from PIL import Image, ImageDraw, ImageFont

    def font(size: int, bold: bool = False):
        for name in (["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    def hand(size: int):
        for name in ("segoepr.ttf", "comic.ttf", "DejaVuSans-Oblique.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return font(size)

    image = Image.new("RGB", (1240, 1754), (252, 251, 247))
    draw = ImageDraw.Draw(image)
    ink, pen, line = (30, 30, 30), (20, 40, 140), (120, 120, 120)
    draw.text((70, 60), "ABELLAR REALTY", fill=(74, 107, 0), font=font(44, True))
    draw.text((70, 118), "Dasmariñas, Cavite  ·  SAMPLE FORM FOR DEMONSTRATION", fill=(110, 110, 110), font=font(20))
    draw.text((70, 175), "SELLER / AGENT RECRUITMENT FORM", fill=ink, font=font(34, True))
    rows = [
        ("Full name", "Patricia Anne Lim"), ("Date of birth", "March 14, 1996"),
        ("Home address", "Blk 4 Lot 9, Brgy. Salitran II, Dasmariñas, Cavite"),
        ("Mobile number", "0917 555 0177"), ("Email address", "patricia.lim@example.com"),
        ("Recruited by", "Andrea Villanueva"), ("Team / cluster", "Team Pinyas"),
        ("Real estate experience", "1 year (property consultant)"), ("PRC license no.", "None yet"),
        ("How you heard about us", "Referral"),
    ]
    y = 260
    for label, value in rows:
        draw.text((70, y), label, fill=ink, font=font(22, True))
        draw.line((400, y + 34, 1170, y + 34), fill=line, width=2)
        draw.text((410, y - 4), value, fill=pen, font=hand(30))
        y += 78
    y += 20
    draw.text((70, y), "DECLARATION", fill=ink, font=font(24, True))
    y += 46
    draw.rectangle((70, y, 100, y + 30), outline=ink, width=3)
    draw.line((76, y + 16, 86, y + 26), fill=pen, width=5)
    draw.line((86, y + 26, 98, y + 2), fill=pen, width=5)
    statement = ("I declare that I am not actively bound to another real estate broker, and that the details "
                 "above are true.")
    words, current, lines = statement.split(), "", []
    for word in words:
        if len(current) + len(word) > 70:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    lines.append(current)
    for index, text in enumerate(lines):
        draw.text((120, y + index * 32), text, fill=ink, font=font(22))
    y += 140
    draw.line((70, y + 60, 520, y + 60), fill=line, width=2)
    draw.text((90, y), "Patricia A. Lim", fill=pen, font=hand(40))
    draw.text((70, y + 70), "Signature of applicant", fill=ink, font=font(20))
    draw.line((700, y + 60, 1170, y + 60), fill=line, width=2)
    draw.text((720, y + 8), long_date(day), fill=pen, font=hand(32))
    draw.text((700, y + 70), "Date", fill=ink, font=font(20))
    y += 170
    draw.text((70, y), "FOR OFFICE USE", fill=ink, font=font(20, True))
    draw.rectangle((70, y + 36, 1170, y + 170), outline=line, width=2)
    draw.text((90, y + 56), "Received by the Filing Manager. To be recorded in ALTY > Recruitment.",
              fill=(110, 110, 110), font=font(20))
    # A slight tilt and shadow, like a phone photo of the paper.
    photo = Image.new("RGB", (1320, 1834), (205, 200, 190))
    photo.paste(image.rotate(-0.8, expand=False, fillcolor=(205, 200, 190)), (40, 40))
    path = OUT / "10-recruitment-form-patricia-lim.jpg"
    photo.save(path, quality=88)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", help="the reservation / presentation date (YYYY-MM-DD); default today")
    args = parser.parse_args()
    day = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    OUT.mkdir(parents=True, exist_ok=True)
    files = []

    files.append(Doc("Buyer's Information Sheet").section("Buyer").fields([
        ("Client ID", BUYER["client_id"]), ("Full Name", BUYER["name"]), ("Date of Birth", "June 2, 1991"),
        ("Civil Status", BUYER["civil_status"]), ("Address", BUYER["address"]),
        ("Contact Number", BUYER["phone"]), ("Email Address", BUYER["email"]), ("Occupation", BUYER["occupation"]),
        ("Preferred Contact", "Mobile"), ("Purpose of Purchase", "Residential"),
    ]).section("Property of interest").fields([
        ("Listing ID", DEMO["code"]), ("Property Title", TITLE), ("Agent Name", AGENT),
    ]).text("The buyer confirms that the information above is complete and correct, and allows Abellar Realty "
            "to process it for the reservation and purchase of the property.").signatures(
        f"{BUYER['name']} (Buyer)").save("01-buyers-information-sheet.docx"))

    files.append(Doc("Buyer's Document", "Valid ID (photocopy attached) - SPECIMEN").fields([
        ("Client ID", BUYER["client_id"]), ("Full Name", BUYER["name"]), ("ID Type", "Philippine Passport (specimen)"),
        ("ID Number", "SPECIMEN-0000000"), ("ID Expiry", "June 1, 2031"),
    ]).text("SPECIMEN ONLY. Not a real identification document. In an actual transaction the buyer's two "
            "government-issued IDs are photocopied here and signed.").save("02-buyers-document-valid-id.docx"))

    files.append(Doc("Buyer's Document", "Proof of income - Certificate of Employment and Compensation").fields([
        ("Client ID", BUYER["client_id"]), ("Full Name", BUYER["name"]), ("Occupation", BUYER["occupation"]),
        ("Employer", "Sample Tech Solutions Inc. (fictitious)"), ("Employment Status", "Regular, since 2019"),
        ("Gross Monthly Income", "PHP 48,000.00"),
    ]).text("This certifies that the employee named above is currently employed with the company and receives "
            "the monthly compensation stated. Issued upon the employee's request for a housing loan application."
            ).signatures("HR Manager, Sample Tech Solutions Inc.").save("03-buyers-document-proof-of-income.docx"))

    files.append(Doc("Reservation Agreement", f"{PROJECT_NAME} by {DEVELOPER}").section("Reservation").fields([
        ("Reservation ID", DEMO["reservation_id"]), ("Reservation Date", long_date(day)),
        ("Client ID", BUYER["client_id"]), ("Buyer Name", BUYER["name"]), ("Email", BUYER["email"]),
        ("Contact Number", BUYER["phone"]), ("Listing ID", DEMO["code"]), ("Property Title", TITLE),
        ("Property Address", ADDRESS), ("Agent Name", AGENT), ("Reservation Amount", peso(FEE)),
        ("Payment Method", "Cash"),
    ]).section("Sample computation").fields([
        ("Total Contract Price", peso(TCP)), ("Down Payment", f"{peso(DOWN)} ({DP_PERCENT}%)"),
        ("Net Equity", f"{peso(NET_EQUITY)} payable in {EQUITY_MONTHS} months of {peso(MONTHLY_EQUITY)}"),
        ("Payment Scheme", "Pag-IBIG Housing Loan for the balance"), ("Loanable Amount", peso(LOAN)),
        ("Estimated Monthly Amortization", peso(MONTHLY)),
    ]).section("Terms").text(
        "The reservation fee holds the unit for the buyer and is credited to the down payment. It is "
        "non-refundable and non-transferable.",
        f"The net equity is paid monthly over {EQUITY_MONTHS} months starting one month after the reservation. "
        "The balance is paid through the buyer's housing loan upon loan takeout.",
        "The buyer submits the Buyer's Information Sheet, two valid IDs and proof of income within 15 days.",
        "Failure to pay the equity on time may cancel the reservation as provided by the developer.",
    ).signatures(f"{BUYER['name']} (Buyer)", f"{AGENT} (Seller, Abellar Realty)",
                 f"Authorized representative, {DEVELOPER}").save("04-reservation-agreement.docx"))

    files.append(Doc("Official Receipt", "Reservation fee").fields([
        ("Receipt No", "OR-2026-10421"), ("Payment Date", long_date(day)), ("Received From", BUYER["name"]),
        ("Client ID", BUYER["client_id"]), ("Reservation ID", DEMO["reservation_id"]), ("Listing ID", DEMO["code"]),
        ("Amount Paid", peso(FEE)), ("Payment Method", "Cash"),
    ]).text("Received the amount above as reservation fee for the property stated.").signatures(
        "Cashier, Abellar Realty").save("05-official-receipt-reservation-fee.docx"))

    first_equity = day
    files.append(Doc("Official Receipt", f"Equity payment 1 of {EQUITY_MONTHS} (paid in advance)").fields([
        ("Receipt No", "OR-2026-10588"), ("Payment Date", long_date(first_equity)),
        ("Received From", BUYER["name"]), ("Client ID", BUYER["client_id"]),
        ("Reservation ID", DEMO["reservation_id"]), ("Listing ID", DEMO["code"]),
        ("Amount Paid", peso(MONTHLY_EQUITY)), ("Payment Method", "Bank transfer (BDO)"),
    ]).text(f"Received the amount above as the first of {EQUITY_MONTHS} monthly equity payments.").signatures(
        "Cashier, Abellar Realty").save("06-official-receipt-equity-1.docx"))

    files.append(Doc("Buyer's Document", "Letter of Guarantee - Pag-IBIG Fund (SAMPLE)").fields([
        ("Client ID", BUYER["client_id"]), ("Full Name", BUYER["name"]), ("Listing ID", DEMO["code"]),
        ("Lender", "Pag-IBIG Fund (sample)"), ("Approved Loan Amount", peso(LOAN)), ("Loan Term", "30 years"),
        ("LOG Number", "LOG-SAMPLE-2026-0101"),
    ]).text(f"This letter guarantees the release of the approved housing loan to {DEVELOPER} upon completion of "
            "the requirements for the property stated. SAMPLE ONLY, not issued by Pag-IBIG Fund.").save(
        "07-letter-of-guarantee.docx"))

    files.append(Doc("Deed of Absolute Sale").fields([
        ("Transaction ID", DEMO["sale_id"]), ("Reservation ID", DEMO["reservation_id"]),
        ("Sale Date", long_date(day)), ("Client ID", BUYER["client_id"]), ("Buyer Name", BUYER["name"]),
        ("Listing ID", DEMO["code"]), ("Property Title", TITLE), ("Agent Name", AGENT),
        ("Sale Amount", peso(TCP)),
    ]).text(f"KNOW ALL MEN BY THESE PRESENTS that {DEVELOPER}, for and in consideration of the sale amount above, "
            f"sells, transfers and conveys to the buyer named above the property stated, free from all liens "
            "and encumbrances.",
            "The buyer accepts the sale and the property in its present condition after inspection.").signatures(
        f"Authorized representative, {DEVELOPER} (Seller)", f"{BUYER['name']} (Buyer)",
        "Notary Public").save("08-deed-of-absolute-sale.docx"))

    files.append(Doc("Commission Voucher").fields([
        ("Voucher No.", DEMO["voucher_no"]), ("Date", long_date(day)), ("Agent name", AGENT), ("TCP", peso(TCP)),
        ("Particulars", f"{RATE}% sales commission, {TITLE}, buyer {BUYER['name']}"),
        ("Amount", peso(COMMISSION)), ("Mode of payment", "ATM"), ("Commission amount", peso(COMMISSION)),
        ("Bank name", "BDO"),
    ]).text("Received the commission stated above in full.").signatures(
        f"{AGENT} (Received by)", "Prepared by, Accounting", "Approved by, Abellar Realty").save(
        "09-commission-voucher.docx"))

    files.append(recruitment_form(day))
    for path in files:
        print(path.relative_to(OUT.parents[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
