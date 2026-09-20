from types import SimpleNamespace
from uuid import uuid4
import pytest
from app.services.clinic import ClinicService
from app.dependencies.auth import get_current_profile
from app.main import app
from app.models.roles import UserRole
from app.schemas.auth import Profile
from fastapi.testclient import TestClient
class Db:
 def __init__(self): self.calls=[]
 async def request(self,*a,**k): self.calls.append((a,k)); return []
 async def rpc(self,*a,**k): self.calls.append((a,k)); return 1
def svc():
 s=ClinicService(SimpleNamespace(clinic_timezone='UTC',supabase_secret_key='x',supabase_rest_url='x'));s.db=Db();return s
@pytest.mark.asyncio
async def test_expiration_uses_atomic_idempotent_rpc():
 s=svc(); assert await s.expire_pending(uuid4())==1; assert s.db.calls[0][0][0]=='expire_pending_appointments'
@pytest.mark.asyncio
async def test_confirmed_only_reminders_are_deduplicated():
 s=svc();s._rows=lambda *a,**k:__import__('asyncio').sleep(0,result=[{'id':'a','patient_profile_id':'p'}])
 assert await s.create_day_before_reminders()==1; assert s.db.calls[0][1]['payload']['deduplication_key']=='appointment_reminder:a'
@pytest.mark.asyncio
async def test_no_reminders_when_no_confirmed_appointments():
 s=svc();s._rows=lambda *a,**k:__import__('asyncio').sleep(0,result=[]);assert await s.create_day_before_reminders()==0
@pytest.mark.parametrize('role',[UserRole.PATIENT,UserRole.DOCTOR])
def test_automation_routes_are_admin_protected(role):
 app.dependency_overrides[get_current_profile]=lambda:Profile(id=uuid4(),full_name='x',email='x@test.dev',role=role,is_active=True)
 try: assert TestClient(app).post('/api/v1/internal/automation/expire-pending').status_code==403
 finally: app.dependency_overrides.clear()
