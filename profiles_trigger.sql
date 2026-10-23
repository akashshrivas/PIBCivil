-- profiles_trigger.sql
-- ---------------------------------------------------------------
-- Matches YOUR existing table: public.profiles(id, display_name,
-- preferred_language, created_at). It does NOT create the table and
-- does NOT touch your existing RLS policy.
--
-- BEFORE running: run the "triggers on auth.users" check query from my
-- last message. If it returns a row that already creates profiles,
-- do NOT run this file (you would get two triggers doing the same job).
--
-- Run in: Supabase dashboard > SQL Editor > New query > Run.
-- ---------------------------------------------------------------

-- 1. Function that creates a profile row for every new user.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer          -- runs with the owner's rights, so it can insert
set search_path = ''      -- safety setting: stops look-alike table tricks
as $$
begin
  insert into public.profiles (id, display_name)
  values (
    new.id,
    -- Google sign-in provides "full_name" or "name"; email-link users
    -- have neither, so display_name stays empty (null) for them.
    coalesce(
      new.raw_user_meta_data ->> 'full_name',
      new.raw_user_meta_data ->> 'name'
    )
  )
  -- If a profile somehow already exists, do nothing instead of failing.
  on conflict (id) do nothing;

  return new;
exception
  when others then
    -- IMPORTANT: if anything goes wrong creating the profile (for example
    -- a required column without a default), we log a warning but still
    -- let the sign-up succeed. Otherwise users would see
    -- "Database error saving new user" and could not register at all.
    raise warning 'handle_new_user failed for %: %', new.id, sqlerrm;
    return new;
end;
$$;

-- Nobody should be able to call this function directly from the API.
revoke execute on function public.handle_new_user() from public, anon, authenticated;

-- 2. Run the function every time a new user signs up.
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- 3. One-time backfill: create profiles for users who signed up before
--    this trigger existed (your profiles table is currently empty).
insert into public.profiles (id, display_name)
select
  u.id,
  coalesce(u.raw_user_meta_data ->> 'full_name', u.raw_user_meta_data ->> 'name')
from auth.users u
on conflict (id) do nothing;

-- 4. Check the result: you should see one row per existing user.
-- select * from public.profiles;
