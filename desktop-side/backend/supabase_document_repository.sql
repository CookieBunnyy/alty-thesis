-- Run in the Supabase SQL Editor to align the existing legacy documents table
-- with the desktop repository metadata upsert contract.

ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS document_name TEXT,
    ADD COLUMN IF NOT EXISTS folder_id INTEGER,
    ADD COLUMN IF NOT EXISTS related_party_id INTEGER,
    ADD COLUMN IF NOT EXISTS related_party_name TEXT,
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS storage_bucket TEXT,
    ADD COLUMN IF NOT EXISTS file_hash TEXT,
    ADD COLUMN IF NOT EXISTS property_listing_id INTEGER,
    ADD COLUMN IF NOT EXISTS property_listing_external_id TEXT,
    ADD COLUMN IF NOT EXISTS property_listing_title TEXT,
    ADD COLUMN IF NOT EXISTS transaction_reference TEXT,
    ADD COLUMN IF NOT EXISTS related_party_external_id TEXT,
    ADD COLUMN IF NOT EXISTS uploaded_by INTEGER,
    ADD COLUMN IF NOT EXISTS confirmed_by INTEGER,
    ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS archived_by INTEGER,
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS rejected_by INTEGER,
    ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS duplicate_of_id INTEGER;

ALTER TABLE public.documents
    ALTER COLUMN folder_name DROP NOT NULL;

UPDATE public.documents
SET document_name = coalesce(
    nullif(document_name, ''),
    nullif(title, ''),
    nullif(file_name, '')
)
WHERE document_name IS NULL OR document_name = '';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.documents
        GROUP BY document_id, version
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Duplicate document_id/version rows exist; resolve them before enabling repository upserts';
    END IF;
END;
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_document_id_version
    ON public.documents(document_id, version);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.documents TO service_role;
NOTIFY pgrst, 'reload schema';