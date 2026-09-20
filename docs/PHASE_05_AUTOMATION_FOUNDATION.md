# Phase 05 Automation Foundation

This document defines the existing durable outbox contract and the safe n8n consumption pattern. It does not configure an n8n instance, an email provider, or real credentials, and it does not claim that any email has been delivered.

## Existing architecture

`automation_events` is the sole durable email-work outbox. It is created in migration `002_core_schema.sql`, has RLS enabled with no client policies, and is indexed for runnable `pending`/`failed` rows. Application services and the Phase 03 transactional RPCs insert events; neither the frontend nor a client-side Supabase connection reads or writes this table.

| Contract field | Meaning |
| --- | --- |
| `id` | Durable event identifier; use it as the email-provider idempotency identifier where supported. |
| `event_type` | Routing key for n8n. |
| `aggregate_type`, `aggregate_id` | The subject (`appointment` or `doctor`) and its identifier. |
| `recipient_profile_id`, `recipient_email` | Intended recipient reference. Existing producers use `recipient_profile_id`; n8n resolves the current permitted email server-side. |
| `payload` | Optional safe metadata. Current producers leave it at `{}`; no visit-note content is allowed. |
| `status` | `pending`, `processing`, `processed`, or `failed`. |
| `attempt_count`, `available_at` | Durable retry count and next eligible attempt time. |
| `processed_at` | Successful delivery record time. |
| `deduplication_key` | Globally unique producer idempotency key. |
| `created_at`, `updated_at` | Creation and state-transition timestamps. |

The event table deliberately contains no password, JWT, API key, service-role credential, or visit note.

## Current producer mapping

| Required outcome | Actual event type | Created by | Recipient | Deduplication key | State |
| --- | --- | --- | --- | --- | --- |
| Doctor invitation/password setup | `doctor_invitation` | Trusted admin doctor creation | New doctor profile | `doctor_invitation:{doctor_id}` | READY |
| Appointment confirmation | `appointment_confirmed` | Doctor confirms pending appointment | Appointment patient | `appointment_confirmed:{appointment_id}` | READY |
| Appointment rejection | `appointment_rejected` | Doctor rejects pending appointment | Appointment patient | `appointment_rejected:{appointment_id}` | READY |
| Patient cancellation | `appointment_cancelled` | Patient cancellation service | Appointment patient | `appointment_cancelled:{appointment_id}` | READY |
| Admin cancellation | `appointment_cancelled` | Admin cancellation service | Appointment patient | `appointment_cancelled:{appointment_id}` | READY |
| Leave cancellation | `appointment_cancelled_leave` | `add_doctor_leave` transactional RPC | Each affected appointment patient | `appointment_cancelled_leave:{appointment_id}` | READY |
| Day-before reminder | `appointment_reminder` | Clinic-timezone reminder process | Appointment patient | `appointment_reminder:{appointment_id}` | READY |
| Expired pending appointment | `appointment_pending_expired` | Expiration transactional RPC | Appointment patient | `appointment_pending_expired:{appointment_id}` | READY |

The generic cancellation event intentionally covers both patient and admin cancellations. A cancellation email can use the appointment state and optional cancellation reason; it does not need actor identity to notify the patient. The leave and expiration flows use distinct event types for their specific wording.

## Event data for email composition

The event itself is minimal by design. Once n8n has claimed an event, it may use `aggregate_id` and `recipient_profile_id` through its server-only Supabase connection to retrieve only the data needed for the template:

- appointment events: recipient email/name, doctor name, specialty, `start_at`, `end_at`, status, and cancellation/rejection reason when applicable;
- doctor invitation: recipient email/name and a password-setup/sign-in action supplied by the Auth/onboarding process;
- no template may query or include `visit_notes`, note text, history, tokens, passwords, or unrelated profile data.

All appointment times must be formatted in `CLINIC_TIMEZONE`. Eligibility for next-day reminders and expiration is decided in FastAPI using this configured timezone; n8n must not recalculate eligibility.

## n8n consumer protocol

The workflow pattern is documented in `n8n/workflows/README.md`.

1. On a conservative schedule, query only events whose `status` is `pending` or `failed` and whose `available_at` is due.
2. For each candidate, claim it with a conditional server-side update that requires its current eligible status. Set `status=processing` and increment `attempt_count`; continue only when the conditional update returns that event. A lost race sends nothing.
3. Route on `event_type`, fetch the minimal referenced records, and construct the matching email.
4. Send with the durable event `id` as the provider idempotency key/message identifier whenever the selected provider supports it.
5. Only after provider success, conditionally set `status=processed` and `processed_at=now()`.
6. On temporary failure, set `status=failed`, retain the attempt count, and set `available_at` to a bounded exponential-backoff time. Do not set `processed_at`.
7. Stop rapid retries after a configured maximum (recommended five attempts); leave the event in `failed` for operational review rather than falsely marking it delivered.

The unique producer `deduplication_key` prevents duplicate work creation. Conditional claim/complete updates prevent two n8n executions from intentionally sending the same claimed event. Provider-level idempotency using `event.id` protects the acknowledgement gap where a provider accepted an email but the subsequent outbox completion update failed.

## Secure n8n access

There is no browser/client access to the outbox. The existing FastAPI scheduling endpoints are protected by the application's admin authorization and create events; they are not an event-delivery API.

For the later n8n deployment, store a server-side Supabase service-role credential only in an encrypted n8n credential or its private environment, never in workflow JSON, repository files, FastAPI responses, frontend variables, browser storage, logs, or email content. The n8n instance must be private and restricted to the automation operator. A placeholder-only environment template is provided at `n8n/.env.example`.

Direct service-role access is required for the current outbox consumer because `automation_events` intentionally has no client RLS policies. If a future deployment cannot safely store a service-role credential in n8n, implement a narrowly scoped internal worker API with an independent rotation-ready secret before enabling delivery; do not reuse patient/doctor JWTs or expose an admin login token to n8n.

## Email content contract

| Event | Minimum content |
| --- | --- |
| `doctor_invitation` | Clinic identity, doctor name, account setup/sign-in action. Never include a password. |
| `appointment_confirmed` | Clinic identity, doctor, clinic-local date/time, confirmed status. |
| `appointment_rejected` | Clinic identity, doctor/date-time context, rejection status, safe reason if present. |
| cancellation events | Clinic identity, doctor/date-time context, cancellation status, safe reason if present. |
| `appointment_reminder` | Clinic identity, doctor, clinic-local appointment date/time, reminder wording. |
| `appointment_pending_expired` | Clinic identity, doctor/date-time context, expired/cancelled status. |

No marketing content, private clinical notes, unrelated patient data, passwords, or credentials are permitted.

## Locked acceptance alignment

| Locked test | Automation readiness | Reason |
| --- | --- | --- |
| Test 1 — confirmation email | READY | Durable confirmation event and consumer contract exist; actual provider configuration/delivery is later manual setup. |
| Test 2 — invitation email | READY | Durable doctor invitation event and password-free content contract exist. |
| Test 5 — leave cancellation email | READY | Transactional leave RPC creates one deduplicated cancellation event per affected appointment. |
| Test 6 — cancellation email | READY | Patient/admin cancellations produce durable appointment cancellation events. |
| Test 10 — reminder/expiration | READY | Clinic-timezone backend jobs emit deduplicated reminder and expiration events; the n8n consumer contract preserves retry/idempotency. |

These are readiness statements only. The locked acceptance tests remain unexecuted.

## Manual owner actions before enabling delivery

1. Run and secure a private n8n instance.
2. Create the server-only Supabase service-role credential in n8n from the private deployment environment; do not paste it into an exported workflow or source control.
3. Configure an email-provider credential in n8n and verify that it supports a provider idempotency key or stable message identifier.
4. Import/build the dispatcher from the documented workflow pattern, set a conservative schedule and retry/backoff limits, and run a controlled non-production event test.
5. Configure the n8n instance timezone/display policy to use the clinic timezone for formatting only; backend eligibility remains authoritative.

## Verification outcome

- Existing outbox and producer idempotency: **PASS**.
- Consumer workflow foundation and secure deployment contract: **PASS**.
- Real n8n/email-provider configuration and delivery verification: **not performed in this task**.
