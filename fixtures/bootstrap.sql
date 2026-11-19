create extension if not exists pgcrypto;
create role anon nologin;
create role authenticated nologin;
create role authenticator noinherit login password 'local-only';
grant anon to authenticator;
grant authenticated to authenticator;
create schema if not exists auth;
create or replace function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;
create table if not exists public.synthetic_users(id uuid primary key, label text unique not null);
insert into public.synthetic_users values ('00000000-0000-0000-0000-0000000000a1','USER_A'), ('00000000-0000-0000-0000-0000000000b1','USER_B') on conflict (id) do update set label = excluded.label;
create table if not exists public.health_daily (
 id uuid primary key default gen_random_uuid(), user_id uuid not null, date date not null,
 steps integer, distance_km double precision, calories double precision,
 exercise_minutes integer, active_minutes integer, updated_at timestamptz default now(), unique(user_id,date)
);
alter table public.health_daily enable row level security;
grant usage on schema public to anon, authenticated;
grant select, insert, update on public.health_daily to anon, authenticated;
