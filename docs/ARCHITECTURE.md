# Architecture

## System flow

```text
React (browser) → FastAPI (application API) → Supabase/PostgreSQL (identity and data)
                                   ↓
                         application events → n8n → email provider
```

## Layer responsibilities

### React

The frontend presents accessible, responsive role-specific experiences. It uses a small API service layer rather than embedding network calls throughout components. Route guards improve the user experience later, but do not replace server-side authorization.

### FastAPI

FastAPI is the trusted application boundary. It validates requests, verifies Supabase-issued JWTs against JWKS with issuer and expiration checks, loads application profiles server-side, applies role authorization, enforces scheduling rules, and exposes versioned HTTP APIs. Domain logic belongs in services; data access belongs in repositories.

### Supabase and PostgreSQL

Supabase provides authentication and PostgreSQL persistence. Phase 02 migrations define profiles, doctors, availability, leave days, appointments, visit notes, audit logs, and automation/outbox events, along with indexes, constraints, restrictive RLS policies, and a patient-only auth profile trigger.

### n8n and email

The API will emit durable application events. n8n will consume them to coordinate doctor invitations, appointment confirmations, rejections and cancellations, leave cancellations, reminders, and expired pending appointments. Workflows must support retries, error handling, idempotency, and duplicate-email protection.

## Security boundary

The browser is untrusted. API authorization and business rules must be independently enforced on the backend. Private visit notes must never be returned to administrators, and patients and doctors can access only records they are explicitly permitted to see.
