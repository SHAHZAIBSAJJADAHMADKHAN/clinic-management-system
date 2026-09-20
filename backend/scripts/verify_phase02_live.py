"""One-time Phase 02 live verification. Does not print credentials or tokens."""
from __future__ import annotations

import os
import secrets
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from uuid import uuid4

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import Settings  # noqa: E402


@dataclass
class VerificationState:
    users: list[str] = field(default_factory=list)
    doctors: list[str] = field(default_factory=list)
    appointments: list[str] = field(default_factory=list)
    availabilities: list[str] = field(default_factory=list)
    leaves: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


settings = Settings()
state = VerificationState()
results: list[tuple[str, bool, str]] = []


def service_headers() -> dict[str, str]:
    return {
        "apikey": settings.supabase_secret_key,
        "Authorization": f"Bearer {settings.supabase_secret_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def public_headers(token: str) -> dict[str, str]:
    return {"apikey": settings.supabase_publishable_key, "Authorization": f"Bearer {token}"}


def require(response: httpx.Response, message: str) -> list[dict]:
    if response.is_error:
        raise RuntimeError(f"{message} (HTTP {response.status_code})")
    payload = response.json()
    return payload if isinstance(payload, list) else [payload]


def expect_rejected(response: httpx.Response, name: str, expected_hint: str | None = None) -> None:
    body = response.text.lower()
    passed = response.is_error and (expected_hint is None or expected_hint.lower() in body)
    results.append((name, passed, "rejected" if passed else f"unexpected HTTP {response.status_code}"))
    if not passed:
        raise RuntimeError(f"{name} did not reject as expected")


def create_auth_user(client: httpx.Client, label: str) -> tuple[str, str, str]:
    suffix = uuid4().hex
    email = f"phase02-verification-{label}-{suffix}@example.invalid"
    password = secrets.token_urlsafe(32)
    response = client.post(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users",
        headers=service_headers(),
        json={"email": email, "password": password, "email_confirm": True},
    )
    user_id = require(response, "Could not create temporary verification Auth user")[0]["id"]
    state.users.append(user_id)
    for _ in range(5):
        profile = client.get(
            f"{settings.supabase_rest_url}/profiles",
            headers=service_headers(),
            params={"id": f"eq.{user_id}", "select": "id,role,is_active"},
        )
        rows = require(profile, "Could not read temporary verification profile")
        if rows:
            if rows[0]["role"] != "patient" or not rows[0]["is_active"]:
                raise RuntimeError("Auth trigger did not create an active patient profile")
            return user_id, email, password
        time.sleep(0.25)
    raise RuntimeError("Timed out waiting for Auth profile trigger")


def login(client: httpx.Client, email: str, password: str) -> str:
    response = client.post(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": settings.supabase_publishable_key, "Content-Type": "application/json"},
        json={"email": email, "password": password},
    )
    return require(response, "Could not obtain temporary authenticated session")[0]["access_token"]


def create_doctor(client: httpx.Client, profile_id: str, specialty: str) -> str:
    require(
        client.patch(
            f"{settings.supabase_rest_url}/profiles",
            headers=service_headers(),
            params={"id": f"eq.{profile_id}"},
            json={"role": "doctor"},
        ),
        "Could not promote temporary doctor profile",
    )
    doctor = require(
        client.post(
            f"{settings.supabase_rest_url}/doctors", headers=service_headers(), json={"profile_id": profile_id, "specialty": specialty}
        ),
        "Could not create temporary doctor",
    )[0]
    state.doctors.append(doctor["id"])
    return doctor["id"]


def cleanup(client: httpx.Client) -> bool:
    success = True
    for table, ids in (
        ("visit_notes", state.notes),
        ("appointments", state.appointments),
        ("doctor_availability", state.availabilities),
        ("doctor_leaves", state.leaves),
        ("doctors", state.doctors),
    ):
        for record_id in reversed(ids):
            response = client.delete(f"{settings.supabase_rest_url}/{table}", headers=service_headers(), params={"id": f"eq.{record_id}"})
            success = success and not response.is_error
    for user_id in reversed(state.users):
        response = client.delete(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{user_id}",
            headers=service_headers(),
            params={"should_soft_delete": "false"},
        )
        success = success and not response.is_error
    return success


def main() -> int:
    required = (settings.supabase_url, settings.supabase_publishable_key, settings.supabase_secret_key, settings.supabase_jwks_url)
    if not all(required):
        print("LIVE VERIFICATION NOT RUN: Supabase configuration is incomplete.")
        return 2

    try:
        with httpx.Client(timeout=15.0) as client:
            jwks = client.get(settings.supabase_jwks_url)
            results.append(("JWT/JWKS endpoint reachability", not jwks.is_error and isinstance(jwks.json().get("keys"), list), "reachable"))
            if results[-1][1] is False:
                raise RuntimeError("Configured JWKS endpoint did not return a JWKS key set")

            invalid_role = client.post(
                f"{settings.supabase_rest_url}/profiles",
                headers=service_headers(),
                json={"id": str(uuid4()), "full_name": "Phase 02 Invalid Role", "email": "invalid-role@example.invalid", "role": "invalid"},
            )
            expect_rejected(invalid_role, "Invalid profile role", "app_role")

            p1_id, p1_email, p1_password = create_auth_user(client, "patient-one")
            p2_id, p2_email, p2_password = create_auth_user(client, "patient-two")
            d1_profile, d1_email, d1_password = create_auth_user(client, "doctor-one")
            d2_profile, d2_email, d2_password = create_auth_user(client, "doctor-two")
            admin_id, admin_email, admin_password = create_auth_user(client, "admin")
            d1_id = create_doctor(client, d1_profile, "Phase 02 Verification")
            d2_id = create_doctor(client, d2_profile, "Phase 02 Verification")
            require(client.patch(f"{settings.supabase_rest_url}/profiles", headers=service_headers(), params={"id": f"eq.{admin_id}"}, json={"role": "admin"}), "Could not promote temporary admin profile")

            invalid_availability = client.post(
                f"{settings.supabase_rest_url}/doctor_availability",
                headers=service_headers(),
                json={"doctor_id": d1_id, "day_of_week": 2, "start_time": "10:00", "end_time": "10:00"},
            )
            expect_rejected(invalid_availability, "Invalid availability time", "check")
            availability = require(
                client.post(f"{settings.supabase_rest_url}/doctor_availability", headers=service_headers(), json={"doctor_id": d1_id, "day_of_week": 2, "start_time": "09:00", "end_time": "10:00"}),
                "Could not create baseline availability",
            )[0]
            state.availabilities.append(availability["id"])
            overlap_availability = client.post(
                f"{settings.supabase_rest_url}/doctor_availability",
                headers=service_headers(),
                json={"doctor_id": d1_id, "day_of_week": 2, "start_time": "09:30", "end_time": "10:30"},
            )
            expect_rejected(overlap_availability, "Overlapping availability", "exclusion")

            leave = require(
                client.post(f"{settings.supabase_rest_url}/doctor_leaves", headers=service_headers(), json={"doctor_id": d1_id, "leave_date": str(date(2031, 6, 17)), "reason": "Phase 02 verification"}),
                "Could not create baseline leave",
            )[0]
            state.leaves.append(leave["id"])
            duplicate_leave = client.post(
                f"{settings.supabase_rest_url}/doctor_leaves", headers=service_headers(), json={"doctor_id": d1_id, "leave_date": str(date(2031, 6, 17))}
            )
            expect_rejected(duplicate_leave, "Duplicate doctor leave", "duplicate")

            start, end = "2031-06-18T09:00:00Z", "2031-06-18T09:30:00Z"
            baseline = require(
                client.post(f"{settings.supabase_rest_url}/appointments", headers=service_headers(), json={"patient_profile_id": p1_id, "doctor_id": d1_id, "start_at": start, "end_at": end, "status": "pending"}),
                "Could not create baseline appointment",
            )[0]
            state.appointments.append(baseline["id"])
            doctor_conflict = client.post(
                f"{settings.supabase_rest_url}/appointments", headers=service_headers(), json={"patient_profile_id": p2_id, "doctor_id": d1_id, "start_at": start, "end_at": end, "status": "confirmed"}
            )
            expect_rejected(doctor_conflict, "Same-doctor active appointment conflict", "exclusion")
            require(
                client.patch(f"{settings.supabase_rest_url}/appointments", headers=service_headers(), params={"id": f"eq.{baseline['id']}"}, json={"status": "cancelled", "cancelled_at": "2031-06-17T00:00:00Z"}),
                "Could not cancel baseline appointment",
            )
            freed_slot = require(
                client.post(f"{settings.supabase_rest_url}/appointments", headers=service_headers(), json={"patient_profile_id": p2_id, "doctor_id": d1_id, "start_at": start, "end_at": end, "status": "pending"}),
                "Cancelled appointment did not release doctor slot",
            )[0]
            state.appointments.append(freed_slot["id"])
            results.append(("Cancelled appointment releases doctor slot", True, "insert succeeded"))
            patient_conflict = client.post(
                f"{settings.supabase_rest_url}/appointments", headers=service_headers(), json={"patient_profile_id": p2_id, "doctor_id": d2_id, "start_at": start, "end_at": end, "status": "pending"}
            )
            expect_rejected(patient_conflict, "Same-patient active appointment conflict", "exclusion")
            invalid_duration = client.post(
                f"{settings.supabase_rest_url}/appointments", headers=service_headers(), json={"patient_profile_id": p1_id, "doctor_id": d2_id, "start_at": "2031-06-18T10:00:00Z", "end_at": "2031-06-18T10:29:00Z", "status": "pending"}
            )
            expect_rejected(invalid_duration, "Invalid appointment duration", "check")
            invalid_status = client.post(
                f"{settings.supabase_rest_url}/appointments", headers=service_headers(), json={"patient_profile_id": p1_id, "doctor_id": d2_id, "start_at": "2031-06-18T10:00:00Z", "end_at": "2031-06-18T10:30:00Z", "status": "invalid"}
            )
            expect_rejected(invalid_status, "Invalid appointment status", "appointment_status")

            note = require(
                client.post(f"{settings.supabase_rest_url}/visit_notes", headers=service_headers(), json={"appointment_id": freed_slot["id"], "doctor_id": d1_id, "patient_profile_id": p2_id, "note_text": "Phase 02 temporary verification note."}),
                "Could not create temporary visit note",
            )[0]
            state.notes.append(note["id"])
            p1_token, p2_token = login(client, p1_email, p1_password), login(client, p2_email, p2_password)
            d1_token, d2_token = login(client, d1_email, d1_password), login(client, d2_email, d2_password)
            admin_token = login(client, admin_email, admin_password)
            own_profile = require(client.get(f"{settings.supabase_rest_url}/profiles", headers=public_headers(p1_token), params={"id": f"eq.{p1_id}", "select": "id"}), "Patient own-profile RLS request failed")
            other_profile = require(client.get(f"{settings.supabase_rest_url}/profiles", headers=public_headers(p1_token), params={"id": f"eq.{p2_id}", "select": "id"}), "Patient cross-profile RLS request failed")
            results.append(("Patient profile isolation", len(own_profile) == 1 and not other_profile, "authenticated session"))
            patient_note = require(client.get(f"{settings.supabase_rest_url}/visit_notes", headers=public_headers(p2_token), params={"id": f"eq.{note['id']}", "select": "id"}), "Patient note RLS request failed")
            foreign_patient_note = require(client.get(f"{settings.supabase_rest_url}/visit_notes", headers=public_headers(p1_token), params={"id": f"eq.{note['id']}", "select": "id"}), "Foreign patient note RLS request failed")
            doctor_note = require(client.get(f"{settings.supabase_rest_url}/visit_notes", headers=public_headers(d1_token), params={"id": f"eq.{note['id']}", "select": "id"}), "Doctor note RLS request failed")
            admin_note = require(client.get(f"{settings.supabase_rest_url}/visit_notes", headers=public_headers(admin_token), params={"id": f"eq.{note['id']}", "select": "id"}), "Admin note RLS request failed")
            foreign_doctor_appointment = require(client.get(f"{settings.supabase_rest_url}/appointments", headers=public_headers(d2_token), params={"id": f"eq.{freed_slot['id']}", "select": "id"}), "Foreign doctor appointment RLS request failed")
            results.append(("Visit-note and doctor-scope RLS", len(patient_note) == 1 and not foreign_patient_note and len(doctor_note) == 1 and not admin_note and not foreign_doctor_appointment, "authenticated sessions"))
    except Exception as error:
        results.append(("Unexpected live verification error", False, str(error)))
    finally:
        with httpx.Client(timeout=15.0) as client:
            cleaned = cleanup(client)
        results.append(("Temporary verification data cleanup", cleaned, "dependency-safe deletion"))

    for name, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'}: {name} — {detail}")
    return 0 if all(passed for _, passed, _ in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
