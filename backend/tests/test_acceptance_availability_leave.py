from datetime import date, datetime, timedelta, timezone
from pathlib import Path
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


async def configure_slots(
    clinic: ClinicService,
    appointments: list[dict[str, str]] | None = None,
    leave: bool = False,
) -> None:
    async def rows(table: str, **_params):
        if table == "doctor_leaves":
            return [{"id": "leave"}] if leave else []
        if table == "doctor_availability":
            return [{"start_time": "09:00:00", "end_time": "11:00:00"}]
        if table == "appointments":
            return appointments or []
        raise AssertionError(f"unexpected table: {table}")

    clinic._rows = rows
    clinic.active_doctor = lambda _: __import__("asyncio").sleep(0)


def active_appointment(hour: int, minute: int, status: str) -> dict[str, str]:
    start = datetime(2035, 1, 1, hour, minute, tzinfo=timezone.utc)
    return {
        "start_at": start.isoformat(),
        "end_at": (start + timedelta(minutes=30)).isoformat(),
        "status": status,
    }


@pytest.mark.asyncio
async def test_acceptance_4_direct_outside_hours_booking_is_rejected(monkeypatch):
    clinic = service()
    await configure_slots(clinic)
    monkeypatch.setattr(
        "app.services.clinic.now_utc",
        lambda: datetime(2034, 12, 31, tzinfo=timezone.utc),
    )

    with pytest.raises(HTTPException) as raised:
        await clinic.validate_slot(
            object(),
            DOCTOR_ID,
            datetime(2035, 1, 1, 11, tzinfo=timezone.utc),
            datetime(2035, 1, 1, 11, 30, tzinfo=timezone.utc),
        )

    assert raised.value.status_code == 409
    assert raised.value.detail == "Requested slot is unavailable."


@pytest.mark.asyncio
async def test_acceptance_4_fully_booked_active_window_has_no_free_slots(monkeypatch):
    clinic = service()
    appointments = [
        active_appointment(9, 0, "pending"),
        active_appointment(9, 30, "confirmed"),
        active_appointment(10, 0, "pending"),
        active_appointment(10, 30, "confirmed"),
    ]
    await configure_slots(clinic, appointments)
    monkeypatch.setattr(
        "app.services.clinic.now_utc",
        lambda: datetime(2034, 12, 31, tzinfo=timezone.utc),
    )

    assert await clinic.slots(DOCTOR_ID, MONDAY) == []


@pytest.mark.asyncio
async def test_acceptance_5_past_and_deactivated_doctor_bookings_are_rejected(monkeypatch):
    clinic = service()
    monkeypatch.setattr(
        "app.services.clinic.now_utc",
        lambda: datetime(2035, 1, 1, 9, tzinfo=timezone.utc),
    )

    with pytest.raises(HTTPException) as past:
        await clinic.validate_slot(
            object(),
            DOCTOR_ID,
            datetime(2035, 1, 1, 8, tzinfo=timezone.utc),
            datetime(2035, 1, 1, 8, 30, tzinfo=timezone.utc),
        )
    assert past.value.status_code == 400

    async def inactive_doctor(*_args, **_kwargs):
        return {"is_active": False}

    clinic._one = inactive_doctor
    with pytest.raises(HTTPException) as inactive:
        await clinic.active_doctor(DOCTOR_ID)
    assert inactive.value.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["completed", "no_show"])
async def test_acceptance_5_doctor_cannot_finalize_a_future_visit(status):
    clinic = service()
    clinic.doctor_for = lambda _: __import__("asyncio").sleep(0, result={"id": "doctor"})
    clinic._one = lambda *_args, **_kwargs: __import__("asyncio").sleep(
        0,
        result={
            "id": "appointment",
            "status": "confirmed",
            "start_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        },
    )

    with pytest.raises(HTTPException) as raised:
        await clinic.doctor_transition(object(), "appointment", status)

    assert raised.value.status_code == 400
    assert raised.value.detail == "Visit cannot be finalized before it starts."


@pytest.mark.asyncio
async def test_acceptance_5_leave_day_has_no_slots(monkeypatch):
    clinic = service()
    await configure_slots(clinic, leave=True)
    monkeypatch.setattr(
        "app.services.clinic.now_utc",
        lambda: datetime(2034, 12, 31, tzinfo=timezone.utc),
    )

    assert await clinic.slots(DOCTOR_ID, MONDAY) == []


def test_acceptance_5_leave_rpc_cancels_active_visits_and_emits_events_atomically():
    migration = (
        Path(__file__).parents[2]
        / "supabase/migrations/006_phase03_transactional_operations.sql"
    ).read_text()

    assert "security definer" in migration
    assert "update appointments set status='cancelled'" in migration
    assert "status in ('pending','confirmed') returning *" in migration
    assert "appointment_cancelled_leave" in migration
    assert "on conflict (deduplication_key) do nothing" in migration
    assert "start_at at time zone p_clinic_timezone" in migration
