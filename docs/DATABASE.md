# Database Design

## Tables and relationships

- `profiles` extends Supabase `auth.users` with application identity, a constrained role, and active status.
- `doctors` is a one-to-one extension of a `doctor` profile.
- `doctor_availability` stores recurring weekly intervals; `doctor_leaves` stores unique date exceptions.
- `appointments` links one patient profile to one doctor and stores UTC-safe `timestamptz` intervals.
- `visit_notes` links to one appointment and repeats its doctor and patient references for explicit privacy checks.
- `audit_logs` is append-oriented and excludes private note content by convention.
- `automation_events` is a transactional-outbox foundation with retry fields and a unique deduplication key.

## Integrity strategy

All application roles are PostgreSQL enum values: `patient`, `doctor`, and `admin`. Triggers ensure a doctor record references a doctor profile and prevent that profile from being demoted while linked to a doctor record. Appointment triggers require a patient profile.

Appointment duration is constrained to exactly 30 minutes. Two partial PostgreSQL exclusion constraints block overlapping `pending` or `confirmed` intervals: one by doctor and one by patient. This is transaction-safe and prevents races that a select-then-insert check cannot prevent. Availability uses a GiST exclusion constraint over a normalized minute range to prohibit overlapping intervals for a doctor and weekday.

## Timestamps

Appointment instants and audit/event timestamps use `timestamptz`, stored as UTC-safe instants. Date and local time fields are reserved only for recurring availability and leave dates. Future application services will apply the clinic timezone when presenting slots.

## RLS philosophy

RLS is defense in depth around a FastAPI-first architecture. Direct authenticated clients can read only their own profile and records in which they are involved; no broad public policy exists. Client-side mutation is deliberately unavailable for operations managed through the API. In particular, there is no admin-wide visit-note policy: only the involved patient and doctor can select a note, and only the doctor can write it.

## Automation outbox

`automation_events` carries event type, aggregate identifiers, recipient references, JSON payload, retry state, scheduling time, and a unique `deduplication_key`. Future application transactions will write the domain change and outbox event together; n8n can then process due pending events safely.
