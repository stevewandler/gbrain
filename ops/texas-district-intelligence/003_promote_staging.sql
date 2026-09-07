-- Promote bulk-imported AskTED contacts from staging into district_contacts.
--
-- Run AFTER the rows are in public.district_contacts_staging. This step is
-- transport-agnostic -- it doesn't care whether staging was filled via a
-- dashboard CSV import, a scoped psql role, or an HTTPS relay (see README.md
-- "How the 2026-08-27 load actually moved data" for what was used and why).
--
-- Safe to run repeatedly: the insert upserts on natural_key, so re-promoting the
-- same staging content is a no-op apart from touching last_seen_run_id. Rows
-- already loaded by the batch loader collapse into the same natural_key because
-- both paths hash the identical tuple.
--
-- Nothing is deleted and nothing is validated destructively: rows that fail the
-- district FK check are simply not promoted, and the reject query below names
-- them so they can be reconciled rather than silently lost.

-- ---------------------------------------------------------------------------
-- 1. Promote.
-- ---------------------------------------------------------------------------
insert into public.district_contacts (
  org_level, district_id, region_number, campus_id, campus_name,
  full_name, first_name, last_name, role_title, role_code, email, phone,
  natural_key, first_seen_run_id, last_seen_run_id
)
select
  s.org_level,
  nullif(s.district_id, ''),
  nullif(s.region_number, '')::int,
  nullif(s.campus_id, ''),
  nullif(s.campus_name, ''),
  s.full_name,
  nullif(s.first_name, ''),
  nullif(s.last_name, ''),
  s.role_title,
  coalesce(rc.role_code, 'other'),   -- fall back rather than reject on a new code
  nullif(s.email, ''),
  nullif(s.phone, ''),
  s.natural_key,
  r.run_id,
  r.run_id
from (
  -- Collapse any duplicate natural_key inside staging: ON CONFLICT DO UPDATE
  -- cannot touch the same row twice in one statement (SQLSTATE 21000).
  select distinct on (natural_key) *
  from public.district_contacts_staging
  order by natural_key, nullif(email,'') nulls last, nullif(phone,'') nulls last
) s
join public.source_runs r
  on r.source_name = case when s.source_scope = 'esc'
                          then 'askted_personnel_esc'
                          else 'askted_personnel' end
left join public.role_code_ref rc on rc.role_code = s.role_code
where
  -- FK guard: promote only rows whose district exists, so one unknown id cannot
  -- abort the whole promote. Rejects are reported in step 2.
  (s.org_level = 'esc' or exists (
     select 1 from public.districts d where d.district_id = nullif(s.district_id, '')))
  -- Region must resolve for ESC rows (district_contacts_org_ref_ck).
  and (s.org_level <> 'esc' or nullif(s.region_number, '') is not null)
on conflict (natural_key) do update set
  last_seen_run_id = excluded.last_seen_run_id,
  email            = coalesce(excluded.email, public.district_contacts.email),
  phone            = coalesce(excluded.phone, public.district_contacts.phone),
  role_title       = excluded.role_title,
  role_code        = excluded.role_code,
  updated_at       = now();

-- ---------------------------------------------------------------------------
-- 2. Reject report — run this and expect ZERO rows.
-- ---------------------------------------------------------------------------
-- select s.source_scope, s.district_id, s.full_name, s.role_title,
--        case
--          when s.org_level <> 'esc' and not exists (
--            select 1 from public.districts d where d.district_id = nullif(s.district_id,''))
--            then 'district_id not in districts'
--          when s.org_level = 'esc' and nullif(s.region_number,'') is null
--            then 'esc row without region_number'
--        end as reject_reason
-- from public.district_contacts_staging s
-- where (s.org_level <> 'esc' and not exists (
--          select 1 from public.districts d where d.district_id = nullif(s.district_id,'')))
--    or (s.org_level = 'esc' and nullif(s.region_number,'') is null);

-- ---------------------------------------------------------------------------
-- 3. Reconcile, then clear staging.
-- ---------------------------------------------------------------------------
-- select
--   (select count(*) from public.district_contacts_staging) as staged,
--   (select count(*) from public.district_contacts)         as live,
--   (select count(*) from public.district_contacts where role_code = 'other') as unmapped;
--
-- Expect live = distinct natural_key in staging (minus any rejects). Then:
-- truncate public.district_contacts_staging;
--
-- Finally record what actually landed, so row_count_raw vs row_count_loaded
-- tells the truth about the 11,114 nameless rows that were never loaded:
-- update public.source_runs set row_count_loaded = (
--   select count(*) from public.district_contacts c
--   where c.last_seen_run_id = source_runs.run_id)
-- where source_name in ('askted_personnel','askted_personnel_esc');
