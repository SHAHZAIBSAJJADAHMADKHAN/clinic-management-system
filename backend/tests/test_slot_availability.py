from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.clinic import ClinicService


MONDAY = date(2035, 1, 1)
DOCTOR_ID = uuid4()


def service() -> ClinicService:
    return ClinicService(
        SimpleNamespace(
            clinic_timezone="UTC",
            supabase_secret_key="x",
            supabase_rest_url="http://example.test/rest/v1",
        )
    )


def appointment(status: str) -> dict[str, str]:
    return {
        "start_at": "2035-01-01T09:00:00+00:00",
        "end_at": "2035-01-01T09:30:00+00:00",
        "status": status,
    }


async def configure_rows(
    clinic: ClinicService,
    appointments: list[dict[str, str]] | None = None,
    leave: bool = False,
) -> list[tuple[str, dict]]:
    calls: list[tuple[str, dict]] = []

    async def rows(table: str, **params):
        calls.append((table, params))
        if table == "doctor_leaves":
            return [{"id": "leave"}] if leave else []
        if table == "doctor_availability":
            return [{"start_time": "09:00:00", "end_time": "11:00:00"}]
        if table == "appointments":
            return appointments or []
        raise AssertionError(f"unexpected table: {table}")

    clinic._rows = rows
    clinic.active_doctor = lambda _: __import__("asyncio").sleep(0)
    return calls


@pytest.mark.asyncio
async def test_empty_monday_availability_generates_four_half_hour_slots(monkeypatch):
    clinic = service()
    await configure_rows(clinic)
    monkeypatch.setattr(
        "app.services.clinic.now_utc",
        lambda: datetime(2034, 12, 31, tzinfo=timezone.utc),
    )

    slots = await clinic.slots(DOCTOR_ID, MONDAY)

    assert [slot["start_at"].strftime("%H:%M") for slot in slots] == [
        "09:00",
        "09:30",
        "10:00",
        "10:30",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "confirmed"])
async def test_active_appointment_holds_its_slot_after_postgrest_timestamp_serialization(monkeypatch, status):
    clinic = service()
    calls = await configure_rows(clinic, [appointment(status)])
    monkeypatch.setattr(
        "app.services.clinic.now_utc",
        lambda: datetime(2034, 12, 31, tzinfo=timezone.utc),
    )

    slots = await clinic.slots(DOCTOR_ID, MONDAY)

    assert [slot["start_at"].strftime("%H:%M") for slot in slots] == [
        "09:30",
        "10:00",
        "10:30",
    ]
    appointment_query = next(params for table, params in calls if table == "appointments")
    assert appointment_query["doctor_id"] == f"eq.{DOCTOR_ID}"
    assert appointment_query["status"] == "in.(pending,confirmed)"
    assert appointment_query["start_at"] == "gte.2035-01-01T00:00:00+00:00"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["rejected", "cancelled", "completed", "no_show"])
async def test_non_active_appointment_statuses_do_not_hold_slots(monkeypatch, status):
    clinic = service()
    # PostgREST applies the active-status filter, so inactive records are not
    # returned to slot generation.
    await configure_rows(clinic, [])
    monkeypatch.setattr(
        "app.services.clinic.now_utc",
        lambda: datetime(2034, 12, 31, tzinfo=timezone.utc),
    )

    slots = await clinic.slots(DOCTOR_ID, MONDAY)

    assert len(slots) == 4


@pytest.mark.asyncio
async def test_another_patient_cannot_select_an_active_pending_slot(monkeypatch):
    clinic = service()
    await configure_rows(clinic, [appointment("pending")])
    monkeypatch.setattr(
        "app.services.clinic.now_utc",
        lambda: datetime(2034, 12, 31, tzinfo=timezone.utc),
    )

    with pytest.raises(HTTPException) as raised:
        await clinic.validate_slot(
            object(),
            DOCTOR_ID,
            datetime(2035, 1, 1, 9, tzinfo=timezone.utc),
            datetime(2035, 1, 1, 9, 30, tzinfo=timezone.utc),
        )

    assert raised.value.status_code == 409
    assert raised.value.detail == "Requested slot is unavailable."


@pytest.mark.asyncio
async def test_leave_and_past_slots_remain_unavailable(monkeypatch):
    clinic = service()
    await configure_rows(clinic, leave=True)
    monkeypatch.setattr(
        "app.services.clinic.now_utc",
        lambda: datetime(2034, 12, 31, tzinfo=timezone.utc),
    )
    assert await clinic.slots(DOCTOR_ID, MONDAY) == []

    clinic = service()
    await configure_rows(clinic)
    monkeypatch.setattr(
        "app.services.clinic.now_utc",
        lambda: datetime(2035, 1, 1, 12, tzinfo=timezone.utc),
    )
    assert await clinic.slots(DOCTOR_ID, MONDAY) == []
