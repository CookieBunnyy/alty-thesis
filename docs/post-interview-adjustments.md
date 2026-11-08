# ALTY – Post-interview requirements validation and system adjustments

This document records the audit of the existing ALTY system against the
follow-up interview with Abellar Realty, the changes made, and the questions
that still need Abellar's confirmation.

Scope: the web-based system (website + Management System at `/manage`) and
its API (`desktop-side/backend`). The retired desktop client is not changed.

---

## Phase 1 – Audit of the existing system

### Architecture

| Layer | Implementation |
|---|---|
| Website + Management System | React 19 / Vite / Tailwind v4 (`website-side/frontend`), deployed on Vercel. Management pages live under `src/manage/`. |
| Main API | FastAPI + SQLAlchemy + Alembic (`desktop-side/backend`), PostgreSQL (Supabase), deployed on Render (`alembic upgrade head` on start). |
| Chatbot (MIA) | FastAPI + scikit-learn (`website-side/backend`); reads the public listings from the main API. |
| Central sync | Agents, listings, clients and transactions are pushed to / pulled from Supabase tables (`cloud_sync.py`, `*_sync.py`). |
| Auth | JWT bearer tokens, bcrypt, session version, DB-backed throttling, captcha. Staff and website clients share the `users` table; `role` decides access. |

### Roles before the change

| Role | Pages (nav) | API guard sets |
|---|---|---|
| Administrator | everything | `MANAGEMENT_ROLES`, `FILING_ROLES`, `require_admin` |
| General Manager | everything except Audit | `MANAGEMENT_ROLES`, `FILING_ROLES` |
| President | everything except Users, Audit | `MANAGEMENT_ROLES`, `FILING_ROLES` |
| Filing Manager | dashboard, properties, partners, clients, transactions, documents, media, agents, settings | `FILING_ROLES` |
| Agent | same as Filing Manager (+ "My Work" when linked to an agent record) | none beyond "signed in" |
| Employee | same as Filing Manager | none beyond "signed in" |
| Client | website only | `get_current_client` |

**Finding:** most read endpoints (`/transactions`, `/clients`, `/agents`,
`/dashboard/*`, `/analytics/overview`, `/documents`, `/search`, …) only require
*any* staff login. An Agent account could therefore read company-wide sales,
every client and every other agent's figures.

### Requirements comparison

| Existing implementation | Interview finding | Required adjustment | Priority |
|---|---|---|---|
| Six staff roles (Administrator, General Manager, President, Filing Manager, Agent, Employee) | Four user groups: Admin/Marketing staff (system admin), Seller/Agent, Filing Manager, Broker/Company owner | Map to **Administrator** (Admin / Marketing staff), **Broker** (company owner), **Filing Manager**, **Seller**; migrate existing accounts; keep legacy names working | High |
| Agent/Employee accounts can read company-wide data | Sellers must not see company-wide sales reports or other sellers' records | Close company data to Sellers; give Sellers their own scoped endpoints and pages | High |
| No developer accounts exist | Developers must not have system access | Keep it so: developers stay records (Partners), no role, cannot register | High (verify) |
| "Agents" terminology | Abellar calls them sellers | Label agents as **Sellers** in the Management System (data model and IDs unchanged) | Medium |
| Partners / Developers module (developer is optional on a listing) | Developer → Abellar (accredited) → Sellers → Buyers | Record each developer's **accreditation** of Abellar; add project name, floor area, perspective images; listings can only be **approved for marketing** with verified, unexpired accreditation; public site shows only approved listings | High |
| No link between listings and the sellers marketing them | Admin distributes listings to sellers | **Listing assignments** (which sellers market which listing) | High |
| Recruitment pipeline (applicant → onboarded) built earlier | Recruitment data: name, birthday, contact, address, email, recruiter, team/cluster, "not bound to another broker" declaration | Add birthday, recruiter, team/cluster, broker-affiliation declaration; link approved recruits to seller accounts; recruitment reports | High |
| Branches (offices) with branch-to-branch comparison | Teams/clusters (e.g. Pinyas, Batangas, San Pablo), configurable | Reuse the branches table as configurable **Teams / Clusters**; show each team's figures without rankings | Medium |
| Transactions start at reservation (from documents) | Inquiry → viewing (physical/virtual) → reservation → developer processing → closing | Add a **deal pipeline** from inquiry to closing with status history, linked to the existing reservation/sale records | High |
| Payment schedule and buying-cost estimate (tax/fee rates) | Payment schedule, taxes and closing procedure not established | Switch both **off by default** (configurable); keep code for when Abellar confirms | High |
| Commission figures estimated from a 3% default rate | Commission vouchers are the main retained document; sharing arrangement not yet validated | **Commission records** per transaction (sale or rental) with configurable commission structures, approval and release; no default rate | High |
| Document types include a generic "Voucher" | Commission Voucher is the primary retained document; actual field labels unknown | **Commission Voucher** document type: OCR text → all label/value pairs found, configurable field schema, human verification and correction, link to commission/seller/property/transaction | High |
| Analytics, forecasting, DSS, workforce planning | Management monitors **recruitment and sales** | **Reports**: sales and recruitment with date/seller/recruiter/team/project filters, daily/monthly/yearly; dashboard leads with sales and recruitment | High |
| Business Outlook forecasting | Not mentioned in the interview | Keep, labelled as an estimate that is not an interview requirement | Low |
| Document folders | Not mentioned | Keep (no change) | — |

### Decisions taken where the interview is silent (to confirm)

* **General Manager → Administrator, President → Broker, Employee → Filing
  Manager, Agent → Seller.** Old names still work everywhere (mapped on read).
* **Broker** has company-wide access, including Audit Logs and a read-only
  Users list; creating users, changing roles and system settings stay with the
  Administrator (the system administrator).
* Accreditation is recorded **per developer** (Partners) because Abellar is
  accredited by the developer; a listing inherits it from its developer.
* Sellers may edit only a configurable set of listing fields on listings
  assigned to them (default: description and amenities;
  `SELLER_EDITABLE_LISTING_FIELDS`).
* Seller commission visibility is **off** per seller until management turns it
  on for that seller.
* Branches (added earlier) are reused as **Teams / Clusters**; the
  branch-to-branch comparison was removed from that page (each team's own
  figures are shown).

---

## Phase 2–5 – Changes made

Each change lists the interview finding behind it. All database changes are
additive Alembic migrations (`0016`–`0021`); no data is deleted.

### 1. Roles and access control

* **Finding:** four user groups (Admin/Marketing staff, Seller/Agent, Filing
  Manager, Broker/Owner); sellers must not see company-wide reports or other
  sellers' records; developers have no access.
* **Change:** roles `Administrator`, `Broker`, `Filing Manager`, `Seller`
  (`app/core/security.py`). Legacy names map on read; migration `0016` rewrites
  stored roles and role descriptions. New guards: `get_company_user` (every
  company-data endpoint) and `get_seller_user` (seller pages). A Seller account
  must be linked to its seller record. Listing/photo editing is limited to
  management. The Broker can read the audit trail and the Users list but not
  create accounts.
* **Frontend:** menu by role, seller home = My Work, global search hidden for
  sellers, "Agents" labelled **Sellers**, "Buyers & Sellers" labelled
  **Buyers & Owners**.

#### Role and permission matrix

| Page / action | Administrator | Broker | Filing Manager | Seller |
|---|:-:|:-:|:-:|:-:|
| Dashboard (company) | ✓ | ✓ | ✓ (sales only) | – |
| Reports – sales | ✓ | ✓ | ✓ | – |
| Reports – recruitment | ✓ | ✓ | – | – |
| Properties – view | ✓ | ✓ | ✓ | own + approved only |
| Properties – edit, approve for marketing, assign sellers | ✓ | ✓ | – | – |
| Listing description/amenities (assigned listings) | ✓ | ✓ | – | ✓ |
| Partners / developers, accreditation | ✓ | ✓ | – | – |
| Transactions and deal pipeline | ✓ | ✓ | view | own deals only |
| Commissions – record, approve, release | ✓ | ✓ | – | – |
| Commissions – view, attach vouchers | ✓ | ✓ | ✓ | own, if allowed |
| Document repository, voucher verification | ✓ | ✓ | ✓ | – |
| Voucher field set-up | ✓ | ✓ | – | – |
| Sellers, Recruitment, Teams, Workforce | ✓ | ✓ | – | – |
| Analytics, Business Outlook, Recommendations | ✓ | ✓ | – | – |
| Users & Access | ✓ manage | view | – | – |
| Audit Logs | ✓ | ✓ | – | – |
| System settings | ✓ | – | – | – |
| Developers | no account of any kind | | | |

### 2. Property and accreditation management

* **Finding:** Developer → Abellar (accredited) → Sellers → Buyers; Abellar
  doesn't own the properties.
* **Change (migration `0017`):** developer accreditation on Partners (status,
  reference, validity, notes, who verified it); listings gain project name,
  floor area and a marketing status (Draft / Approved / Withdrawn). A listing
  can be **approved for marketing only while its developer's accreditation is
  verified and unexpired**; the public website, MIA and the map show only
  approved listings, and an expiring accreditation removes them automatically
  (`services/accreditation.py`). Listing assignments record which sellers
  market which listing. Digital Preview uploads can be marked **Architectural
  perspective / project image**.
* **Setting:** `ACCREDITATION_REQUIRED` (default on). Existing listings start
  as Draft, so the public site is empty until developers' accreditations are
  recorded and listings approved — set it to `false` only for a transition.

### 3. Recruitment and seller management

* **Finding:** recruitment records hold birthday, contact, address, email,
  recruiter, team/cluster and a "not bound to another broker" declaration.
* **Change (migration `0018`):** those fields on applicants; approval requires
  the declaration; onboarding creates the seller record (with recruiter and
  team) and optionally the seller's login; teams are configurable (reusing the
  branches table). Sellers record who recruited them.

### 4. Transaction management (inquiry to closing)

* **Finding:** inquiry → viewing (physical or virtual) → decision → reservation
  → developer processing → closing.
* **Change (migration `0019`):** **deals** with inquiry date, viewing type and
  schedule, reservation date and status, developer processing status, closing
  date and full history (`deal_events`). Reservations and sales recorded from
  documents or "Proceed to sale" move the deal automatically; a cancelled
  reservation marks it lost. Sellers record inquiries and viewings for their
  own buyers. Existing reservations/sales were converted into deals.
* **Unconfirmed financial features switched off:** the reservation payment
  schedule and the buying-cost estimate (`PAYMENT_SCHEDULE_ENABLED`,
  `COST_ESTIMATE_ENABLED`, both default off).

### 5. Commission management

* **Finding:** commission vouchers are the main retained document; rental
  commissions are agreed between lessor and broker; the sharing arrangement is
  not validated.
* **Change (migration `0020`):** commission records (sale or rental) with the
  seller, property/project, basis, agreed amount, optional seller share,
  agreement, approval (pending/approved/rejected), release (partial or full)
  and the supporting voucher. **Commission structures** are optional and only
  suggest an amount. The earlier assumed 3% commission rate was removed:
  commission figures (Business Outlook, per seller, per team) now come only
  from recorded commission records. Sellers see their own records only when
  management enables it per seller.

### 6. Document repository and NLP/OCR

* **Change (migration `0021`):** document type **Commission Voucher**
  (recognised from its title), filed in a "Commission Vouchers" folder. The
  existing pipeline extracts the text (OCR when needed); every
  "label: value" pair is kept; fields are mapped through a **configurable
  schema** that starts empty (no field labels were invented). A person reviews
  the values, corrects them, links the voucher to its commission (seller,
  property and transaction follow) and verifies it. The original file is never
  modified; every verification is in the document history and audit log.

### 7. Reports and dashboard

* **Finding:** management monitors recruitment and sales; certificates are given
  to top sellers and top recruiters.
* **Change:** **Reports** page — sales (by period day/month/year, top sellers,
  by project, by team, every sale) and recruitment (applications, recruited
  sellers, top recruiters, by team, by status) with date, seller, recruiter,
  team and project filters, PDF export per table and printing. The dashboard
  now opens with sales and recruitment; the duplicated agent-performance card
  was removed and the revenue forecast is labelled an estimate. Business
  Outlook states that forecasts are statistical estimates.

---

## Files

**New backend:** `api/v1/seller.py`, `deals.py`, `commissions.py`, `reports.py`;
`services/accreditation.py`, `deal_pipeline.py`, `commissions.py`,
`document_review.py`, `reports.py`; `models/listing_assignment.py`, `deal.py`,
`commission.py`, `extraction.py`; migrations `0016`–`0021`.

**Changed backend:** `core/security.py`, `core/config.py`; routers `agents`,
`analytics`, `audit`, `clients`, `dashboard`, `documents`, `intelligence`,
`media`, `partners`, `property_listings`, `public`, `recruitment`, `search`,
`system`, `transactions`, `users`; services `analytics`, `client_sync`,
`document_classification`, `document_filing`, `document_processing`,
`workforce_planning`; models `agent`, `media`, `partner`, `property_listing`,
`workforce`.

**New frontend (`src/manage`):** `CommissionsPage`, `ReportsPage`,
`DealsPipeline`, `SellerListingsPage`, `listingMarketing`, `voucherReview`,
`dashboardSalesRecruitment`, `branches.ts`.

**Changed frontend:** `ManageApp`, `ManageLayout`, `format`, `ui`, `tours`,
`i18n.fil` (≈380 Filipino strings), `AgentsPage`, `agentWorkforce`,
`BranchesPage`, `DashboardPage`, `DocumentsPage`, `ForecastingPage`,
`MediaPage`, `PartnersPage`, `PropertiesPage`, `PropertyEditForm`,
`RecruitmentPage`, `TransactionsPage`, `UsersPage`, `ProfilePage`,
`WorkforcePlan`.

### New and changed API endpoints

| Endpoint | Purpose |
|---|---|
| `GET/POST /property-listings/{id}/marketing` | accreditation state; approve / withdraw |
| `POST /property-listings/{id}/sellers`, `DELETE …/sellers/{agent}` | assign / remove sellers |
| `GET /seller/listings`, `PUT /seller/listings/{id}` | seller's listings; permitted edits |
| `GET /seller/commissions` | seller's own commissions (if allowed) |
| `GET/POST /deals`, `GET /deals/summary`, `GET/PUT /deals/{id}`, `POST /deals/{id}/stage` | deal pipeline |
| `GET /commissions`, `/summary`, `/{id}`; `POST /commissions`; `PUT /{id}`; `POST /{id}/approval`, `/release`, `/cancel`; `PUT /{id}/voucher` | commission records |
| `GET/POST /commissions/structures`, `PUT /commissions/structures/{id}`, `POST /commissions/preview` | commission structures |
| `GET /documents/schemas`, `PUT /documents/schemas/{type}` | configurable extraction fields |
| `GET/PUT /documents/{id}/extraction`, `POST …/extraction/remap` | voucher review and verification |
| `GET /reports/sales`, `/reports/recruitment`, `/reports/dashboard` | management reports |
| `GET /transactions/features` | which unconfirmed financial features are on |
| Partners create/update | accreditation fields |
| `POST /recruitment/applicants/{id}/onboard` | optional seller login (`account`) |
| `PUT /agents/{id}/assignment` | `commission_visible` |
| Company-data endpoints | now refuse Seller accounts |

---

## Phase 6 – Test results

* Backend: **193 automated tests pass** (PostgreSQL test database), including
  new suites `test_interview_roles`, `test_accreditation`, `test_deal_pipeline`,
  `test_commissions`, `test_commission_vouchers`, `test_reports`, plus the
  updated workforce, payment and cost tests.
* Browser checks (Chrome, desktop 1366 px and phone 390 px) for each role:
  menus match the matrix; a Seller gets "not available" on Reports and
  Transactions; approval is blocked for a listing without accreditation; a
  commission voucher was uploaded, read, verified and linked; a seller recorded
  an inquiry with a virtual viewing. No console errors, no horizontal scrolling.
* Website: TypeScript, ESLint and production build pass.

---

## Outstanding questions for Abellar Realty

1. **Commission voucher sample:** the printed field labels (to configure the
   voucher schema) and which fields are required.
2. **Commission sharing:** how commission is split between seller and Abellar,
   per developer or per project; whether rates differ by property type.
3. **Rental commissions:** the usual basis (e.g. months of rent) and who
   records rental agreements.
4. **Accreditation:** is it granted per developer, per project, or both, and
   does it expire? Which document proves it?
5. **Roles:** confirm the mapping of the former General Manager and Employee
   accounts, and whether the Broker should manage user accounts.
6. **Seller permissions:** which listing fields sellers may edit, and whether
   sellers should see their commissions by default.
7. **Payment schedule and buying costs:** the reservation fee, down payment and
   monthly terms, and the taxes/fees buyers pay — currently switched off.
8. **Developer processing:** the actual steps/statuses between reservation and
   closing.
9. **Certificates:** the format and criteria for top-seller and top-recruiter
   certificates (not built yet).
10. **Terminology on the public website:** whether buyers should see "seller"
    or "agent".
