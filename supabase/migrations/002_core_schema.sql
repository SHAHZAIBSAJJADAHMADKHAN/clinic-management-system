-- Core application schema. Auth identities remain owned by Supabase in auth.users.
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null check (char_length(trim(full_name)) between 1 and 200),
  email text not null check (char_length(trim(email)) between 3 and 320),
  phone text,
  role public.app_role not null default 'patient',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.doctors (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null unique references public.profiles(id) on delete restrict,
  specialty text not null check (char_length(trim(specialty)) between 1 and 150),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.doctor_availability (
  id uuid primary key default gen_random_uuid(),
  doctor_id uuid not null references public.doctors(id) on delete cascade,
  day_of_week smallint not null check (day_of_week between 0 and 6),
  start_time time not null,
  end_time time not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (end_time > start_time),
  exclude using gist (
    doctor_id with =,
    day_of_week with =,
    int4range(
      (extract(epoch from start_time) / 60)::integer,
      (extract(epoch from end_time) / 60)::integer,
      '[)'
    ) with &&
  )
);

create table public.doctor_leaves (
  id uuid primary key default gen_random_uuid(),
  doctor_id uuid not null references public.doctors(id) on delete cascade,
  leave_date date not null,
  reason text check (reason is null or char_length(reason) <= 500),
  created_at timestamptz not null default now(),
  unique (doctor_id, leave_date)
);

create table public.appointments (
  id uuid primary key default gen_random_uuid(),
  patient_profile_id uuid not null references public.profiles(id) on delete restrict,
  doctor_id uuid not null references public.doctors(id) on delete restrict,
  start_at timestamptz not null,
  end_at timestamptz not null,
  status public.appointment_status not null default 'pending',
  rejection_reason text check (rejection_reason is null or char_length(rejection_reason) <= 500),
  cancellation_reason text check (cancellation_reason is null or char_length(cancellation_reason) <= 500),
  cancelled_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (end_at = start_at + interval '30 minutes'),
  check ((status <> 'cancelled') or cancelled_at is not null),
  exclude using gist (
    doctor_id with =,
    tstzrange(start_at, end_at, '[)') with &&
  ) where (status in ('pending', 'confirmed')),
  exclude using gist (
    patient_profile_id with =,
    tstzrange(start_at, end_at, '[)') with &&
  ) where (status in ('pending', 'confirmed'))
);

create table public.visit_notes (
  id uuid primary key default gen_random_uuid(),
  appointment_id uuid not null unique references public.appointments(id) on delete restrict,
  doctor_id uuid not null references public.doctors(id) on delete restrict,
  patient_profile_id uuid not null references public.profiles(id) on delete restrict,
  note_text text not null check (char_length(trim(note_text)) between 1 and 10000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  actor_profile_id uuid references public.profiles(id) on delete set null,
  action text not null check (char_length(trim(action)) between 1 and 100),
  entity_type text not null check (char_length(trim(entity_type)) between 1 and 100),
  entity_id uuid not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table public.automation_events (
  id uuid primary key default gen_random_uuid(),
  event_type text not null check (char_length(trim(event_type)) between 1 and 100),
  aggregate_type text not null check (char_length(trim(aggregate_type)) between 1 and 100),
  aggregate_id uuid not null,
  recipient_profile_id uuid references public.profiles(id) on delete set null,
  recipient_email text,
  payload jsonb not null default '{}'::jsonb,
  status public.automation_event_status not null default 'pending',
  attempt_count integer not null default 0 check (attempt_count >= 0),
  available_at timestamptz not null default now(),
  processed_at timestamptz,
  deduplication_key text not null unique check (char_length(trim(deduplication_key)) between 1 and 200),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
