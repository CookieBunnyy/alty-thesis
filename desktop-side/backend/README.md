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
