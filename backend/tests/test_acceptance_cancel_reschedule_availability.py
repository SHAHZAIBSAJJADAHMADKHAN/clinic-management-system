from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from app.schemas.clinic import AppointmentReschedule, AvailabilityCreate, LeaveCreate
from app.services.clinic import ClinicService


def service():
    return ClinicService(SimpleNamespace(clinic_timezone="UTC", supabase_secret_key="x", supabase_rest_url="http://example.test/rest/v1"))


def profile():
    return SimpleNamespace(id=uuid4())


class Db:
    def __init__(self):
        self.calls = []

    async def request(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if args[:2] == ("PATCH", "appointments"):
            return [{"id": "appointment", "patient_profile_id": kwargs["params"]["patient_profile_id"].removeprefix("eq.")}]
        return [{"id": "record"}]

    async def rpc(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return [{"id": "appointment", "status": "pending"}]


@pytest.mark.asyncio
async def test_acceptance_6_cancel_releases_active_slot_and_emits_one_event(monkeypatch):
    clinic, patient = service(), profile()
    clinic.db = Db()
    start = datetime(2035, 1, 1, 12, tzinfo=timezone.utc)
    clinic._one = lambda *_args, **_kwargs: __import__("asyncio").sleep(0, result={"id": "appointment", "patient_profile_id": str(patient.id), "status": "confirmed", "start_at": start.isoformat()})
    monkeypatch.setattr("app.services.clinic.now_utc", lambda: start - timedelta(hours=3))

    result = await clinic.cancel(patient, "appointment", "No longer needed")

    assert result["id"] == "appointment"
    appointment_patch = next(call for call in clinic.db.calls if call[0][:2] == ("PATCH", "appointments"))
    assert appointment_patch[1]["payload"]["status"] == "cancelled"
    events = [call for call in clinic.db.calls if call[0][:2] == ("POST", "automation_events")]
    assert len(events) == 1
    assert events[0][1]["payload"]["event_type"] == "appointment_cancelled"
    assert events[0][1]["payload"]["deduplication_key"] == "appointment_cancelled:appointment"


@pytest.mark.asyncio
async def test_acceptance_6_patient_cannot_cancel_within_two_hours_or_another_patients_appointment(monkeypatch):
    clinic, patient = service(), profile()
    clinic.db = Db()
    start = datetime(2035, 1, 1, 12, tzinfo=timezone.utc)
    queries = []

    async def owned_row(*_args, **kwargs):
        queries.append(kwargs)
        return {"status": "confirmed", "start_at": start.isoformat(), "patient_profile_id": str(patient.id)}

    clinic._one = owned_row
    monkeypatch.setattr("app.services.clinic.now_utc", lambda: start - timedelta(minutes=90))
    with pytest.raises(HTTPException) as raised:
        await clinic.cancel(patient, "appointment")

    assert raised.value.status_code == 400
    assert raised.value.detail == "Cancellation is blocked within two hours."
    assert queries[0]["patient_profile_id"] == f"eq.{patient.id}"
    assert not clinic.db.calls


@pytest.mark.asyncio
async def test_acceptance_6_reschedule_is_owned_validated_and_returns_pending(monkeypatch):
    clinic, patient = service(), profile()
    clinic.db = Db()
    old_start = datetime(2035, 1, 1, 12, tzinfo=timezone.utc)
    new_start = old_start + timedelta(hours=2)
    appointment_id, new_doctor = uuid4(), uuid4()
    queries, validated = [], []

    async def existing(*_args, **kwargs):
        queries.append(kwargs)
        return {"id": str(appointment_id), "status": "confirmed", "start_at": old_start.isoformat()}

    async def validate(*args):
        validated.append(args)

    clinic._one = existing
    clinic.validate_slot = validate
    monkeypatch.setattr("app.services.clinic.now_utc", lambda: old_start - timedelta(hours=3))
    result = await clinic.reschedule(patient, appointment_id, AppointmentReschedule(doctor_id=new_doctor, start_at=new_start, end_at=new_start + timedelta(minutes=30)))

    assert result[0]["status"] == "pending"
    assert queries[0]["patient_profile_id"] == f"eq.{patient.id}"
    assert validated[0][1:] == (new_doctor, new_start, new_start + timedelta(minutes=30))
    rpc = clinic.db.calls[0]
    assert rpc[0][0] == "reschedule_patient_appointment"
    assert rpc[0][1]["p_patient_id"] == str(patient.id)
    assert rpc[0][1]["p_doctor_id"] == str(new_doctor)


@pytest.mark.asyncio
async def test_acceptance_7_server_validation_rejects_invalid_availability_and_past_leave():
    clinic = service()
    clinic.db = Db()
    with pytest.raises(HTTPException, match="End time must be after start time"):
        await clinic.add_availability(profile(), AvailabilityCreate(day_of_week=1, start_time=time(11), end_time=time(11)))
    with pytest.raises(HTTPException, match="Leave date must be in the future"):
        await clinic.add_leave(profile(), LeaveCreate(leave_date=datetime.now(timezone.utc).date()))
    assert not clinic.db.calls


@pytest.mark.asyncio
async def test_acceptance_7_overlap_is_mapped_to_clear_server_error_and_valid_window_is_saved():
    clinic, doctor_profile = service(), profile()
    clinic.db = Db()
    clinic.doctor_for = lambda _: __import__("asyncio").sleep(0, result={"id": "doctor"})
    clinic.audit = lambda *_args: __import__("asyncio").sleep(0)
    original_request = clinic.db.request

    async def conflict(*_args, **_kwargs):
        raise httpx.HTTPStatusError("conflict", request=httpx.Request("POST", "http://example.test"), response=httpx.Response(409))

    clinic.db.request = conflict
    with pytest.raises(HTTPException, match="Availability overlaps an existing interval") as raised:
        await clinic.add_availability(doctor_profile, AvailabilityCreate(day_of_week=1, start_time=time(9, 30), end_time=time(10, 30)))
    assert raised.value.status_code == 409

    clinic.db.request = original_request
    saved = await clinic.add_availability(doctor_profile, AvailabilityCreate(day_of_week=1, start_time=time(9), end_time=time(11)))
    assert saved["id"] == "record"
    request = clinic.db.calls[-1]
    assert request[1]["payload"]["start_time"] == "09:00:00"
    assert request[1]["payload"]["end_time"] == "11:00:00"


def test_acceptance_6_and_7_database_guarantees_remain_transactional():
    root = Path(__file__).parents[2]
    schema = (root / "supabase/migrations/002_core_schema.sql").read_text()
    operations = (root / "supabase/migrations/006_phase03_transactional_operations.sql").read_text()

    assert "check (end_time > start_time)" in schema
    assert "int4range(" in schema
    assert schema.count("where (status in ('pending', 'confirmed'))") == 2
    assert "select * into v_old" in operations and "for update" in operations
    assert "status='pending'" in operations
    assert "revoke all on function public.reschedule_patient_appointment" in operations
