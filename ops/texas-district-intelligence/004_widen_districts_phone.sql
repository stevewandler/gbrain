-- Widen districts.phone to fit AskTED phone numbers with an extension.
--
-- Discovered loading the AskTED organization file (2026-08-27): 250 of 1,216
-- districts (20%) have a phone formatted like "(432) 523-3640 ext:1756" (up
-- to 23 chars), which does not fit the existing varchar(20). Truncating would
-- silently drop the extension for a fifth of all districts, so widen the
-- column instead of the data. Pure widen: cannot invalidate any existing
-- value, no data migration needed, safe to re-run.

do $$
begin
  if (select character_maximum_length from information_schema.columns
      where table_schema = 'public' and table_name = 'districts' and column_name = 'phone') < 40
  then
    alter table public.districts alter column phone type varchar(40);
  end if;
end $$;
