-- Run once in the Supabase SQL Editor. The desktop app accesses this table
-- only through the FastAPI backend using the service_role key.

ALTER TABLE public.listings
    ADD COLUMN IF NOT EXISTS external_listing_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS ix_listings_external_listing_id
    ON public.listings(external_listing_id);

CREATE TABLE IF NOT EXISTS public.clients (
    client_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_client_id TEXT,
    full_name TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
    location TEXT,
    phone_number TEXT,
    email TEXT,
    agent_id VARCHAR(32),
    property_id INTEGER NOT NULL UNIQUE
        REFERENCES public.listings(listing_id) ON DELETE CASCADE,
    transaction_type TEXT NOT NULL
        CHECK (transaction_type IN ('RESERVED', 'SOLD')),
    transaction_date TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('RESERVED', 'SOLD', 'CANCELLED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.clients
    ADD COLUMN IF NOT EXISTS agent_id VARCHAR(32);
ALTER TABLE public.clients
    ADD COLUMN IF NOT EXISTS external_client_id TEXT;
ALTER TABLE public.clients
    ADD COLUMN IF NOT EXISTS email TEXT;

ALTER TABLE public.clients
    DROP CONSTRAINT IF EXISTS ck_clients_status_matches_transaction_type;
ALTER TABLE public.clients
    DROP CONSTRAINT IF EXISTS ck_clients_status;
ALTER TABLE public.clients
    DROP CONSTRAINT IF EXISTS clients_status_check;
ALTER TABLE public.clients
    ADD CONSTRAINT ck_clients_status
    CHECK (status IN ('RESERVED', 'SOLD', 'CANCELLED'));

CREATE INDEX IF NOT EXISTS ix_clients_status ON public.clients(status);
CREATE INDEX IF NOT EXISTS ix_clients_full_name ON public.clients(full_name);
CREATE UNIQUE INDEX IF NOT EXISTS ix_clients_external_client_id
    ON public.clients(external_client_id);

ALTER TABLE public.clients ENABLE ROW LEVEL SECURITY;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.clients TO service_role;
GRANT SELECT ON TABLE public.agents TO service_role;

CREATE TABLE IF NOT EXISTS public.transactions (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_transaction_id TEXT,
    client_id UUID NOT NULL
        REFERENCES public.clients(client_id) ON DELETE RESTRICT,
    property_id INTEGER NOT NULL
        REFERENCES public.listings(listing_id) ON DELETE RESTRICT,
    agent_id VARCHAR(32) NOT NULL
        REFERENCES public.agents(agent_id) ON DELETE RESTRICT,
    transaction_type TEXT NOT NULL
        CHECK (transaction_type IN ('RESERVED', 'SOLD')),
    transaction_date TIMESTAMPTZ NOT NULL,
    amount NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (amount >= 0),
    status TEXT NOT NULL
        CHECK (status IN ('RESERVED', 'COMPLETED', 'CANCELLED')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.transactions
    ADD COLUMN IF NOT EXISTS external_transaction_id TEXT;
ALTER TABLE public.transactions
    DROP CONSTRAINT IF EXISTS transactions_client_id_key;
DROP INDEX IF EXISTS public.ix_transactions_client_id;
CREATE INDEX IF NOT EXISTS ix_transactions_client_id
    ON public.transactions(client_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_transactions_external_transaction_id
    ON public.transactions(external_transaction_id);

CREATE INDEX IF NOT EXISTS ix_transactions_property_id
    ON public.transactions(property_id);
CREATE INDEX IF NOT EXISTS ix_transactions_agent_id
    ON public.transactions(agent_id);
CREATE INDEX IF NOT EXISTS ix_transactions_status
    ON public.transactions(status);

DO $$
BEGIN
    IF to_regclass('public.documents') IS NOT NULL THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE '
                'ON TABLE public.documents TO service_role';
    END IF;
END;
$$;

ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.transactions TO service_role;

-- Backfill the sample clients only from matching existing Supabase agents.
UPDATE public.clients AS client
SET agent_id = assignment.agent_id
FROM (VALUES
    (1, 'AGT-0001'),
    (2, 'AGT-0002'),
    (3, 'AGT-0003'),
    (4, 'AGT-0004'),
    (5, 'AGT-0005'),
    (12, 'AGT-0001'),
    (14, 'AGT-0002')
) AS assignment(property_id, agent_id)
WHERE client.property_id = assignment.property_id
  AND client.agent_id IS NULL
  AND EXISTS (
      SELECT 1 FROM public.agents
      WHERE public.agents.agent_id = assignment.agent_id
  );

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.clients AS client
        LEFT JOIN public.agents AS agent ON agent.agent_id = client.agent_id
        WHERE client.agent_id IS NULL OR agent.agent_id IS NULL
    ) THEN
        RAISE EXCEPTION
            'Every client needs an existing agent_id; assign unmatched client rows before rerunning this script';
    END IF;
END;
$$;

INSERT INTO public.transactions (
    client_id,
    property_id,
    agent_id,
    transaction_type,
    transaction_date,
    amount,
    status,
    created_at,
    updated_at
)
SELECT
    client.client_id,
    client.property_id,
    client.agent_id,
    client.transaction_type,
    coalesce(client.transaction_date, client.created_at),
    greatest(coalesce(listing.price_total, 0), 0),
    CASE WHEN client.status = 'SOLD' THEN 'COMPLETED'
         WHEN client.status = 'CANCELLED' THEN 'CANCELLED'
         ELSE 'RESERVED' END,
    client.created_at,
    client.updated_at
FROM public.clients AS client
JOIN public.listings AS listing ON listing.listing_id = client.property_id
WHERE NOT EXISTS (
        SELECT 1
        FROM public.transactions AS existing
        WHERE existing.client_id = client.client_id
            AND existing.property_id = client.property_id
            AND existing.transaction_type = client.transaction_type
);

ALTER TABLE public.clients ALTER COLUMN agent_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_clients_agent_id_agents'
          AND conrelid = 'public.clients'::regclass
    ) THEN
        ALTER TABLE public.clients
            ADD CONSTRAINT fk_clients_agent_id_agents
            FOREIGN KEY (agent_id) REFERENCES public.agents(agent_id)
            ON DELETE RESTRICT;
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS ix_clients_agent_id ON public.clients(agent_id);

CREATE OR REPLACE FUNCTION public.sync_client_property_status()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    normalized_status TEXT;
BEGIN
    normalized_status := upper(replace(coalesce(NEW.status, ''), ' ', '_'));

    IF normalized_status NOT IN ('RESERVED', 'SOLD') THEN
        UPDATE public.clients
        SET status = 'CANCELLED', updated_at = now()
        WHERE property_id = NEW.listing_id;
        UPDATE public.transactions
        SET status = 'CANCELLED', updated_at = now()
        WHERE property_id = NEW.listing_id AND status = 'RESERVED';
    ELSE
        UPDATE public.clients
        SET transaction_type = normalized_status,
            status = normalized_status,
            updated_at = now()
        WHERE property_id = NEW.listing_id;
        UPDATE public.transactions
                SET status = 'COMPLETED',
            updated_at = now()
                WHERE property_id = NEW.listing_id
                    AND normalized_status = 'SOLD'
                    AND status = 'RESERVED';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sync_client_property_status ON public.listings;
CREATE TRIGGER trg_sync_client_property_status
AFTER UPDATE OF status ON public.listings
FOR EACH ROW
WHEN (OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION public.sync_client_property_status();

DROP FUNCTION IF EXISTS public.create_client_transaction(
    UUID, TEXT, TEXT, TEXT, INTEGER, VARCHAR, TEXT, TIMESTAMPTZ
);

CREATE OR REPLACE FUNCTION public.create_client_transaction(
    p_client_id UUID,
    p_full_name TEXT,
    p_location TEXT,
    p_phone_number TEXT,
    p_email TEXT,
    p_property_id INTEGER,
    p_agent_id VARCHAR(32),
    p_transaction_type TEXT,
    p_transaction_date TIMESTAMPTZ
)
RETURNS SETOF public.clients
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    current_property_status TEXT;
    current_agent_status TEXT;
    current_property_amount NUMERIC(14, 2);
    requested_status TEXT;
BEGIN
    requested_status := upper(replace(coalesce(p_transaction_type, ''), ' ', '_'));
    IF requested_status NOT IN ('RESERVED', 'SOLD') THEN
        RAISE EXCEPTION 'INVALID_TRANSACTION_TYPE' USING ERRCODE = '22023';
    END IF;

    SELECT upper(replace(coalesce(status, ''), ' ', '_')), price_total
    INTO current_property_status, current_property_amount
    FROM public.listings
    WHERE listing_id = p_property_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'PROPERTY_NOT_FOUND' USING ERRCODE = 'P0001';
    END IF;
    IF current_property_status <> 'AVAILABLE' THEN
        RAISE EXCEPTION 'PROPERTY_NOT_AVAILABLE' USING ERRCODE = 'P0001';
    END IF;

    SELECT upper(coalesce(status, ''))
    INTO current_agent_status
    FROM public.agents
    WHERE agent_id = p_agent_id
    FOR KEY SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'AGENT_NOT_FOUND' USING ERRCODE = 'P0001';
    END IF;
    IF current_agent_status <> 'ACTIVE' THEN
        RAISE EXCEPTION 'AGENT_NOT_ACTIVE' USING ERRCODE = 'P0001';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.clients WHERE property_id = p_property_id
    ) THEN
        RAISE EXCEPTION 'CLIENT_EXISTS' USING ERRCODE = 'P0001';
    END IF;

    INSERT INTO public.clients (
        client_id,
        full_name,
        location,
        phone_number,
        email,
        agent_id,
        property_id,
        transaction_type,
        transaction_date,
        status
    ) VALUES (
        p_client_id,
        p_full_name,
        p_location,
        p_phone_number,
        nullif(lower(trim(coalesce(p_email, ''))), ''),
        p_agent_id,
        p_property_id,
        requested_status,
        p_transaction_date,
        requested_status
    );

    UPDATE public.listings
    SET status = requested_status
    WHERE listing_id = p_property_id;

    INSERT INTO public.transactions (
        client_id,
        property_id,
        agent_id,
        transaction_type,
        transaction_date,
        amount,
        status
    ) VALUES (
        p_client_id,
        p_property_id,
        p_agent_id,
        requested_status,
        p_transaction_date,
        greatest(coalesce(current_property_amount, 0), 0),
        CASE WHEN requested_status = 'SOLD' THEN 'COMPLETED' ELSE 'RESERVED' END
    );

    RETURN QUERY
    SELECT * FROM public.clients WHERE client_id = p_client_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.rollback_client_transaction(
    p_client_id UUID,
    p_property_id INTEGER,
    p_transaction_type TEXT
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    current_property_status TEXT;
BEGIN
    SELECT upper(replace(coalesce(status, ''), ' ', '_'))
    INTO current_property_status
    FROM public.listings
    WHERE listing_id = p_property_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    IF current_property_status = upper(replace(p_transaction_type, ' ', '_'))
       AND EXISTS (
           SELECT 1 FROM public.clients
           WHERE client_id = p_client_id AND property_id = p_property_id
       ) THEN
        DELETE FROM public.transactions
        WHERE client_id = p_client_id AND property_id = p_property_id;
        DELETE FROM public.clients
        WHERE client_id = p_client_id AND property_id = p_property_id;
        UPDATE public.listings
        SET status = 'AVAILABLE'
        WHERE listing_id = p_property_id;
    END IF;
END;
$$;

REVOKE ALL ON FUNCTION public.create_client_transaction(
    UUID, TEXT, TEXT, TEXT, TEXT, INTEGER, VARCHAR, TEXT, TIMESTAMPTZ
) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.rollback_client_transaction(
    UUID, INTEGER, TEXT
) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.create_client_transaction(
    UUID, TEXT, TEXT, TEXT, TEXT, INTEGER, VARCHAR, TEXT, TIMESTAMPTZ
) TO service_role;
GRANT EXECUTE ON FUNCTION public.rollback_client_transaction(
    UUID, INTEGER, TEXT
) TO service_role;

UPDATE public.clients AS client
SET status = 'CANCELLED', updated_at = now()
FROM public.listings AS listing
WHERE listing.listing_id = client.property_id
    AND upper(replace(coalesce(listing.status, ''), ' ', '_'))
            NOT IN ('RESERVED', 'SOLD')
    AND client.status <> 'CANCELLED';

UPDATE public.transactions AS transaction
SET status = 'CANCELLED', updated_at = now()
FROM public.listings AS listing
WHERE listing.listing_id = transaction.property_id
    AND upper(replace(coalesce(listing.status, ''), ' ', '_'))
            NOT IN ('RESERVED', 'SOLD')
    AND transaction.status <> 'CANCELLED';

UPDATE public.clients AS client
SET transaction_type = upper(replace(listing.status, ' ', '_')),
    status = upper(replace(listing.status, ' ', '_')),
    updated_at = now()
FROM public.listings AS listing
WHERE listing.listing_id = client.property_id
  AND upper(replace(coalesce(listing.status, ''), ' ', '_'))
      IN ('RESERVED', 'SOLD')
  AND (
      client.transaction_type IS DISTINCT FROM upper(replace(listing.status, ' ', '_'))
      OR client.status IS DISTINCT FROM upper(replace(listing.status, ' ', '_'))
  );

UPDATE public.transactions AS transaction
SET status = 'COMPLETED',
    updated_at = now()
FROM public.listings AS listing
WHERE listing.listing_id = transaction.property_id
    AND upper(replace(coalesce(listing.status, ''), ' ', '_')) = 'SOLD'
    AND transaction.status = 'RESERVED';

-- Insert only for the supplied sample property IDs whose current cloud status
-- is RESERVED or SOLD. Available properties are deliberately excluded.
INSERT INTO public.clients (
    full_name,
    location,
    phone_number,
    agent_id,
    property_id,
    transaction_type,
    transaction_date,
    status
)
SELECT
    CASE listing.listing_id
        WHEN 1 THEN 'Michael Ortigas'
        WHEN 2 THEN 'Andrea Villanueva'
        WHEN 3 THEN 'Daniel Reyes'
        WHEN 4 THEN 'Sofia Mendoza'
        WHEN 5 THEN 'Gabriel Santos'
        WHEN 12 THEN 'Isabella Cruz'
        WHEN 14 THEN 'Rafael Dela Cruz'
    END,
    CASE listing.listing_id
        WHEN 1 THEN 'Makati City'
        WHEN 2 THEN 'Taguig City'
        WHEN 3 THEN 'Quezon City'
        WHEN 4 THEN 'Pasig City'
        WHEN 5 THEN 'Manila'
        WHEN 12 THEN 'Taguig City'
        WHEN 14 THEN 'Makati City'
    END,
    CASE listing.listing_id
        WHEN 1 THEN '09170000001'
        WHEN 2 THEN '09170000002'
        WHEN 3 THEN '09170000003'
        WHEN 4 THEN '09170000004'
        WHEN 5 THEN '09170000005'
        WHEN 12 THEN '09170000012'
        WHEN 14 THEN '09170000014'
    END,
    assigned_agent.agent_id,
    listing.listing_id,
    upper(replace(listing.status, ' ', '_')),
    CASE listing.listing_id
        WHEN 1 THEN '2026-08-12T10:00:00+08:00'::timestamptz
        WHEN 2 THEN '2026-08-19T14:30:00+08:00'::timestamptz
        WHEN 3 THEN '2026-07-03T09:15:00+08:00'::timestamptz
        WHEN 4 THEN '2026-07-18T11:45:00+08:00'::timestamptz
        WHEN 5 THEN '2026-08-27T13:00:00+08:00'::timestamptz
        WHEN 12 THEN '2026-09-02T15:20:00+08:00'::timestamptz
        WHEN 14 THEN '2026-09-08T10:10:00+08:00'::timestamptz
    END,
        upper(replace(listing.status, ' ', '_'))
FROM public.listings AS listing
JOIN public.agents AS assigned_agent
    ON assigned_agent.agent_id = CASE listing.listing_id
            WHEN 1 THEN 'AGT-0001'
            WHEN 2 THEN 'AGT-0002'
            WHEN 3 THEN 'AGT-0003'
            WHEN 4 THEN 'AGT-0004'
            WHEN 5 THEN 'AGT-0005'
            WHEN 12 THEN 'AGT-0001'
            WHEN 14 THEN 'AGT-0002'
    END
WHERE listing.listing_id IN (1, 2, 3, 4, 5, 12, 14)
    AND upper(replace(coalesce(listing.status, ''), ' ', '_')) IN ('RESERVED', 'SOLD')
    AND upper(coalesce(assigned_agent.status, '')) = 'ACTIVE'
ON CONFLICT (property_id) DO NOTHING;

INSERT INTO public.transactions (
    client_id,
    property_id,
    agent_id,
    transaction_type,
    transaction_date,
    amount,
    status
)
SELECT
    client.client_id,
    client.property_id,
    client.agent_id,
    client.transaction_type,
    coalesce(client.transaction_date, now()),
    greatest(coalesce(listing.price_total, 0), 0),
    CASE WHEN client.status = 'SOLD' THEN 'COMPLETED'
         WHEN client.status = 'CANCELLED' THEN 'CANCELLED'
         ELSE 'RESERVED' END
FROM public.clients AS client
JOIN public.listings AS listing ON listing.listing_id = client.property_id
WHERE NOT EXISTS (
        SELECT 1
        FROM public.transactions AS existing
        WHERE existing.client_id = client.client_id
            AND existing.property_id = client.property_id
            AND existing.transaction_type = client.transaction_type
);