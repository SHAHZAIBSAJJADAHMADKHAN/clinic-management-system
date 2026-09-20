import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import Settings


def test_karachi_clinic_time_round_trips_through_canonical_utc_storage():
    clinic_time = datetime(2026, 9, 22, 10, 0, tzinfo=ZoneInfo("Asia/Karachi"))
    stored_in_utc = clinic_time.astimezone(timezone.utc)

    assert stored_in_utc == datetime(2026, 9, 22, 5, 0, tzinfo=timezone.utc)
    assert stored_in_utc.astimezone(ZoneInfo("Asia/Karachi")) == clinic_time


def test_default_clinic_timezone_and_email_workflow_use_asia_karachi():
    assert Settings().clinic_timezone == "Asia/Karachi"

    workflow = json.loads(
        (Path(__file__).parents[2] / "n8n/workflows/clinic-email-dispatcher.json").read_text()
    )
    email_node = next(node for node in workflow["nodes"] if node["name"] == "Build Appointment Email")
    code = email_node["parameters"]["jsCode"]

    assert "N8N_CLINIC_TIMEZONE || 'Asia/Karachi'" in code
    assert "timeZone: zone" in code
    assert "const when = `${date} at ${time}`" in code
