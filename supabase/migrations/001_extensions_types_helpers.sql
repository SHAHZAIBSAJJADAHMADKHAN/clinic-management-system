-- Shared extensions, constrained domain types, and timestamp helper.
create extension if not exists pgcrypto;
create extension if not exists btree_gist;

create type public.app_role as enum ('patient', 'doctor', 'admin');
create type public.appointment_status as enum ('pending', 'confirmed', 'rejected', 'cancelled', 'completed', 'no_show');
create type public.automation_event_status as enum ('pending', 'processing', 'processed', 'failed');

create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
