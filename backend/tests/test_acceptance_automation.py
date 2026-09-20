from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.services.clinic import ClinicService


def service(zone="UTC"):
    return ClinicService(SimpleNamespace(clinic_timezone=zone, supabase_secret_key="x", supabase_rest_url="http://example.test/rest/v1"))


class ReminderDb:
    def __init__(self):
        self.events = []

    async def request(self, _method, _table, **kwargs):
        payload = kwargs["payload"]
        if any(event["deduplication_key"] == payload["deduplication_key"] for event in self.events):
            raise httpx.HTTPStatusError("duplicate", request=httpx.Request("POST", "http://example.test"), response=httpx.Response(409))
        self.events.append(payload)
        return [payload]


@pytest.mark.asyncio
async def test_acceptance_10_reminder_uses_clinic_day_bounds_and_is_idempotent(monkeypatch):
    clinic = service("Asia/Karachi")
    clinic.db = ReminderDb()
    captured = {}

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2035, 1, 1, 12, tzinfo=tz)

    async def appointments(_table, **params):
        captured.update(params)
        return [{"id": "appointment", "patient_profile_id": "patient"}]

    clinic._rows = appointments
    monkeypatch.setattr("app.services.clinic.datetime", FixedDatetime)

    assert await clinic.create_day_before_reminders() == 1
    assert await clinic.create_day_before_reminders() == 0
    assert captured["status"] == "eq.confirmed"
    assert captured["and_"] == "(start_at.gte.2035-01-01T19:00:00+00:00,start_at.lt.2035-01-02T19:00:00+00:00)"
    assert clinic.db.events == [{
        "event_type": "appointment_reminder",
        "aggregate_type": "appointment",
        "aggregate_id": "appointment",
        "recipient_profile_id": "patient",
        "deduplication_key": "appointment_reminder:appointment",
    }]


@pytest.mark.asyncio
async def test_acceptance_10_expiration_is_atomic_idempotent_and_persists_on_refetch():
    clinic = service()
    appointment_id, patient_id = uuid4(), uuid4()
    state = {"status": "pending", "events": []}

    class Db:
        async def rpc(self, name, _payload):
            assert name == "expire_pending_appointments"
            if state["status"] != "pending":
                return 0
            state["status"] = "cancelled"
            state["events"].append({"event_type": "appointment_pending_expired", "aggregate_id": str(appointment_id), "recipient_profile_id": str(patient_id), "deduplication_key": f"appointment_pending_expired:{appointment_id}"})
            return 1

    clinic.db = Db()
    assert await clinic.expire_pending(uuid4()) == 1
    assert await clinic.expire_pending(uuid4()) == 0

    async def refetch(_table, **_params):
        return [{"id": str(appointment_id), "status": state["status"]}]

    clinic._rows = refetch
    assert (await clinic.my_appointments(SimpleNamespace(id=patient_id)))[0]["status"] == "cancelled"
    assert state["events"] == [{"event_type": "appointment_pending_expired", "aggregate_id": str(appointment_id), "recipient_profile_id": str(patient_id), "deduplication_key": f"appointment_pending_expired:{appointment_id}"}]


def test_acceptance_10_database_and_n8n_contracts_cover_expiration_and_reminders():
    root = Path(__file__).parents[2]
    schema = (root / "supabase/migrations/002_core_schema.sql").read_text()
    operations = (root / "supabase/migrations/006_phase03_transactional_operations.sql").read_text()
    workflow = (root / "n8n/workflows/clinic-email-dispatcher.json").read_text()

    assert "deduplication_key text not null unique" in schema
    assert "update appointments set status='cancelled'" in operations
    assert "appointment_pending_expired" in operations
    assert "on conflict (deduplication_key) do nothing" in operations
    assert '"appointment_reminder"' in workflow
    assert '"appointment_pending_expired"' in workflow
    assert "recipient_profile_id" in workflow and "aggregate_id" in workflow

