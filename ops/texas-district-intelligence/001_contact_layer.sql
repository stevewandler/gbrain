-- Texas District Intelligence — narrow AskTED contact layer
--
-- Target:  Supabase project texas-esc-districts (fdnncloyxjsxwdhpfkjj)
-- Status:  APPROVED 2026-08-26 by the brain owner; applied to fdnncloyxjsxwdhpfkjj.
--          Additive only. Apply order: this file, then the loader (see README.md).
--          Safe to re-run: verified idempotent across 3 consecutive runs.
--
-- Scope decision (2026-08-26): ship the narrow contact layer now so the team gets
-- the superintendent list, rather than waiting on the six-blocker governed
-- architecture remediation. This migration is ADDITIVE ONLY — it creates new
-- tables and touches nothing existing, so the governed model can absorb it later.
--
-- Design rules carried over from the 2026-08-21 audit:
--   * "Missing is not zero, closed, vacant, or ended." A person who stops
--     appearing in a run gets a stale last_seen_run_id, never a fabricated
--     end date.
--   * Every row is traceable to the run that produced it.
--   * AskTED is the official dated directory baseline, not the automatic
--     winner for every field. district_websites can be fresher on leadership.

-- No BEGIN/COMMIT here: the caller supplies the transaction.
-- Supabase apply_migration wraps it; with psql use `psql -1 -f`.

-- ---------------------------------------------------------------------------
-- Provenance: one row per ingest occurrence.
-- ---------------------------------------------------------------------------
create table if not exists public.source_runs (
  run_id            uuid primary key default gen_random_uuid(),
  source_name       varchar(64)  not null,          -- 'askted_personnel', 'askted_organization'
  source_date       date,                           -- the date the SOURCE claims, not fetch time
  retrieved_at      timestamptz  not null default now(),
  artifact_filename text,
  artifact_sha256   char(64),                       -- checksum of the exact bytes parsed
  parser_version    varchar(32)  not null,
  row_count_raw     integer,                        -- rows in the file
  row_count_loaded  integer,                        -- rows that survived normalization
  selected_scope    text,                           -- roles/orgs requested from AskTED
  notes             text,
  created_at        timestamptz  not null default now()
);

comment on table public.source_runs is
  'Append-only ingest log. One row per retrieval occurrence. artifact_sha256 pins the exact bytes parsed so a run is reproducible.';

create index if not exists source_runs_source_name_date_idx
  on public.source_runs (source_name, source_date desc);

-- ---------------------------------------------------------------------------
-- Contacts: the flat, queryable table the revenue team actually needs.
-- ---------------------------------------------------------------------------
create table if not exists public.district_contacts (
  contact_id        bigserial primary key,

  -- Organization. AskTED personnel rows are district, campus, or ESC scoped.
  org_level         varchar(16) not null
                      check (org_level in ('district','campus','esc')),
  district_id       varchar(16) references public.districts (district_id),
  region_number     integer     references public.escs (region_number),
  campus_id         varchar(16),      -- TEA campus number when org_level='campus'
  campus_name       varchar(255),     -- no campus table yet; see README follow-ups

  -- Person + role
  full_name         varchar(255) not null,
  first_name        varchar(128),
  last_name         varchar(128),
  role_title        varchar(255) not null,   -- verbatim AskTED title, never rewritten
  role_code         varchar(48),             -- normalized; see role_code_ref
  email             varchar(255),
  phone             varchar(64),

  -- Idempotency + history
  natural_key       char(64) not null,       -- sha256 of normalized identity tuple
  first_seen_run_id uuid not null references public.source_runs (run_id),
  last_seen_run_id  uuid not null references public.source_runs (run_id),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),

  -- An org_level='district' row must name a district; 'esc' must name a region.
  constraint district_contacts_org_ref_ck check (
    (org_level = 'district' and district_id is not null)
    or (org_level = 'campus'   and district_id is not null)
    or (org_level = 'esc'      and region_number is not null)
  ),
  constraint district_contacts_natural_key_uq unique (natural_key)
);

comment on table public.district_contacts is
  'AskTED personnel directory, one row per person-role-org observation. Upsert on natural_key; a row absent from a newer run keeps its old last_seen_run_id rather than being deleted or marked ended.';
comment on column public.district_contacts.role_title is
  'Verbatim AskTED title. Never normalized in place — role_code carries the normalization so the original is always recoverable.';
comment on column public.district_contacts.last_seen_run_id is
  'Most recent run that still contained this person-role-org. Staleness here means "not in the latest export", NOT "vacated the role".';

create index if not exists district_contacts_district_idx
  on public.district_contacts (district_id);
create index if not exists district_contacts_role_code_idx
  on public.district_contacts (role_code);
create index if not exists district_contacts_region_idx
  on public.district_contacts (region_number);
create index if not exists district_contacts_last_seen_idx
  on public.district_contacts (last_seen_run_id);
-- Plain btree on the folded name: pg_trgm is NOT installed on this project
-- (verified 2026-08-26), so a gin_trgm_ops index would fail on apply. Exact and
-- prefix lookup work here; if fuzzy name matching is needed later, install
-- pg_trgm into the extensions schema first and add the gin index then.
create index if not exists district_contacts_name_lower_idx
  on public.district_contacts (lower(full_name));

-- ---------------------------------------------------------------------------
-- Role normalization. Deliberately a table, not a CHECK constraint: AskTED
-- title strings vary and we want to add mappings without a migration.
-- ---------------------------------------------------------------------------
create table if not exists public.role_code_ref (
  role_code    varchar(48) primary key,
  label        varchar(128) not null,
  seniority    smallint,        -- 1 = district cabinet, 2 = director, 3 = campus, 9 = other
  is_priority  boolean not null default false
);

comment on table public.role_code_ref is
  'Normalized role taxonomy. is_priority marks the roles the revenue team works. NOTE: library_media is priority but AskTED carries NO district-level library role — it exists only at ESC scope. Do not read an empty district library_media set as "no librarian".';

-- Source-role -> role_code mapping lives in the DATABASE, not in loader code, so
-- a new AskTED title string is a one-row insert rather than a migration.
-- Seeded from the full inventory profiled 2026-08-26: all 43 district roles and
-- all 94 ESC roles present in the exports are mapped explicitly. Nothing falls
-- through to 'other' by accident.
create table if not exists public.askted_role_map (
  source_scope varchar(16)  not null check (source_scope in ('district','esc')),
  source_role  varchar(128) not null,
  role_code    varchar(48)  not null references public.role_code_ref (role_code),
  primary key (source_scope, source_role)
);

comment on table public.askted_role_map is
  'Verbatim AskTED Role string -> role_code. A role present in a new export but absent here loads as role_code = other and shows up in the unmapped-role review query.';

-- Postgres has no ADD CONSTRAINT IF NOT EXISTS, so guard it: this file must be
-- safe to re-run (verified against a throwaway PG16 cluster, 2026-08-26).
-- NOT VALID so an unmapped title loads as 'other' without blocking the run.
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'district_contacts_role_code_fk'
      and conrelid = 'public.district_contacts'::regclass
  ) then
    alter table public.district_contacts
      add constraint district_contacts_role_code_fk
      foreign key (role_code) references public.role_code_ref (role_code)
      not valid;
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- Current-state views. Reproducible: they read evidence, they don't store it.
-- ---------------------------------------------------------------------------
create or replace view public.v_latest_run as
  select distinct on (source_name) run_id, source_name, source_date, retrieved_at
  from public.source_runs
  order by source_name, source_date desc nulls last, retrieved_at desc;

create or replace view public.v_current_superintendents as
  select
    d.district_id,
    d.district_name,
    d.region_number,
    d.county_name,
    d.enrollment_oct2025,
    c.full_name       as superintendent,
    c.email,
    c.phone,
    c.role_title,
    r.source_date     as as_of,
    (c.last_seen_run_id = r.run_id) as in_latest_run
  from public.districts d
  left join public.district_contacts c
    on c.district_id = d.district_id
   and c.role_code   = 'superintendent'
   and c.org_level   = 'district'
  left join public.v_latest_run r
    on r.source_name = 'askted_personnel'
  order by d.district_name;

comment on view public.v_current_superintendents is
  'One row per Texas district with its AskTED superintendent. in_latest_run = false means the person was not in the newest export — investigate, do not assume the seat is vacant.';

create or replace view public.v_district_contact_coverage as
  select
    d.district_id,
    d.district_name,
    d.region_number,
    d.enrollment_oct2025,
    count(c.contact_id)                                              as contacts,
    count(c.contact_id) filter (where rc.is_priority)                as priority_contacts,
    count(c.contact_id) filter (where c.role_code = 'superintendent') as superintendents,
    count(c.contact_id) filter (where c.email is not null)           as with_email
  from public.districts d
  left join public.district_contacts c on c.district_id = d.district_id
  left join public.role_code_ref   rc on rc.role_code   = c.role_code
  group by 1,2,3,4;

comment on view public.v_district_contact_coverage is
  'Per-district contact coverage. Districts with contacts = 0 are the gap list to chase, not evidence that the district has no staff.';

-- ---------------------------------------------------------------------------
-- RLS. Directory data is public-record, but these tables carry named
-- individuals with work email and phone: no anon read.
-- ---------------------------------------------------------------------------
alter table public.source_runs        enable row level security;
alter table public.district_contacts  enable row level security;
alter table public.role_code_ref      enable row level security;
alter table public.askted_role_map    enable row level security;

drop policy if exists source_runs_service_all       on public.source_runs;
drop policy if exists district_contacts_service_all on public.district_contacts;
drop policy if exists role_code_ref_service_all     on public.role_code_ref;
drop policy if exists askted_role_map_service_all   on public.askted_role_map;

create policy source_runs_service_all       on public.source_runs
  for all to service_role using (true) with check (true);
create policy district_contacts_service_all on public.district_contacts
  for all to service_role using (true) with check (true);
create policy role_code_ref_service_all     on public.role_code_ref
  for all to service_role using (true) with check (true);
create policy askted_role_map_service_all   on public.askted_role_map
  for all to service_role using (true) with check (true);

-- Authenticated staff get read-only. No anon grant anywhere.
drop policy if exists district_contacts_auth_read on public.district_contacts;
drop policy if exists role_code_ref_auth_read     on public.role_code_ref;
drop policy if exists source_runs_auth_read       on public.source_runs;
drop policy if exists askted_role_map_auth_read     on public.askted_role_map;

create policy district_contacts_auth_read on public.district_contacts
  for select to authenticated using (true);
create policy role_code_ref_auth_read on public.role_code_ref
  for select to authenticated using (true);
create policy source_runs_auth_read on public.source_runs
  for select to authenticated using (true);
create policy askted_role_map_auth_read on public.askted_role_map
  for select to authenticated using (true);

-- Grants are EXPLICIT, not inherited from Supabase's ALTER DEFAULT PRIVILEGES.
-- Relying on ambient default privileges is how a green test run ends up
-- depending on cluster state that differs between environments — the same class
-- of finding that blocked the earlier governed package. Say it out loud instead.
revoke all on public.district_contacts from anon, authenticated;
revoke all on public.source_runs       from anon, authenticated;
revoke all on public.role_code_ref     from anon, authenticated;
revoke all on public.askted_role_map   from anon, authenticated;

grant select on public.district_contacts to authenticated;
grant select on public.source_runs       to authenticated;
grant select on public.role_code_ref     to authenticated;
grant select on public.askted_role_map   to authenticated;

grant all on public.district_contacts to service_role;
grant all on public.source_runs       to service_role;
grant all on public.role_code_ref     to service_role;
grant all on public.askted_role_map   to service_role;
grant usage, select on sequence public.district_contacts_contact_id_seq to service_role;

-- Views inherit nothing automatically; grant them the same way.
grant select on public.v_latest_run                 to authenticated, service_role;
grant select on public.v_current_superintendents    to authenticated, service_role;
grant select on public.v_district_contact_coverage  to authenticated, service_role;
revoke all on public.v_latest_run                from anon;
revoke all on public.v_current_superintendents    from anon;
revoke all on public.v_district_contact_coverage  from anon;

