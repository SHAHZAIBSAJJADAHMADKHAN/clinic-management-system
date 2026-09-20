# n8n Automation Foundation

The project uses the existing durable `automation_events` outbox as the single source of transactional email work. Workflow exports belong in `workflows/`, but must never include real credentials.

The documented dispatcher routes doctor invitations, appointment confirmation/rejection/cancellation, leave cancellation, reminders, and expired pending appointments. It claims events conditionally, uses durable idempotency keys, and marks success/failure in the outbox rather than relying only on n8n execution history.

Read [the dispatcher workflow foundation](workflows/README.md) and [the Phase 05 contract](../docs/PHASE_05_AUTOMATION_FOUNDATION.md) before configuring an n8n instance.
