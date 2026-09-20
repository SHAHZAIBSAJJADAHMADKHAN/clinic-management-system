from datetime import date, timedelta, time
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.models.roles import UserRole
from app.schemas.auth import Profile
from app.schemas.clinic import AvailabilityCreate, LeaveCreate
from app.services.clinic import ClinicService

def profile(): return Profile(id=uuid4(),full_name='Doctor',email='doctor@example.test',role=UserRole.DOCTOR,is_active=True)
class FakeDb:
    def __init__(self): self.calls=[]
    async def request(self,*args,**kwargs): self.calls.append((args,kwargs)); return [{'id':str(uuid4()),'leave_date':'2035-01-01'}]
    async def rpc(self,*args,**kwargs): self.calls.append((args,kwargs)); return [{'id':str(uuid4()),'leave_date':'2035-01-01'}]
def svc():
    service=ClinicService(SimpleNamespace(clinic_timezone='UTC',supabase_secret_key='x',supabase_rest_url='x'))
    service.db=FakeDb(); return service
@pytest.mark.asyncio
async def test_update_own_availability_audits():
    s=svc(); p=profile(); s.doctor_for=lambda _: __import__('asyncio').sleep(0,result={'id':'doctor'}); s._one=lambda *a,**k: __import__('asyncio').sleep(0,result={'id':'availability'})
    s.audit=lambda *a: __import__('asyncio').sleep(0); r=await s.update_availability(p,'availability',AvailabilityCreate(day_of_week=1,start_time=time(9),end_time=time(10)))
    assert r['id'] and any(x[0][0]=='PATCH' for x in s.db.calls)
@pytest.mark.asyncio
async def test_invalid_availability_is_rejected():
    s=svc()
    with pytest.raises(HTTPException) as e: await s.update_availability(profile(),uuid4(),AvailabilityCreate(day_of_week=1,start_time=time(10),end_time=time(10)))
    assert e.value.status_code==400
@pytest.mark.asyncio
async def test_delete_uses_own_doctor_scope():
    s=svc(); p=profile(); s.doctor_for=lambda _: __import__('asyncio').sleep(0,result={'id':'own-doctor'}); s._one=lambda *a,**k: __import__('asyncio').sleep(0,result={'id':'availability'}); s.audit=lambda *a: __import__('asyncio').sleep(0)
    await s.delete_availability(p,uuid4()); assert any(c[0][0]=='DELETE' for c in s.db.calls)
@pytest.mark.asyncio
async def test_past_leave_rejected():
    s=svc()
    with pytest.raises(HTTPException) as e: await s.add_leave(profile(),LeaveCreate(leave_date=date.today()-timedelta(days=1)))
    assert e.value.status_code==400
@pytest.mark.asyncio
async def test_future_leave_uses_transactional_rpc():
    s=svc(); p=profile(); s.doctor_for=lambda _: __import__('asyncio').sleep(0,result={'id':'doctor'})
    await s.add_leave(p,LeaveCreate(leave_date=date.today()+timedelta(days=2)))
    assert any(c[0][0]=='add_doctor_leave' for c in s.db.calls)
@pytest.mark.asyncio
async def test_other_doctor_availability_is_not_mutated():
    s=svc(); p=profile(); s.doctor_for=lambda _: __import__('asyncio').sleep(0,result={'id':'doctor-a'})
    async def missing(*a,**k): raise HTTPException(404,'Record not found.')
    s._one=missing
    with pytest.raises(HTTPException) as e: await s.delete_availability(p,uuid4())
    assert e.value.status_code==404 and not s.db.calls
@pytest.mark.asyncio
async def test_other_doctor_leave_is_not_mutated():
    s=svc(); p=profile(); s.doctor_for=lambda _: __import__('asyncio').sleep(0,result={'id':'doctor-a'})
    async def missing(*a,**k): raise HTTPException(404,'Record not found.')
    s._one=missing
    with pytest.raises(HTTPException) as e: await s.delete_leave(p,uuid4())
    assert e.value.status_code==404 and not s.db.calls
@pytest.mark.asyncio
async def test_future_leave_deletion_audits():
    s=svc(); p=profile(); s.doctor_for=lambda _: __import__('asyncio').sleep(0,result={'id':'doctor'})
    s._one=lambda *a,**k: __import__('asyncio').sleep(0,result={'id':'leave','leave_date':'2035-01-01'}); s.audit=lambda *a: __import__('asyncio').sleep(0)
    await s.delete_leave(p,uuid4()); assert any(c[0][0]=='DELETE' for c in s.db.calls)
def test_leave_rpc_cancels_active_appointments_with_idempotent_events():
    migration=(__import__('pathlib').Path(__file__).parents[2]/'supabase/migrations/006_phase03_transactional_operations.sql').read_text()
    assert "status in ('pending','confirmed')" in migration
    assert "appointment_cancelled_leave" in migration
    assert "on conflict (deduplication_key) do nothing" in migration
