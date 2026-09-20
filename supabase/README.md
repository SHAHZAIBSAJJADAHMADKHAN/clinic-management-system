# Supabase Database and Access-Control Foundation

Contents:

- `migrations/` for ordered PostgreSQL migrations
- `policies/` for RLS policy documentation or supporting SQL
- `seed/` for non-production development data

The ordered migrations now implement profiles, doctors, availability, leave days, appointments, visit notes, audit logs, automation/outbox events, indexes, constraints, restrictive RLS policies, and patient-only profile creation from Supabase Auth. Apply them in filename order through the Supabase SQL Editor. See `../docs/DATABASE.md` and `../docs/PHASE_02_DATABASE_VERIFICATION.md` before applying them.
