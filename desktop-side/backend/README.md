# Abellar Realty Desktop Backend

## 1. Recommended desktop system architecture

The desktop application is the internal enterprise layer that manages operational data, documents, workforce, properties, and transactions for Abellar Realty. It is separated from the public website and functions as the authoritative system of record for internal operations.

### Architectural layers

1. Presentation layer
   - PyQt6 desktop client
   - Role-aware sidebar and module navigation
   - Forms, dashboards, tables, filters, and modal dialogs

2. Application layer
   - FastAPI API
   - Business logic services
   - Validation and authorization
   - Document intake, analytics, and recommendation services

3. Data layer
   - PostgreSQL as the primary transactional database
   - SQLite for local/offline caches where applicable
   - SQLAlchemy ORM and Alembic migrations

4. Intelligence layer
   - Document classification support
   - Media validation and feature extraction
   - Forecasting and analytics
   - Decision-support recommendation generation

5. Integration layer
   - Future website integration through centralized data services
   - Partner and developer data feeds
   - Document and media exchange interfaces

### Core design principles

- Internal management system only; public website is out of scope
- Role-based access control for all operational modules
- Business logic stays in backend services, not in UI code
- AI and analytics are decision-support tools only
- No irreversible action without human review

## 2. Database ERD / relationship design

The core domain models are:

- Branch
- User
- Role
- Partner
- Property
- Client
- Seller / Source
- Transaction
- Document
- Media
- Commission
- Forecast
- Recommendation
- AuditLog

The key relationships are:

- Branch has many users, employees, agents, and properties
- Role has many users
- Partner has many properties and related documents
- Property belongs to a branch, partner, and assigned agent
- Client has many inquiries, transactions, and related documents
- Transaction belongs to a property, client, and agent
- Document can relate to multiple business records
- Recommendation is derived from analytics and monitoring history

## 3. Complete database table list

Core tables:

- roles
- branches
- users
- employees
- agents
- partners
- properties
- clients
- sellers
- transactions
- commissions
- documents
- media
- sales_summary
- forecasts
- recommendations
- audit_logs
- permissions
- user_permissions

## 4. Module-to-table mapping

| Module | Primary tables |
| --- | --- |
| Dashboard | users, transactions, properties, commissions, recommendations, audit_logs |
| Property & Partner Management | properties, partners, branches |
| Client & Transaction Management | clients, sellers, transactions, commissions |
| Centralized Records & Repository | documents, audit_logs |
| Agent & Workforce Management | users, employees, agents, branches |
| Digital Preview Management | media, properties |
| Forecasting & Analysis | sales_summary, transactions, forecasts |
| Decision Support & Recommendations | recommendations, analytics summaries, properties, transactions |
| User Access & System Administration | users, roles, permissions, audit_logs |

## 5. Role and permission matrix

| Role | Core access |
| --- | --- |
| President | Company overview, all branch analytics, strategic recommendations |
| General Manager | Branch operations, transactions, approvals, dashboard |
| Administrator | User management, role assignment, configuration |
| Filing Manager | Document repository, approval, archive, audit review |
| Agent | Assigned clients, assigned properties, transactions, commission |
| Employee | Only authorized responsibilities and branch-scoped tasks |

Permissions should be configurable and can be extended as the organization structure is validated.

## 6. Backend folder structure

```text
backend/
  app/
    __init__.py
    api/
      __init__.py
      deps.py
      v1/
        __init__.py
        auth.py
    core/
      __init__.py
      config.py
      database.py
      security.py
    models/
      __init__.py
      branch.py
      role.py
      user.py
      property.py
    schemas/
      __init__.py
      auth.py
      branch.py
      user.py
    services/
      __init__.py
      auth_service.py
  alembic/
    versions/
  alembic.ini
  main.py
  requirements.txt
  .env.example
```

## 7. Desktop frontend folder structure

```text
desktop-frontend/
  app/
    main.py
    windows/
      main_window.py
      login_window.py
    widgets/
      sidebar.py
      dashboard_card.py
    screens/
      dashboard_screen.py
      properties_screen.py
      clients_screen.py
      transactions_screen.py
      documents_screen.py
      workforce_screen.py
      analytics_screen.py
      recommendations_screen.py
      admin_screen.py
  resources/
    icons/
    styles/
  requirements.txt
```

## 8. API structure

```text
/api/v1
  POST /auth/login
  POST /auth/register
  GET /auth/me
  GET /branches
  POST /branches
  GET /properties
  POST /properties
  GET /transactions
  POST /transactions
  GET /documents
  POST /documents
  GET /recommendations
  POST /recommendations/review
  GET /audit-logs
```

## 9. Development sequence

1. Phase 1: Foundation and auth
2. Phase 2: Users, roles, branches, partners, properties
3. Phase 3: Clients, agents, transactions, commissions
4. Phase 4: Document repository and audit trail
5. Phase 5: Desktop UI shell and role-aware navigation
6. Phase 6: Media and OpenCV integration foundation
7. Phase 7: Analytics and forecasting
8. Phase 8: Decision support recommendations
9. Phase 9: Hardening, testing, and deployment readiness

## 10. Requirements TO BE VALIDATED

The following items are not fully explicit from the manuscript and should be validated with the client before implementation is considered final:

- Exact employee hierarchy and branch structure
- Ownership model for properties relayed by partners and developers
- Commission split formulas and approval workflow
- Document retention policy and archive lifecycle
- Required document sets per transaction type
- Property media acceptance workflow
- Forecasting KPI definitions and confidence thresholds
- Recommendation review process and approval rules
- Detailed role-permission matrix by branch
- Local/offline use requirements for branch offices
- Whether the desktop app should also support multi-branch syncing

## Phase 1 implementation status

This project has begun with the Phase 1 foundation:

- FastAPI backend skeleton
- PostgreSQL configuration
- SQLAlchemy base setup
- Initial user/role/branch/property models
- Authentication helpers
- Alembic-ready structure

The remaining phase 1 work is to complete the database migration and verify the backend bootstraps correctly.

## Document Repository

The desktop repository uses the existing authenticated FastAPI API. Files are uploaded to the private Supabase Storage bucket by FastAPI; document metadata is written to the Supabase `public.documents` table and local PostgreSQL. The Supabase service-role key belongs only in the backend environment, never in the desktop application.

Configure these backend environment variables (for example, in `desktop-side/backend/.env`):

```dotenv
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVER_SIDE_SERVICE_ROLE_KEY
SUPABASE_DOCUMENTS_BUCKET=documents
```

Create the private bucket and metadata table in the Supabase SQL editor:

```sql
insert into storage.buckets (id, name, public, file_size_limit)
values ('documents', 'documents', false, 26214400)
on conflict (id) do update
set public = false, file_size_limit = 26214400;

create table if not exists public.documents (
  document_id uuid not null,
  version integer not null,
  document_name varchar(255) not null,
  document_type varchar(80) not null,
  folder_id integer,
  property_id integer,
  transaction_id integer,
  related_party_id integer,
  related_party_name varchar(200),
  description text,
  storage_path varchar(1000) not null,
  storage_bucket varchar(120) not null,
  mime_type varchar(160) not null,
  file_size integer not null,
  file_hash varchar(64) not null,
  status varchar(32) not null,
  uploaded_by integer not null,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  confirmed_by integer,
  confirmed_at timestamptz,
  archived_by integer,
  archived_at timestamptz,
  rejected_by integer,
  rejected_at timestamptz,
  duplicate_of_id integer,
  primary key (document_id, version)
);

alter table public.documents enable row level security;
revoke all on table public.documents from anon, authenticated;
grant all on table public.documents to service_role;

drop policy if exists documents_bucket_service_role_only on storage.objects;
create policy documents_bucket_service_role_only
on storage.objects as restrictive for all to public
using (bucket_id <> 'documents' or auth.role() = 'service_role')
with check (bucket_id <> 'documents' or auth.role() = 'service_role');
```

Apply local schema changes and start the backend from `desktop-side/backend`:

```powershell
python -m alembic upgrade head
python main.py
```

Start the desktop app from `desktop-side/frontend` with `python main.py`. `Property`, `User`, and `DocumentFolder` are linked with foreign keys; transaction and buyer/seller IDs are nullable integration fields until those tables exist. Document classification, confirmation, archive, rejection, and replacement actions require an Administrator, General Manager, or Filing Manager account. The classification service is an extension point only; no AI decisions are simulated.

## Agent Management

Agents are sourced from the Supabase `public.agents` table and synchronized into the local PostgreSQL `agents` table by FastAPI. The service-role credential stays in the backend environment. Coordinates are stored for future location-based features; this module does not implement a website map.

Create the Supabase table and demo rows in the Supabase SQL editor. These names and records are demonstration data:

```sql
create table if not exists public.agents (
  agent_id varchar(32) primary key,
  full_name varchar(200) not null,
  phone_number varchar(40),
  agent_location varchar(255),
  latitude numeric(9, 6),
  longitude numeric(9, 6),
  star_rating numeric(2, 1),
  assignments_count integer not null default 0,
  transactions_count integer not null default 0,
  completed_sales integer not null default 0,
  total_sales numeric(16, 2) not null default 0,
  total_commission numeric(16, 2) not null default 0,
  performance_score numeric(6, 2) not null default 0,
  status varchar(24) not null default 'ACTIVE',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.agents enable row level security;
revoke all on table public.agents from anon, authenticated;
grant usage on schema public to service_role;
grant select on table public.agents to service_role;

insert into public.agents (
  agent_id, full_name, agent_location, latitude, longitude, star_rating
) values
  ('AGT-0001', 'Maria Santos', 'BGC, Taguig', 14.5547, 121.0244, 4.8),
  ('AGT-0002', 'John Reyes', 'Makati City', 14.5547, 121.0167, 4.6),
  ('AGT-0003', 'Angela Cruz', 'Quezon City', 14.6760, 121.0437, 4.9),
  ('AGT-0004', 'Michael Garcia', 'Pasig City', 14.5764, 121.0851, 4.5),
  ('AGT-0005', 'Sofia Mendoza', 'Parañaque City', 14.4793, 121.0198, 4.7)
on conflict (agent_id) do update set
  full_name = excluded.full_name,
  agent_location = excluded.agent_location,
  latitude = excluded.latitude,
  longitude = excluded.longitude,
  star_rating = excluded.star_rating,
  updated_at = now();
```

After creating/seeding Supabase, run `python -m alembic upgrade head` from `desktop-side/backend`; the migration seeds the same local demo records marked `DEMO`. Start the backend with `python main.py` and the desktop from `desktop-side/frontend` with `python main.py`. Use **Sync from Supabase** in Agent Management to insert or update local rows by `agent_id`; syncing requires an existing Administrator or General Manager role. Endpoints: `GET /api/v1/agents`, `GET /api/v1/agents/{agent_id}`, and `POST /api/v1/agents/sync`.

## Locally Added Property Listings

`POST /api/v1/property-listings` creates a row in local PostgreSQL only, obtains `listing_id` from the PostgreSQL sequence, and marks the row `PENDING`. The sequence alignment migration advances the existing sequence beyond the current maximum ID. The existing **Sync Listings** operation is pull-only (`Supabase listings` to `PostgreSQL`); it does not publish pending local rows. To publish a new record, an authorized operator must explicitly create/upsert it in Supabase using the generated `listing_id` and listing data, then the existing pull sync can reconcile it and mark it `SYNCED`. Do not rely on Sync Listings to upload the record: if Supabase returns a row with the same ID, the current pull sync overwrites local fields from Supabase. No automatic two-way write was added.

Apply backend migrations with `python -m alembic upgrade head` from `desktop-side/backend`. Photo selections are stored as text path references in `photos`; this form does not upload image files to Supabase Storage.

## Property Status Synchronization

The local `property_listings.status` field is migrated with a database default of `AVAILABLE`. Add the corresponding field to Supabase `public.listings` before editing properties whose `sync_status` is `SYNCED`; status changes to synced rows are mirrored to Supabase, and pull sync reads a valid cloud status when present. When the cloud row lacks a status, pull sync preserves the existing local status (new rows default to `AVAILABLE`).

Run this in the Supabase SQL Editor:

```sql
alter table public.listings
  add column if not exists status varchar(20) not null default 'AVAILABLE';

update public.listings
set status = 'AVAILABLE'
where status is null or trim(status) = '';

alter table public.listings
  alter column status set default 'AVAILABLE',
  alter column status set not null;
```

The desktop does not connect to Supabase. FastAPI uses its existing server-side Supabase credentials for synced-row updates/deletes. New local `PENDING` rows remain local until explicitly published through the established operator workflow.
