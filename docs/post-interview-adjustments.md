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

---

## Follow-up changes (2026-11-09)

### Broker role removed
* Roles are now **Administrator**, **Filing Manager** and **Seller**. The Broker
  column in the role matrix above no longer applies.
* Migration `20261109_0022` moves any account stored as `Broker` (or the older
  `President`) to `Administrator`. Nothing is deleted. Old names are still read
  as Administrator (`LEGACY_ROLES`), and `Broker` can no longer be assigned
  (422).

### Forgot password without email (Administrator approval)
There is no email subscription yet, so "Forgot password?" sends a request to
the Administrator instead of an email link.

1. The staff member enters their username (or registered email) and an optional
   message. Their browser receives a secret and a 6-digit **check code**. The
   server stores only the secret's SHA-256 hash.
2. Administrators see the request in the notification bell and at the top of
   **Users & Access**. To approve, they type the check code the person reads to
   them, in person or by phone. A wrong code can't be approved.
3. The requester's page checks every 10 s. Once the request is approved, it shows
   the "choose a new password" form, but only on the device that asked. The
   reset is single-use, ends every session of the account and is written to the
   audit log.
4. A request waits up to 72 h (`PASSWORD_RESET_REQUEST_HOURS`). An approval stays
   usable for 24 h (`PASSWORD_RESET_APPROVED_HOURS`). Declined and expired
   requests can't be used. Each account can have at most 3 pending requests, and
   the existing per-IP and per-account rate limits apply.
5. Unknown usernames get the same answer, so the page doesn't reveal which
   accounts exist.

* `PASSWORD_RESET_VIA` (default `admin`) chooses the mode. Set it to `email`
  (with `STAFF_APP_URL` and `EMAIL_PROVIDER`) to go back to email links later.
* Endpoints:
  - `POST /auth/password-reset/ask`
  - `POST /auth/password-reset/status`
  - `GET /password-requests`
  - `POST /password-requests/{id}/approve|deny` (Administrator only)
  - the existing `POST /auth/password-reset/confirm` finishes the reset.
* Migration `20261109_0023` adds `password_reset_requests`.
* Tests: `tests/test_password_requests.py`.

### Loading screen
The logo was removed from the welcome/loading screen (`index.html`). The text
and the progress bar stay.

---

## Demo preparation and office-board features (2026-11-09)

### Starting from zero
`desktop-side/backend/scripts/reset_demo_data.py` deletes every record and leaves one account: `admin` / `admin1234`. Change that password after the demo.

How it works:
* It writes a full `pg_dump` backup to `~/alty-backups` first, and stops if the backup fails.
* It keeps the schema version, `roles`, `document_schemas` and the document folder structure.
* Run it with `--yes`, and add `--database-url "<url>"` for a database other than the one in `.env`.
* Storage files and the central Supabase tables are not touched. Pressing a **Sync** button afterwards brings the central records back.
* Restore with `pg_restore --clean --if-exists -d "<url>" <backup file>`.

### Sellers as accounts and sellers adding properties
* **Users & Access → New user → Seller:** if no seller record is picked, one is created from the name, mobile number and team. Email is optional.
* **Adding a property:** `POST /property-listings` is open to the Administrator and to sellers.
  - The **developer is required** and must be a partner of type Developer.
  - A seller's property is assigned to them and starts **not approved**, so it isn't on the website until the Administrator approves it. That approval still needs the developer's verified accreditation.
  - The seller can edit every field of their own property until it is approved.
* **Images:** the add-property form has a second step with three groups of images, each checked for quality as it is uploaded (resolution, sharpness, brightness and contrast).
  - Property photos and perspectives.
  - **Floor plans**, with a label. Drawings aren't marked down for being bright or low in contrast.
  - **Amenities**, with a required name, laid out like the developer's flyer.
  - Images that fail the check are never shown on the website.
* **Digital Preview page:** removed. Quality analysis now happens where images are uploaded.
* **On the website:** the property popup shows **Floor plans** and **Amenity** pictures with their captions.

### Announcements & memos (`/manage/bulletin`)
* **Announcements:** monthly meeting (with date and time), update, project/flyer, general.
* **Memos:**
  - **target sales**: progress is shown to company staff;
  - **incentive**: reward tiers by minimum sales (e.g. Bohol ₱75M, Boracay ₱100M, Thailand ₱150M), and/or a flat incentive per sale, optionally limited to one developer;
  - **sales notice**: date, buyer, agent, project and TCP of a recorded reservation, like the whiteboard memo;
  - **general**.
* Optional flyer image, pinning and archiving. The Administrator posts, and **every new post notifies every staff account**.
* **Sales figures:** only recorded reservations and sales count, each buyer-property deal once, cancelled ones excluded. Sellers see the target and their own figures, never the company total or other sellers.

### Transactions in the whiteboard format
The default view is a **sales board by team**. There is one table per team or cluster, with columns RES. DATE · BUYER · AGENT · PROJECT NAME · TCP. The record list uses the same columns.

### Tripping schedule (`/manage/trips`)
* **Columns:** DATE · PICK-UP · TIME · SUBDIVISION · AGENT, plus buyers and status (scheduled, confirmed, ongoing, done, cancelled).
* **Live updates:** every open board checks `GET /trips/version` every 8 seconds and reloads only when something changed. Phones show trips as cards.
* **Who sees what:** sellers see and manage their own trips, and can only add their own buyers. Company staff see all trips.
* **Notify buyers:**
  - Buyers with a website account see the schedule and message under **My site trippings** on their account page, which checks for changes every 15 seconds.
  - Every buyer with a number gets a ready text message, with an SMS link and a copy button for Messenger or Viber.
  - Changing a trip marks its buyers as not yet notified.
* **Notifications:** trips in the next two days, and recent changes, go to the agent and to company staff.

### Endpoints and migration
* **Endpoints:**
  - `POST /property-listings`
  - `GET /seller/developers`
  - `PATCH /media/{id}` (caption and kind)
  - `/bulletin` (CRUD, `/{id}/image`, `/sales-options`)
  - `/trips` (CRUD, `/version`, `/buyer-options`, `/{id}/status`, `/{id}/notify`)
  - `/client/trips`, `/client/trips/read`
* **Migration** `20261109_0024`: `bulletin_posts`, `trips`, `trip_buyers`, `trip_notices`, `property_media.caption` and `property_listings.submitted_by_user_id`.
* **Tests:** `tests/test_demo_features.py`.

### Developers from the office board (2026-11-10)
`desktop-side/backend/scripts/seed_developers.py` adds the 24 developers and partners from the office's "Developers and Partners" board, with 23 logos in `scripts/developer_logos/` (Jeika has no logo yet).
* Re-running it is safe: existing names are kept, and a developer only gets a logo if it has none.
* Run it with `--database-url "<url>"` for the live database.
* Every developer is recorded as accredited (Verified), because they are on the official board. Reference numbers and expiry dates can be added per developer.
* The home page shows the logos in full colour on white cards, and the Partners table shows each logo.

Every password field now has a show / hide button (`src/components/PasswordInput.tsx`).

### One copy of the data: old website tables retired (2026-11-10)
The desktop era copied records out to the old website tables in Supabase (`public.agents`, `public.listings`, `public.clients`, `public.transactions`). After the reset they still held the old sample data. New records then showed "Pending", and pushing them failed because new IDs such as AGT-0001 collided with the old ones.
* **Copying is off:** `CLOUD_SYNC_ENABLED` now defaults to `false`, and `render.yaml` sets it to `false` too. The API's own tables (schema `alty_api`) are the only copy.
* **MIA** reads listings and agents only from the API's public endpoints (`/api/v1/public/properties` and `/agents`). It recommends exactly what the website shows, and never reads the old tables.
* **Management System:** the "Sync from Supabase" buttons and the Sync columns and labels are gone. The Settings push panel appears only if copying is switched back on.
* The old `public.*` tables are no longer read by anything; deleting them is optional.

### Map pins and lot boundaries (2026-11-10)
* **Adding a property:** there are no latitude/longitude boxes. **Find on map** opens a map that searches the address already typed. Click the spot to drop a red pin; drag it to adjust. The pin's address fills the location field if that's empty.
* **Second step:** **Draw lot boundary** lets the seller outline the lot in red on satellite imagery. It measures the area, the perimeter and each side, and can set the lot area.
* **Who may draw the boundary:** management on any property; a seller only on a property they added, until it is approved (`PUT /property-listings/{id}/boundary`).
* **Agent location** (`PUT /agents/{id}/location`): sellers pin where they're based on **My Work**, and the Administrator can do it from the seller's drawer on the Sellers page. Without a pin, "Reserve / Purchase" on the website lists the agent as "Location not on the map" and can't rank by distance.

## Recruitment form uploads, agent mobile numbers, document folders (2026-11-10)

- **Recruitment form upload.** Each applicant has a "Recruitment form" section: photos or PDF scans of the
  form they filled in, one per page ("Add pages", or "Take a photo" on a phone), viewable full size.
  The pages can also be chosen while recording a new applicant. Table `applicant_forms`
  (migration `20261110_0025`); endpoints `POST/GET/DELETE /recruitment/applicants/{id}/forms[/{form_id}]`.
- **Filing Manager on Recruitment.** The Filing Manager can open Recruitment, record and edit applicants and
  upload their forms. Moving applicants through the stages, rejecting, onboarding and deleting stay with the
  Administrator.
- **No "Applying as".** Recruitment is only for sellers / agents, so the field is gone from the form, table and
  details; onboarding sets the designation (default Trainee Agent).
- **Agent mobile number.** Signed-in buyers call or text an agent from "Reserve / Purchase" only when the agent
  has a mobile number. It could only be entered when the account was created; now the seller adds or changes
  it on My Work, and the Administrator in the Sellers drawer (`PUT /agents/{id}/phone`). The website says
  "No mobile number on file yet" instead of showing no buttons.
- **Document folders.** Top-level folders are now Commission Documents (was Commission Vouchers), Vouchers,
  Properties, Buyers, Sellers, Agents, Transactions and Archived. "Financial" and "Contracts" are removed:
  vouchers go to Vouchers; receipts, proof of payment, invoices and contracts are filed under
  Buyers / <client> with the rest of the client's purchase. The migration moves existing folders and documents
  (same-named client folders are merged) and then deletes the emptied folders.

## Second interview (2026-11-11)

Abellar Realty's answers to the outstanding questions above, and what changed (migration `20261111_0026`).

| # | Answer | Change |
|---|---|---|
| 1 | Voucher details: agent who sold, voucher date, TCP, particulars, amount, where paid (ATM, etc.), commission amount, bank name. No sample yet. | The Commission Voucher field set-up starts with these 8 fields (with common printed labels as aliases), still editable once a real sample arrives. |
| 2 | Rate depends on the agreement; usually 3–5% of the TCP, mostly 5%. Buyers mostly pay through a bank, SSS or Pag-IBIG loan. | New sale commissions start at **5% of the TCP** (`DEFAULT_COMMISSION_RATE_PERCENT`), editable; the agreed amount always wins. Rentals still need an amount. |
| 3 | Released all at once ("isang bagsakan") or in parts ("paonti-onti"), as the lender pays. | Each payout is its own record (`commission_releases`) with method (ATM, bank transfer, check, cash, e-wallet), bank name, reference and particulars. |
| 4 | Accreditation may cover all projects (nationwide/regional) or specific projects/clusters; usually 1 year, renewed yearly. | Partners record the **scope** (all projects / region / named projects). A listing under a project-specific accreditation must be one of the named projects to be approved or shown. A verification without an end date lasts a year; **Renew for another year**; warning 30 days before it ends. |
| 5 | Sellers see their own buyers, each sale's status (pending, reserved, under evaluation, closed) and their commissions (received and upcoming). | Commissions are **shared with sellers by default** (management can still turn it off per seller); My commissions shows Received / Upcoming / Waiting for approval and each payout. Developer processing is labelled **Under evaluation**; deals show the next step. |
| 6 | After the reservation: documents (Reservation Agreement, Buyer's Information Sheet, IDs, proof of income) → equity monthly (12–24 months) → loan application (bank, in-house, Pag-IBIG) → loan approval / LOG → inspection and turnover → fully paid, title transferred. | Each deal has these **steps** (ticked by company staff, visible to the seller), its **financing** (Bank, Pag-IBIG, SSS, In-house, Cash; loan steps only for loans) and **equity terms**. |
| 7 | Abellar tracks the buyer's payments too, depending on the financing. | The **payment schedule is on** (`PAYMENT_SCHEDULE_ENABLED`): reservation fee, equity in monthly instalments over the terms, then the **loan takeout** in one lump sum (bank / Pag-IBIG / SSS), in-house monthly amortization, or the cash balance. The tax/fee estimate stays off (not confirmed). |
| 8 | Top sellers by sales amount, monthly and quarterly. | Reports group by **quarter** too; the dashboard shows top sellers this month, this quarter and this year (by sales value). |
| 9 | Listings show RFO / pre-selling, financing accepted (Bank, Pag-IBIG, In-house), a sample computation (TCP, reservation fee, net equity, est. monthly amortization) and who to contact. | Listings record **property status**, **financing accepted**, **reservation fee** and **equity terms**; the website shows a **sample computation** and the developer; "Contact an agent" lists the sellers assigned to the property first (with email for signed-in buyers). |

Still open: rental commission basis, the voucher's exact printed labels (from a real sample), certificate format, and the buyer's taxes and fees.

Tests: `tests/test_interview_two.py` (accreditation scope and renewal, steps after the reservation, loan and in-house schedules, listing computation and contacts, quarterly reports), plus updated commission, voucher and deal tests: **217 backend tests pass**. Browser-checked: partner scope and renewal, deal steps (company and seller), property form computation, commission form at 5%, website sample computation, seller commissions.
