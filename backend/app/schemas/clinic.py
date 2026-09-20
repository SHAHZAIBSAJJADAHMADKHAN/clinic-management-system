from datetime import date, datetime, time
from uuid import UUID
from pydantic import BaseModel, Field

class AvailabilityCreate(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

class AvailabilityUpdate(AvailabilityCreate): pass
class LeaveCreate(BaseModel):
    leave_date: date
    reason: str | None = Field(default=None, max_length=500)
class AppointmentCreate(BaseModel):
    doctor_id: UUID
    start_at: datetime
    end_at: datetime
class AppointmentReschedule(AppointmentCreate): pass
class ReasonRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
class VisitNoteUpsert(BaseModel):
    note_text: str = Field(min_length=1, max_length=10000)
class DoctorCreate(BaseModel):
    email: str
    full_name: str = Field(min_length=1, max_length=200)
    specialty: str = Field(min_length=1, max_length=150)
    phone: str | None = None
class DoctorDeactivate(BaseModel):
    is_active: bool = False
class SlotResponse(BaseModel):
    start_at: datetime
    end_at: datetime
