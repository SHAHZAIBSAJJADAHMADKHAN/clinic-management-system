from types import SimpleNamespace
from uuid import uuid4
import pytest

from app.models.roles import UserRole
from app.schemas.auth import Profile
from app.services.clinic import ClinicService
from app.dependencies.auth import get_current_profile
from app.main import app
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone


def admin():
    return Profile(
        id=uuid4(),
        full_name='Admin',
        email='admin@test.dev',
        role=UserRole.ADMIN,
        is_active=True
    )


class Db:
    def __init__(self):
        self.calls = []

        # Mock settings used by ClinicService.
        # frontend_origin is required by create_doctor()
        # when generating the secure password setup redirect.
        self.settings = SimpleNamespace(
            supabase_url='http://x',
            frontend_origin='http://localhost:5173'
        )

        self.headers = {}

    async def request(self, *a, **k):
        self.calls.append((a, k))
        return [
            {
                'id': 'x',
                'doctor_id': 'd',
                'status': 'pending'
            }
        ]


@pytest.mark.asyncio
async def test_admin_lists_filtered_data_without_notes():
    s = ClinicService(
        SimpleNamespace(
            clinic_timezone='UTC',
            supabase_secret_key='x',
            supabase_rest_url='x'
        )
    )

    s.db = Db()

    rows = await s.admin_appointments(
        'd',
        None,
        'pending'
    )

    assert rows
    assert 'visit_notes' not in s.db.calls[0][1]['params']['select']


@pytest.mark.asyncio
async def test_admin_deactivation_preserves_history():
    s = ClinicService(
        SimpleNamespace(
            clinic_timezone='UTC',
            supabase_secret_key='x',
            supabase_rest_url='x'
        )
    )

    s.db = Db()

    s._one = lambda *a, **k: __import__('asyncio').sleep(
        0,
        result={'id': 'd'}
    )

    s.audit = lambda *a: __import__('asyncio').sleep(0)

    await s.deactivate_doctor(
        admin(),
        'd'
    )

    assert any(
        c[0][0] == 'PATCH'
        and c[0][1] == 'doctors'
        for c in s.db.calls
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'term,field',
    [
        ('Ada', 'full_name'),
        ('ada@test.dev', 'email'),
        ('555', 'phone')
    ]
)
async def test_admin_patient_search_is_safe_and_note_free(
    term,
    field
):
    s = ClinicService(
        SimpleNamespace(
            clinic_timezone='UTC',
            supabase_secret_key='x',
            supabase_rest_url='x'
        )
    )

    s.db = Db()

    await s.admin_patients(term)

    params = s.db.calls[0][1]['params']

    assert (
        field + '.ilike.*' + term + '*'
        in params['or']
    )

    assert 'visit_notes' not in params['select']


@pytest.mark.asyncio
async def test_admin_filters_and_cancellation_outbox():
    s = ClinicService(
        SimpleNamespace(
            clinic_timezone='UTC',
            supabase_secret_key='x',
            supabase_rest_url='x'
        )
    )

    s.db = Db()

    future = (
        datetime.now(timezone.utc)
        + timedelta(days=2)
    ).isoformat()

    await s.admin_appointments(
        'doctor',
        '2035-01-01',
        'confirmed'
    )

    params = s.db.calls[0][1]['params']

    assert params['doctor_id'] == 'eq.doctor'
    assert params['status'] == 'eq.confirmed'
    assert 'visit_notes' not in params['select']

    s.db.calls = []

    s._one = lambda *a, **k: __import__('asyncio').sleep(
        0,
        result={
            'id': 'a',
            'status': 'confirmed',
            'start_at': future,
            'patient_profile_id': 'patient'
        }
    )

    s.audit = lambda *a: __import__('asyncio').sleep(0)

    await s.cancel(
        admin(),
        'a',
        'admin cancel',
        admin=True
    )

    assert any(
        c[0][1] == 'appointments'
        and c[0][0] == 'PATCH'
        for c in s.db.calls
    )

    assert any(
        c[0][1] == 'automation_events'
        for c in s.db.calls
    )


@pytest.mark.asyncio
async def test_dashboard_counts_all_statuses():
    s = ClinicService(
        SimpleNamespace(
            clinic_timezone='UTC',
            supabase_secret_key='x',
            supabase_rest_url='x'
        )
    )

    async def appointments(**_):
        return [
            {
                'doctor_id': 'd',
                'status': x
            }
            for x in (
                'pending',
                'confirmed',
                'completed',
                'no_show',
                'cancelled'
            )
        ]

    s.admin_appointments = appointments

    d = await s.dashboard()

    assert d['per_doctor_counts']['d'] == {
        'pending': 1,
        'confirmed': 1,
        'completed': 1,
        'no_show': 1,
        'cancelled': 1
    }


@pytest.mark.parametrize(
    'role',
    [
        UserRole.PATIENT,
        UserRole.DOCTOR
    ]
)
def test_non_admin_roles_cannot_access_admin_routes(role):
    app.dependency_overrides[get_current_profile] = lambda: Profile(
        id=uuid4(),
        full_name='x',
        email='x@test.dev',
        role=role,
        is_active=True
    )

    try:
        client = TestClient(app)

        assert client.get(
            '/api/v1/admin/patients'
        ).status_code == 403

        assert client.get(
            '/api/v1/admin/dashboard'
        ).status_code == 403

        assert client.post(
            '/api/v1/admin/doctors',
            json={
                'email': 'x@test.dev',
                'full_name': 'x',
                'specialty': 's'
            }
        ).status_code == 403

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_trusted_doctor_creation_and_safe_invitation_outbox(
    monkeypatch
):
    s = ClinicService(
        SimpleNamespace(
            clinic_timezone='UTC',
            supabase_secret_key='server-only',
            supabase_rest_url='http://x/rest/v1',
            frontend_origin='http://localhost:5173'
        )
    )

    db = Db()

    s.db = db

    s.audit = lambda *a: __import__('asyncio').sleep(0)

    class Response:
        is_error = False

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    class Client:
        def __init__(self):
            self.posts = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def post(self, url, **kwargs):
            self.posts.append(
                (url, kwargs)
            )

            return Response(
                {'id': 'auth-user'}
                if url.endswith('/users')
                else {
                    'properties': {
                        'action_link':
                            'https://auth.example.test/recovery-link'
                    }
                }
            )

    client = Client()

    monkeypatch.setattr(
        'app.services.clinic.httpx.AsyncClient',
        lambda **_: client
    )

    from app.schemas.clinic import DoctorCreate

    await s.create_doctor(
        admin(),
        DoctorCreate(
            email='newdoctor@test.dev',
            full_name='New Doctor',
            specialty='Cardiology'
        )
    )

    writes = [
        (
            call[0][0],
            call[0][1],
            call[1].get(
                'payload',
                {}
            )
        )
        for call in db.calls
    ]

    assert (
        'PATCH',
        'profiles',
        {
            'full_name': 'New Doctor',
            'phone': None,
            'role': 'doctor'
        }
    ) in writes

    doctor = [
        payload
        for method, table, payload in writes
        if method == 'POST'
        and table == 'doctors'
    ][0]

    event = [
        payload
        for method, table, payload in writes
        if method == 'POST'
        and table == 'automation_events'
    ][0]

    assert doctor == {
        'profile_id': 'auth-user',
        'specialty': 'Cardiology'
    }

    assert (
        event['event_type']
        == 'doctor_invitation'
    )

    assert (
        event['recipient_profile_id']
        == 'auth-user'
    )

    assert (
        event['deduplication_key']
        == 'doctor_invitation:x'
    )

    assert event['payload'] == {
        'setup_url':
            'https://auth.example.test/recovery-link'
    }

    assert (
        client.posts[1][0]
        == 'http://x/auth/v1/admin/generate_link'
    )

    assert (
        client.posts[1][1]['headers']
        == db.headers
    )

    assert client.posts[1][1]['json'] == {
        'type': 'recovery',
        'email': 'newdoctor@test.dev',
        'redirect_to':
            'http://localhost:5173/set-password'
    }

    assert not any(
        token in str(event).lower()
        for token in (
            'password',
            'jwt',
            'secret',
            'apikey'
        )
    )