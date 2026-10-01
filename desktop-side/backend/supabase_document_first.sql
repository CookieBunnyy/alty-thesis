-- Align Supabase (central database) with the document-first local schema
-- (local Alembic revision 20260930_0005). Run once in the Supabase SQL Editor.
-- Idempotent: safe to re-run.
--
-- Why: a client may now exist before any transaction (Buyer Document) and may
-- hold transactions on more than one property; the old cloud constraints
-- (clients.property_id NOT NULL UNIQUE, agent/transaction_type NOT NULL)
-- would reject those rows when the backend pushes them.

BEGIN;

-- clients ---------------------------------------------------------------------
ALTER TABLE public.clients DROP CONSTRAINT IF EXISTS clients_property_id_key;
ALTER TABLE public.clients DROP CONSTRAINT IF EXISTS uq_clients_property_id;
DROP INDEX IF EXISTS public.uq_clients_property_id;
ALTER TABLE public.clients ALTER COLUMN property_id DROP NOT NULL;
ALTER TABLE public.clients ALTER COLUMN agent_id DROP NOT NULL;
ALTER TABLE public.clients ALTER COLUMN transaction_type DROP NOT NULL;
ALTER TABLE public.clients ALTER COLUMN transaction_date DROP NOT NULL;

ALTER TABLE public.clients DROP CONSTRAINT IF EXISTS ck_clients_status;
ALTER TABLE public.clients DROP CONSTRAINT IF EXISTS clients_status_check;
ALTER TABLE public.clients
    ADD CONSTRAINT ck_clients_status
    CHECK (status IN ('PROSPECT', 'RESERVED', 'SOLD', 'CANCELLED'));

-- Deleting a listing must not delete the client (history is kept).
ALTER TABLE public.clients DROP CONSTRAINT IF EXISTS clients_property_id_fkey;
ALTER TABLE public.clients
    ADD CONSTRAINT clients_property_id_fkey
    FOREIGN KEY (property_id) REFERENCES public.listings(listing_id) ON DELETE SET NULL;

ALTER TABLE public.clients
    ADD COLUMN IF NOT EXISTS occupation TEXT,
    ADD COLUMN IF NOT EXISTS civil_status TEXT,
    ADD COLUMN IF NOT EXISTS preferred_contact TEXT,
    ADD COLUMN IF NOT EXISTS purpose_of_purchase TEXT;
CREATE INDEX IF NOT EXISTS ix_clients_property_id ON public.clients(property_id);

-- transactions -------------------------------------------------------------------
ALTER TABLE public.transactions
    ADD COLUMN IF NOT EXISTS source TEXT,
    ADD COLUMN IF NOT EXISTS source_document_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_active_client_property_type
    ON public.transactions(client_id, property_id, transaction_type)
    WHERE status <> 'CANCELLED';

-- The legacy trigger assumed one client per property and rewrote client rows
-- whenever a listing status changed; the backend now owns that reconciliation.
DROP TRIGGER IF EXISTS trg_sync_client_property_status ON public.listings;

-- Backend-only access (service role). No anon/authenticated grants are added.
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.clients TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.transactions TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.listings TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.agents TO service_role;

COMMIT;

NOTIFY pgrst, 'reload schema';
