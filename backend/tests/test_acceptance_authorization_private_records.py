from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.dependencies.auth import get_current_profile
from app.main import app
from app.models.roles import UserRole
from app.schemas.auth import Profile
from app.services.clinic import ClinicService


def profile(role: UserRole) -> Profile:
    return Profile(id=uuid4(), full_name="Test", email="test@example.test", role=role, is_active=True)


def service() -> ClinicService:
    return ClinicService(SimpleNamespace(clinic_timezone="UTC", supabase_secret_key="x", supabase_rest_url="http://example.test/rest/v1"))


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/v1/doctor/appointments/{}/confirm", None),
        ("post", "/api/v1/admin/doctors", {"email": "new@example.test", "full_name": "New", "specialty": "General"}),
    ],
)
def test_acceptance_8_patient_is_blocked_from_doctor_and_admin_mutations(method, path, payload):
    app.dependency_overrides[get_current_profile] = lambda: profile(UserRole.PATIENT)
    try:
        response = getattr(TestClient(app), method)(path.format(uuid4()) if "{}" in path else path, json=payload)
        assert response.status_code == 403
        assert response.json() == {"detail": "Insufficient permissions."}
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_acceptance_8_other_doctor_cannot_transition_an_appointment():
    clinic, doctor = service(), profile(UserRole.DOCTOR)
    calls = []
    clinic.doctor_for = lambda _: __import__("asyncio").sleep(0, result={"id": "doctor-a"})

    async def missing(*_args, **kwargs):
        calls.append(kwargs)
        raise HTTPException(404, "Record not found.")

    clinic._one = missing
    with pytest.raises(HTTPException) as raised:
        await clinic.doctor_transition(doctor, uuid4(), "confirmed")

    assert raised.value.status_code == 404
    assert raised.value.detail == "Record not found."
    assert calls[0]["doctor_id"] == "eq.doctor-a"


@pytest.mark.asyncio
async def test_acceptance_8_authorized_doctor_transition_remains_available():
    clinic, doctor = service(), profile(UserRole.DOCTOR)
    calls = []
    clinic.doctor_for = lambda _: __import__("asyncio").sleep(0, result={"id": "doctor-a"})
    clinic._one = lambda *_args, **_kwargs: __import__("asyncio").sleep(0, result={"id": "appointment", "status": "pending", "start_at": "2020-01-01T09:00:00+00:00"})

    class Db:
        async def request(self, *args, **kwargs):
            calls.append((args, kwargs))
            return [{"id": "appointment", "patient_profile_id": "patient-a"}]

    clinic.db = Db()
    clinic.audit = lambda *_args: __import__("asyncio").sleep(0)
    result = await clinic.doctor_transition(doctor, uuid4(), "confirmed")

    assert result["id"] == "appointment"
    assert calls[0][0][:2] == ("PATCH", "appointments")
    assert calls[0][1]["payload"] == {"status": "confirmed"}


@pytest.mark.asyncio
async def test_acceptance_9_other_patient_appointment_and_other_doctor_history_are_not_disclosed():
    clinic, patient, doctor = service(), profile(UserRole.PATIENT), profile(UserRole.DOCTOR)
    appointment_queries, history_queries = [], []

    async def missing_appointment(_table, **kwargs):
        appointment_queries.append(kwargs)
        raise HTTPException(404, "Record not found.")

    clinic._one = missing_appointment
    with pytest.raises(HTTPException) as appointment_error:
        await clinic.own_appointment(patient, uuid4())
    assert appointment_error.value.detail == "Record not found."
    assert appointment_queries[0]["patient_profile_id"] == f"eq.{patient.id}"

    clinic.doctor_for = lambda _: __import__("asyncio").sleep(0, result={"id": "doctor-a"})

    async def no_history(_table, **kwargs):
        history_queries.append(kwargs)
        return []

    clinic._rows = no_history
    with pytest.raises(HTTPException) as history_error:
        await clinic.patient_history(doctor, uuid4())
    assert history_error.value.status_code == 404
    assert history_error.value.detail == "Patient history not found."
    assert history_queries[0]["doctor_id"] == "eq.doctor-a"


def test_acceptance_9_admin_cannot_use_either_visit_note_api_and_rls_limits_notes_to_involved_users():
    app.dependency_overrides[get_current_profile] = lambda: profile(UserRole.ADMIN)
    try:
        client = TestClient(app)
        appointment_id = uuid4()
        assert client.get(f"/api/v1/doctor/appointments/{appointment_id}/visit-note").status_code == 403
        assert client.get(f"/api/v1/appointments/me/{appointment_id}/visit-note").status_code == 403
    finally:
        app.dependency_overrides.clear()

    rls = (Path(__file__).parents[2] / "supabase/migrations/004_rls_policies.sql").read_text()
    assert "visit_notes_select_involved_only" in rls
    assert "patient_profile_id = auth.uid()" in rls
    assert "d.id = doctor_id and d.profile_id = auth.uid()" in rls
    assert "visit_notes_insert_involved_doctor_only" in rls

