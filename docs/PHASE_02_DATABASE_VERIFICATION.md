# Phase 02 Database Verification

## Live verification result — 2026-09-18

### PASS

- JWT/JWKS endpoint was reachable using the configured backend value; no credentials or tokens were logged.
- Invalid profile role was rejected.
- Invalid availability time and overlapping availability were rejected.
- Duplicate doctor leave was rejected.
- Active appointment overlap was rejected for both the same doctor and the same patient across two doctors.
- A correctly cancelled appointment released its doctor slot at the database constraint level.
- Invalid appointment duration and invalid appointment status were rejected.
- Authenticated-session RLS checks passed: a patient could read only their own profile and involved note; another patient could not read it; the involved doctor could read it; a different doctor could not read the appointment; and an admin could not read the visit note.
- Temporary verification Auth users and dependent records were deleted after testing. The owner Auth test patient was not accessed or deleted.

### NOT EXECUTED

- Direct catalog-policy introspection was not available through the configured REST/API credentials. Policy definitions were reviewed from the applied migration, and their critical behavior was verified with real authenticated sessions as listed above.

### FAIL

- None.

Run migrations `001` through `005` in order in the Supabase SQL Editor before performing these checks. Use throwaway users created through Supabase Auth; never insert fake password hashes into `auth.users`.

## Constraint checks

1. Attempt `insert into public.profiles (...) values (..., 'invalid_role', ...)`; PostgreSQL must reject the role enum.
2. For one valid doctor, insert availability with identical start/end times and then overlapping times on the same weekday. The check constraint and GiST exclusion constraint must each reject invalid rows.
3. Insert the same `(doctor_id, leave_date)` twice. The unique constraint must reject the second row.
4. Create two 30-minute `pending`/`confirmed` appointments for one doctor with overlapping `tstzrange` values. The doctor exclusion constraint must reject the second insert. Change the first status to `cancelled` with `cancelled_at`; the previously blocked slot should then be insertable.
5. Repeat with one patient and two different doctors at the same time. The patient exclusion constraint must reject the second insert.
6. Attempt an appointment with a 29- or 31-minute duration and an invalid status literal. PostgreSQL must reject both.

## RLS/privacy checks

Use the Supabase client/session context for a patient, an involved doctor, an unrelated doctor, and an admin. Confirm that each user can select only their own/involved profile data and appointments. Confirm the involved patient and doctor can select a visit note; the unrelated doctor and admin receive zero rows. Confirm a patient cannot insert/update a visit note and an admin cannot select it.

## Structural checks

```sql
select tablename, rowsecurity from pg_tables
where schemaname = 'public'
  and tablename in ('profiles','doctors','doctor_availability','doctor_leaves','appointments','visit_notes','audit_logs','automation_events')
order by tablename;

select conname, pg_get_constraintdef(oid)
from pg_constraint
where conrelid = 'public.appointments'::regclass
order by conname;
```

The first query must show `rowsecurity = true` for every listed table. The second must show the 30-minute duration check and both active-appointment exclusion constraints.
