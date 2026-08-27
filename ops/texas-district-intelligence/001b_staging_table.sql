-- Staging table for bulk-loading AskTED personnel rows into district_contacts.
--
-- Applied directly to fdnncloyxjsxwdhpfkjj on 2026-08-27, ahead of this file
-- landing in the repo -- recorded here now so the migration set matches what
-- is actually running in production. Safe to re-run.
--
-- Deliberately unconstrained: every column is `text`, no PK, no unique, no FK.
-- A CSV/JSON bulk load cannot fail partway through on a type cast or a bad
-- district id, because there is nothing here that can reject a row. All
-- validation (district FK, region-required-for-ESC, natural_key dedup) happens
-- once, in 003_promote_staging.sql, on the way into the real district_contacts
-- table -- not here.

create table if not exists public.district_contacts_staging (
  org_level      text,
  district_id    text,
  region_number  text,
  campus_id      text,
  campus_name    text,
  full_name      text,
  first_name     text,
  last_name      text,
  role_title     text,
  role_code      text,
  email          text,
  phone          text,
  natural_key    text,
  source_scope   text,
  loaded_at      timestamptz default now()
);

comment on table public.district_contacts_staging is
  'Unconstrained landing table for bulk AskTED loads. Never queried by the app -- promote into district_contacts via 003_promote_staging.sql, then truncate.';

-- ---------------------------------------------------------------------------
-- RLS, matching 001_contact_layer.sql's pattern: no anon grant anywhere,
-- authenticated is read-only, service_role has full access. Same rationale --
-- explicit grants, not Supabase's ambient ALTER DEFAULT PRIVILEGES.
-- ---------------------------------------------------------------------------
alter table public.district_contacts_staging enable row level security;

drop policy if exists district_contacts_staging_service_all on public.district_contacts_staging;
drop policy if exists district_contacts_staging_auth_read   on public.district_contacts_staging;

create policy district_contacts_staging_service_all on public.district_contacts_staging
  for all to service_role using (true) with check (true);
create policy district_contacts_staging_auth_read on public.district_contacts_staging
  for select to authenticated using (true);

revoke all on public.district_contacts_staging from anon, authenticated;
grant select on public.district_contacts_staging to authenticated;
grant all    on public.district_contacts_staging to service_role;
