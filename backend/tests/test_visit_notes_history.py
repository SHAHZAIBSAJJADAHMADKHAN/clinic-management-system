from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.models.roles import UserRole
from app.schemas.auth import Profile
from app.services.clinic import ClinicService
from app.dependencies.auth import get_current_profile
from app.main import app
from fastapi.testclient import TestClient
from app.schemas.clinic import AppointmentReschedule
def p(role=UserRole.DOCTOR): return Profile(id=uuid4(),full_name='x',email='x@test.dev',role=role,is_active=True)
class Db:
 def __init__(self): self.calls=[]
 async def request(self,*a,**k): self.calls.append((a,k)); return [{'id':'note','note_text':'private'}]
def s():
 x=ClinicService(SimpleNamespace(clinic_timezone='UTC',supabase_secret_key='x',supabase_rest_url='x'));x.db=Db();x.doctor_for=lambda _: __import__('asyncio').sleep(0,result={'id':'doc'});x.audit=lambda *a:__import__('asyncio').sleep(0);return x
@pytest.mark.asyncio
async def test_complete_and_no_show_only_after_start():
 x=s(); old={'id':'a','status':'confirmed','start_at':(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()};x._one=lambda *a,**k:__import__('asyncio').sleep(0,result=old)
 await x.doctor_transition(p(),'a','completed'); await x.doctor_transition(p(),'a','no_show')
 assert len(x.db.calls)>=2
@pytest.mark.asyncio
async def test_future_finalization_and_patient_cancellation_blocked():
 x=s();future={'id':'a','status':'confirmed','start_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()};x._one=lambda *a,**k:__import__('asyncio').sleep(0,result=future)
 with pytest.raises(HTTPException): await x.doctor_transition(p(),'a','completed')
 final={'id':'a','status':'completed','start_at':future['start_at']};x._one=lambda *a,**k:__import__('asyncio').sleep(0,result=final)
 with pytest.raises(HTTPException): await x.cancel(p(UserRole.PATIENT),'a')
@pytest.mark.asyncio
async def test_doctor_note_create_update_and_history_scope():
 x=s(); appointment={'id':'a','doctor_id':'doc','patient_profile_id':'patient'}; x._one=lambda *a,**k:__import__('asyncio').sleep(0,result=appointment)
 async def rows(table,**_): return [] if table=='visit_notes' else [appointment]
 x._rows=rows
 await x.upsert_note(p(),'a','private'); assert any(c[0][0]=='POST' for c in x.db.calls)
 await x.patient_history(p(),'patient'); assert x.db.calls
@pytest.mark.asyncio
async def test_unrelated_doctor_and_patient_note_access_are_denied():
 x=s()
 async def missing(*a,**k): raise HTTPException(404,'Record not found')
 x._one=missing
 with pytest.raises(HTTPException): await x.doctor_note(p(),'other')
 with pytest.raises(HTTPException): await x.patient_note(p(UserRole.PATIENT),'other')
@pytest.mark.asyncio
async def test_involved_patient_can_read_own_note():
 x=s(); calls=[]
 async def one(table,**kwargs):
  calls.append((table,kwargs)); return {'id':'appointment','patient_profile_id':str(p(UserRole.PATIENT).id)} if table=='appointments' else {'id':'note','note_text':'private'}
 x._one=one; note=await x.patient_note(p(UserRole.PATIENT),'appointment')
 assert note['note_text']=='private' and calls[1][1]['patient_profile_id'].startswith('eq.')
@pytest.mark.asyncio
@pytest.mark.parametrize('status',['completed','no_show'])
async def test_final_appointments_cannot_cancel_or_reschedule(status):
 x=s(); patient=p(UserRole.PATIENT); row={'id':'a','status':status,'start_at':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()}
 x._one=lambda *a,**k:__import__('asyncio').sleep(0,result=row)
 with pytest.raises(HTTPException): await x.cancel(patient,'a')
 with pytest.raises(HTTPException): await x.reschedule(patient,'a',AppointmentReschedule(doctor_id=uuid4(),start_at=datetime.now(timezone.utc)+timedelta(days=3),end_at=datetime.now(timezone.utc)+timedelta(days=3,minutes=30)))
@pytest.mark.asyncio
async def test_unrelated_doctor_cannot_read_or_update_note():
 x=s()
 async def denied(*a,**k): raise HTTPException(404,'Record not found')
 x.note_for_doctor=denied
 with pytest.raises(HTTPException): await x.doctor_note(p(),'appointment')
 with pytest.raises(HTTPException): await x.upsert_note(p(),'appointment','private')
@pytest.mark.asyncio
async def test_history_query_is_scoped_to_doctor_and_patient():
 x=s(); doctor=p(); x.doctor_for=lambda _:__import__('asyncio').sleep(0,result={'id':'doctor-a'}); captured={}
 async def rows(table,**kwargs): captured.update(kwargs); return [{'id':'a','doctor_id':'doctor-a','patient_profile_id':'patient-x'}]
 x._rows=rows; history=await x.patient_history(doctor,'patient-x')
 assert history==[{'id':'a','doctor_id':'doctor-a','patient_profile_id':'patient-x'}] and captured['doctor_id']=='eq.doctor-a' and captured['patient_profile_id']=='eq.patient-x'
def test_admin_cannot_access_doctor_visit_note_api():
 admin=p(UserRole.ADMIN); app.dependency_overrides[get_current_profile]=lambda: admin
 try: assert TestClient(app).get(f'/api/v1/doctor/appointments/{uuid4()}/visit-note').status_code==403
 finally: app.dependency_overrides.clear()
