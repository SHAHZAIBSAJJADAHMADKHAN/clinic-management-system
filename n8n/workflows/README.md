# Outbox Email Dispatcher Workflow Foundation

Build one dispatcher workflow around the existing `automation_events` outbox. Do not create separate per-email queues and do not place credentials in this file or exported JSON.

## Node pattern

```text
Schedule Trigger
  -> Fetch due pending/failed events
  -> Split in Batches (small batch)
  -> Conditional claim event
  -> Switch on event_type
  -> Fetch minimum recipient/appointment/doctor context
  -> Build approved transactional email
  -> Email provider send (event.id idempotency key)
  -> Mark processed

Send failure
  -> Mark failed with future available_at backoff
  -> Continue next event
```

## Required safeguards

- Use an encrypted n8n credential backed by the private `N8N_OUTBOX_SUPABASE_*` runtime values. Never use frontend keys, user JWTs, or credentials embedded in workflow JSON.
- Fetch only events with a due `available_at` and `status` in `pending`/`failed`.
- Claim each event with a conditional state update; only the workflow instance receiving the returned claimed row may send it.
- Increment `attempt_count` when claiming. On failure preserve it, leave `processed_at` empty, and use a bounded exponential backoff. Recommended schedule: 5, 15, 60, 240, and 1440 minutes.
- On success set `status=processed` and `processed_at`. Do not mark an event processed before the provider acknowledges it.
- Use `automation_events.id` as the email-provider idempotency key or stable message identifier. This is essential if provider success is known but the outbox completion update times out.
- Route only the documented event types: `doctor_invitation`, `appointment_confirmed`, `appointment_rejected`, `appointment_cancelled`, `appointment_cancelled_leave`, `appointment_reminder`, and `appointment_pending_expired`.
- Fetch only recipient contact and approved appointment/doctor fields. Never fetch or transmit visit notes, passwords, JWTs, secret keys, or unrelated patient data.

## Timezone rule

FastAPI determines reminder and expiration eligibility using `CLINIC_TIMEZONE`. n8n formats an already selected appointment instant in that same timezone; it must not independently decide whether an appointment is tomorrow or expired.

See `docs/PHASE_05_AUTOMATION_FOUNDATION.md` for the complete event and email-content contract.

## Import and controlled activation

1. In n8n, import `clinic-email-dispatcher.json` from this directory.
2. Select and configure the SMTP/email credential on **Send Transactional Email**. The export intentionally contains no credential ID; choose a credential created in this n8n instance. If the provider supports it, configure its stable message identifier/idempotency option to use the durable `event_id` supplied to the node.
3. Configure the private n8n runtime environment values from `n8n/.env.example`: `N8N_OUTBOX_SUPABASE_URL`, `N8N_OUTBOX_SUPABASE_SERVICE_ROLE_KEY`, `N8N_EMAIL_FROM`, `N8N_CLINIC_TIMEZONE`, and `N8N_OUTBOX_MAX_ATTEMPTS`. Keep the service-role value in n8n's encrypted/private configuration only.
4. Perform a controlled test with one non-production `automation_events` record and a safe recipient. Run the workflow manually; do not activate it first.
5. Verify `automation_events`: the claimed test event must become `processed` with `processed_at` after provider acknowledgement. For a simulated send failure it must be `failed`, retain its incremented `attempt_count`, have a future `available_at`, and have no `processed_at`.
6. Activate the workflow only after the controlled test and outbox-state checks succeed. Keep the default five-minute polling interval unless an operations review approves a change.

The workflow uses a conditional `PATCH` claim before any email is sent. A zero-row claim response is intentionally dropped, preventing a competing execution from sending the same event. Unsupported event types are never emailed and are returned to `failed` for operator review.
