# Clinic Appointment & Patient Management System

A portfolio-grade clinic platform replacing appointments managed through calls, WhatsApp, and paper registers with a secure, professional web application.

## Solution

Patients will request appointments with active doctors, doctors will manage availability and appointment decisions, and administrators will manage clinic operations. The API will enforce scheduling and role-based authorization rules; automated communications will be handled through n8n.

## Roles

- **Patient:** finds doctors, requests and manages eligible appointments, and views permitted records.
- **Doctor:** manages availability, leave, appointments, and permitted patient history.
- **Admin:** manages doctors, patients, appointments, and clinic reporting. Administrators must never read private visit notes.

## Tech stack

- Frontend: React, JavaScript, Vite, React Router
- Backend: Python, FastAPI, Pydantic
- Future persistence and auth: Supabase, PostgreSQL, Supabase Auth, JWT/JWKS
- Future automation: n8n and email integration
- Testing: Pytest, Vitest, React Testing Library

## Architecture

`React client → FastAPI API → Supabase/PostgreSQL`

`Application events → n8n workflows → email provider`

See [architecture documentation](docs/ARCHITECTURE.md) for responsibilities and boundaries.

## Repository structure

```text
frontend/   React client
backend/    FastAPI service
supabase/   Future migrations, policies, and seed data
n8n/        Future exported automation workflows
docs/       Architecture documentation
tests/      Cross-system tests as the project grows
```

## Local setup

1. Copy `backend/.env.example` to `backend/.env` and set local values when needed.
2. Install the backend dependencies: `python -m pip install -r backend/requirements.txt`.
3. Start the API: `uvicorn app.main:app --reload --app-dir backend`.
4. In a second terminal, copy `frontend/.env.example` to `frontend/.env`.
5. Install and start the client: `cd frontend; npm install; npm run dev`.

## Current status: Phase 02 implementation pending live database verification

Implemented: Phase 01 foundation plus ordered Supabase migrations for the core data model, transaction-safe appointment and availability conflict constraints, restrictive RLS, patient-only auth profile creation, reusable FastAPI JWT/JWKS authentication dependencies, role authorization helpers, and focused local security tests.

Future work: live Supabase configuration and migration verification, appointment workflows, availability and leave APIs, dashboards, automations, private clinical-note APIs, the final UI system, and the full acceptance suite.

## Development phases

1. **Foundation** — repository, API/client shells, configuration, documentation, and tests.
2. **Data and identity** — Supabase schema, RLS, authentication, and role foundations.
3. **Scheduling domain** — availability, leave, appointment APIs, and business constraints.
4. **Experience** — role dashboards, polished responsive healthcare UI, interactions, and optional 3D assets.
5. **Automation and acceptance** — n8n workflows, email reliability, and official acceptance testing.

## Phase 02 acceptance traceability

Phase 02 establishes foundations for—not end-to-end passes of—official tests #3 (doctor/patient time conflicts), #4 (database validation), #7 (invalid/overlapping availability), #8 (server-side authorization), and #9 (visit-note isolation). See [database verification](docs/PHASE_02_DATABASE_VERIFICATION.md).

## Final acceptance goal

The completed product must satisfy the ten locked scenarios covering booking, availability, collision prevention, authorization, privacy, automation, refresh safety, and mobile usability. Phase 01 deliberately implements none of those domain workflows; it establishes the structure required to implement them safely.
