from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from app.schemas.clinic import AppointmentCreate
from app.services.clinic import ClinicService


def test_acceptance_3_database_constraints_block_active_doctor_and_patient_overlaps():
    schema = (
        Path(__file__).parents[2]
        / "supabase/migrations/002_core_schema.sql"
    ).read_text()

    assert "doctor_id with =" in schema
    assert "patient_profile_id with =" in schema
    assert schema.count("tstzrange(start_at, end_at, '[)') with &&") == 2
    assert schema.count("where (status in ('pending', 'confirmed'))") >= 2


@pytest.mark.asyncio
async def test_acceptance_3_booking_race_is_rejected_when_database_reports_conflict():
    service = ClinicService(
        SimpleNamespace(
            clinic_timezone="UTC",
            supabase_secret_key="x",
            supabase_rest_url="http://example.test/rest/v1",
        )
    )
    start = datetime.now(timezone.utc) + timedelta(days=1)
    data = AppointmentCreate(
        doctor_id=uuid4(),
        start_at=start,
        end_at=start + timedelta(minutes=30),
    )

    async def database_conflict(*_args, **_kwargs):
        request = httpx.Request("POST", "http://example.test/appointments")
        response = httpx.Response(409, request=request)
        raise httpx.HTTPStatusError("conflict", request=request, response=response)

    service.validate_slot = lambda *_args: __import__("asyncio").sleep(0)
    service.db.request = database_conflict
    service.audit = lambda *_args: __import__("asyncio").sleep(0)

    with pytest.raises(HTTPException) as raised:
        await service.book(SimpleNamespace(id=uuid4()), data)

    assert raised.value.status_code == 409
    assert raised.value.detail == "Appointment slot conflict."
