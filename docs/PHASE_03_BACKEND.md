# Phase 03 Backend

## API and roles

All application routes use `/api/v1`. `GET /auth/me` returns the authenticated active profile. Patient routes provide active-doctor discovery, slots, appointment creation/list/detail, eligible cancellation/rescheduling, and their own visit-note read. Doctor routes manage only the caller's availability, future leave, pending requests, schedule, confirmation/rejection, completion/no-show, own visit notes, and history only for that doctor's patient relationship. Admin routes manage doctors, patients, appointments, cancellation, and the dashboard; they never return visit-note content.

## Appointment rules

Slots are 30 minutes, timezone-aware, future-only, inside availability, not on leave, and unavailable when a pending/confirmed appointment occupies them. Database GiST exclusions remain the final concurrent doctor/patient conflict protection. Patients may cancel or reschedule only pending/confirmed appointments more than two hours ahead. Rescheduling returns to `pending`; completed and `no_show` are final for patient mutation.

## Leave, notes, and automation

Future leave is handled by the transactional `add_doctor_leave` RPC, cancelling active appointments on the clinic-local leave date and creating deduplicated outbox events. Notes are accessible only to the involved patient and doctor, enforced in both services and RLS. `POST /internal/automation/expire-pending` and `/day-before-reminders` require admin authorization; they create durable, deduplicated outbox events rather than send mail.

## Time and database operations

`CLINIC_TIMEZONE` defaults to `UTC`; instant comparisons use timezone-aware timestamps and clinic-date calculations use this setting. Migration `006_phase03_transactional_operations.sql` supplies rescheduling, leave cancellation, and pending-expiration RPCs. They are SECURITY DEFINER with a fixed `search_path`, revoked from PUBLIC/anon/authenticated, and executable only by `service_role`.

## Tests

From `backend/`, run `python -m pip install -r requirements.txt` then `python -m pytest -q`.
