# Demo walkthrough: from listing to closed deal

Sample documents for presenting ALTY step by step. Everything here is fictitious and marked SAMPLE.
They belong to the demonstration data from `scripts/seed_demo_flow.py`:

- **Property:** `ABR-26-0101`, *Lumina Tanza - Bettina Single Attached, Blk 7 Lot 5*. It is AVAILABLE and handled by seller **Andrea Villanueva**.
- **Buyer:** **Carlo M. Mendoza** (`BUY-2026-0101`). New: the first document creates him.
- **Price terms:** TCP ₱1,850,000. Reservation fee ₱15,000. Down payment 10%, with the equity paid over 24 months. The balance is paid through a Pag-IBIG loan.

## Setting up (once, before the presentation)

Run these from `desktop-side\backend`:

```
python scripts\reset_demo_data.py --database-url "<postgresql://...>"     # start from zero (makes a backup)
python scripts\seed_developers.py --database-url "<postgresql://...>"     # developers and logos
python scripts\seed_demo_flow.py --database-url "<postgresql://...>"      # a year of records
python scripts\make_demo_documents.py --date 2026-11-20                   # date the documents for the presentation day
```

Accounts (password `Demo-2026!` for all except admin):

| Role | Username |
|---|---|
| Administrator | `admin` / `admin1234` |
| Filing Manager | `filingmanager` |
| Sellers | `andrea.villanueva`, `mark.dizon`, `bea.fernandez`, `kristine.bautista`, `paolo.ramirez`, `miguel.torres`, `joanna.mercado`, `rafael.gutierrez` |

## The walkthrough

| # | Who | Where | What to do | What the system does |
|---|---|---|---|---|
| 1 | Buyer | Website > Properties | Open *Lumina Tanza - Bettina…, Blk 7 Lot 5*. Show the status, financing and **sample computation**, then **Reserve / Purchase**. | Andrea is listed first ("Handles this property"). |
| 2 | Seller (andrea.villanueva) | My deals > New inquiry | Record Carlo's inquiry on that property: **Carlo M. Mendoza**, `0917 555 0142`, `carlo.mendoza@example.com` (the same contact details as his papers, so the documents attach to this deal). Then **Arrange viewing**. Optionally add a **Tripping schedule** entry and press Notify. | Deal at *Inquiry*, then *Viewing*. |
| 3 | Filing Manager | Document Repository > Upload | `01-buyers-information-sheet.docx`, `02-buyers-document-valid-id.docx`, `03-buyers-document-proof-of-income.docx` | Creates the buyer and files the papers under **Buyers / Carlo M. Mendoza**. |
| 4 | Filing Manager | Document Repository | `04-reservation-agreement.docx`, `05-official-receipt-reservation-fee.docx` | Records the reservation (₱15,000). The property becomes *Reserved*; the deal *Reserved*. The receipt links to RSV-2026-0101. |
| 5 | Administrator | Transactions > Pipeline > Carlo's deal | Set **Financing** to Pag-IBIG loan and **Equity terms** to 24 months. | The payment schedule now shows 24 equity payments, then the loan takeout. |
| 6 | Filing Manager | Same deal, "After the reservation" | Tick the Reservation Agreement, Buyer's Information Sheet, Valid IDs and Proof of income. | The deal moves to *Under evaluation*. |
| 7 | Filing Manager, then Administrator | Document Repository; Transactions > the reservation | Filing Manager uploads `06-official-receipt-equity-1.docx`. Administrator records the ₱7,083.33 payment on the reservation's payment schedule. | The first equity payment shows as *Paid*. |
| 8 | Filing Manager | Document Repository, then the deal | Upload `07-letter-of-guarantee.docx`, then tick **Loan application submitted**, **Loan approved (LOG)** and **Turnover**. | Steps done, with dates and who did them. |
| 9 | Filing Manager | Document Repository | `08-deed-of-absolute-sale.docx` | Records the sale (₱1,850,000). The property becomes *Sold*; the deal *Closed*. |
| 10 | Administrator | Commissions > New commission | Choose Carlo's sale. The amount fills in at **5% of the TCP** (₱92,500). Record it, then **Approve**. | Pending, then approved. |
| 11 | Filing Manager | Document Repository | `09-commission-voucher.docx`, then open it and check the 8 fields (agent, date, TCP, particulars, amount, mode of payment, commission amount, bank). Link it to the commission and **Verify**. | Filed under **Commission Documents** and linked to the commission. |
| 12 | Administrator | The commission > Record release | Release ₱92,500 via ATM, BDO (or in two parts). | *Released*, with the payout listed. |
| 13 | Seller (andrea.villanueva) | My commissions / My deals | Show *Received* and *Upcoming*, and the deal's steps. | |
| 14 | Administrator | Dashboard, Reports | Show sales by month and quarter, top sellers, teams and recruitment; use Export PDF / Print. | Carlo's sale is included. |

**Recruitment (optional):** the Filing Manager opens Recruitment > New applicant, enters *Patricia Anne Lim* and adds `10-recruitment-form-patricia-lim.jpg` as the recruitment form. The Administrator then moves her through Screening > Interview > Approved > Onboard.

## Tips

- Upload in the order above. A document fails when what it refers to doesn't exist yet: the reservation needs the property to be AVAILABLE, and the receipt needs the reservation.
- To redo the walkthrough, reset and seed again (step "Setting up").
- The seeded listings have no photos. Upload a few real photos to the demo property (Properties > the property > Images) for nicer cards.
