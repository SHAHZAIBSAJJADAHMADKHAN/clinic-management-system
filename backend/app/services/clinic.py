from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException

from app.core.config import Settings
from app.models.roles import UserRole
from app.repositories.clinic import ClinicRepository
from app.schemas.auth import Profile


ACTIVE = {"pending", "confirmed"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ClinicService:
    def __init__(self, settings: Settings):
        self.db = ClinicRepository(settings)
        self.tz = ZoneInfo(settings.clinic_timezone)

    async def _rows(self, table, **params):
        return await self.db.request(
            "GET",
            table,
            params={
                key.rstrip("_"): value
                for key, value in params.items()
            },
        )

    async def _one(self, table, **params):
        rows = await self._rows(table, **params)

        if not rows:
            raise HTTPException(404, "Record not found.")

        return rows[0]

    async def doctor_for(self, profile: Profile):
        return await self._one(
            "doctors",
            profile_id=f"eq.{profile.id}",
            select="*",
        )

    async def active_doctor(self, doctor_id):
        doctor = await self._one(
            "doctors",
            id=f"eq.{doctor_id}",
            select="*,profiles(full_name)",
        )

        if not doctor["is_active"]:
            raise HTTPException(400, "Doctor is inactive.")

        return doctor

    async def emit(self, typ, aggregate_id, recipient=None):
        key = f"{typ}:{aggregate_id}"

        try:
            await self.db.request(
                "POST",
                "automation_events",
                payload={
                    "event_type": typ,
                    "aggregate_type": "appointment",
                    "aggregate_id": str(aggregate_id),
                    "recipient_profile_id": (
                        str(recipient) if recipient else None
                    ),
                    "deduplication_key": key,
                },
            )
        except httpx.HTTPStatusError:
            pass

    async def audit(
        self,
        actor,
        action,
        entity_type,
        entity_id,
    ):
        await self.db.request(
            "POST",
            "audit_logs",
            payload={
                "actor_profile_id": str(actor),
                "action": action,
                "entity_type": entity_type,
                "entity_id": str(entity_id),
            },
        )

    async def slots(self, doctor_id, day: date):
        await self.active_doctor(doctor_id)

        local_day = day

        leaves = await self._rows(
            "doctor_leaves",
            doctor_id=f"eq.{doctor_id}",
            leave_date=f"eq.{day}",
            select="id",
        )

        if leaves:
            return []

        avail = await self._rows(
            "doctor_availability",
            doctor_id=f"eq.{doctor_id}",
            day_of_week=f"eq.{day.weekday()}",
            select="start_time,end_time",
        )

        day_start = datetime.combine(
            local_day,
            datetime.min.time(),
            self.tz,
        ).astimezone(timezone.utc)

        appointments = await self._rows(
            "appointments",
            doctor_id=f"eq.{doctor_id}",
            status="in.(pending,confirmed)",
            start_at=f"gte.{day_start.isoformat()}",
            select="start_at,end_at",
        )

        blocked = [
            (
                datetime.fromisoformat(
                    item["start_at"].replace("Z", "+00:00")
                ),
                datetime.fromisoformat(
                    item["end_at"].replace("Z", "+00:00")
                ),
            )
            for item in appointments
        ]

        out = []

        for availability in avail:
            cursor = datetime.combine(
                local_day,
                datetime.strptime(
                    availability["start_time"],
                    "%H:%M:%S",
                ).time(),
                self.tz,
            ).astimezone(timezone.utc)

            end = datetime.combine(
                local_day,
                datetime.strptime(
                    availability["end_time"],
                    "%H:%M:%S",
                ).time(),
                self.tz,
            ).astimezone(timezone.utc)

            while cursor + timedelta(minutes=30) <= end:
                finish = cursor + timedelta(minutes=30)

                overlaps_active_appointment = any(
                    cursor < appointment_end
                    and finish > appointment_start
                    for appointment_start, appointment_end in blocked
                )

                if cursor > now_utc() and not overlaps_active_appointment:
                    out.append(
                        {
                            "start_at": cursor,
                            "end_at": finish,
                        }
                    )

                cursor = finish

        return out

    async def validate_slot(
        self,
        patient,
        doctor_id,
        start,
        end,
    ):
        if (
            start.tzinfo is None
            or end.tzinfo is None
            or end - start != timedelta(minutes=30)
        ):
            raise HTTPException(
                400,
                "Appointments must be timezone-aware 30-minute slots.",
            )

        if start <= now_utc():
            raise HTTPException(
                400,
                "Past slots cannot be booked.",
            )

        slots = await self.slots(
            doctor_id,
            start.astimezone(self.tz).date(),
        )

        if not any(
            item["start_at"] == start
            and item["end_at"] == end
            for item in slots
        ):
            raise HTTPException(
                409,
                "Requested slot is unavailable.",
            )

    async def book(self, patient, data):
        await self.validate_slot(
            patient,
            data.doctor_id,
            data.start_at,
            data.end_at,
        )

        try:
            row = (
                await self.db.request(
                    "POST",
                    "appointments",
                    payload={
                        "patient_profile_id": str(patient.id),
                        "doctor_id": str(data.doctor_id),
                        "start_at": data.start_at.isoformat(),
                        "end_at": data.end_at.isoformat(),
                        "status": "pending",
                    },
                )
            )[0]

        except httpx.HTTPStatusError as error:
            raise HTTPException(
                409,
                "Appointment slot conflict.",
            ) from error

        await self.audit(
            patient.id,
            "appointment_created",
            "appointment",
            row["id"],
        )

        return row

    async def my_appointments(self, profile):
        return await self._rows(
            "appointments",
            patient_profile_id=f"eq.{profile.id}",
            select="*,doctors(specialty,profiles(full_name))",
            order="start_at.desc",
        )

    async def own_appointment(
        self,
        profile,
        appointment_id,
    ):
        return await self._one(
            "appointments",
            id=f"eq.{appointment_id}",
            patient_profile_id=f"eq.{profile.id}",
            select="*,doctors(specialty,profiles(full_name))",
        )

    async def cancel(
        self,
        profile,
        appointment_id,
        reason=None,
        admin=False,
    ):
        query = {
            "id": f"eq.{appointment_id}",
        }

        if not admin:
            query["patient_profile_id"] = f"eq.{profile.id}"

        row = await self._one(
            "appointments",
            select="*",
            **query,
        )

        if row["status"] not in ACTIVE:
            raise HTTPException(
                409,
                "Appointment cannot be cancelled in its current state.",
            )

        start = datetime.fromisoformat(
            row["start_at"].replace("Z", "+00:00")
        )

        if (
            not admin
            and start - now_utc() <= timedelta(hours=2)
        ):
            raise HTTPException(
                400,
                "Cancellation is blocked within two hours.",
            )

        updated = (
            await self.db.request(
                "PATCH",
                "appointments",
                params=query,
                payload={
                    "status": "cancelled",
                    "cancelled_at": now_utc().isoformat(),
                    "cancellation_reason": reason,
                },
            )
        )[0]

        await self.emit(
            "appointment_cancelled",
            updated["id"],
            updated.get(
                "patient_profile_id",
                row["patient_profile_id"],
            ),
        )

        await self.audit(
            profile.id,
            "appointment_cancelled",
            "appointment",
            updated["id"],
        )

        return updated

    async def doctor_appointments(
        self,
        profile,
        *,
        pending=False,
        day=None,
        status=None,
    ):
        doctor = await self.doctor_for(profile)

        params = {
            "doctor_id": f"eq.{doctor['id']}",
            "select": (
                "*,profiles!"
                "appointments_patient_profile_id_fkey"
                "(full_name,email,phone)"
            ),
            "order": "start_at.asc",
        }

        if pending:
            params["status"] = "eq.pending"
        elif status:
            params["status"] = f"eq.{status}"

        if day:
            params["start_at"] = f"gte.{day}T00:00:00Z"

        return await self._rows(
            "appointments",
            **params,
        )

    async def doctor_transition(
        self,
        profile,
        appointment_id,
        new_status,
        reason=None,
    ):
        doctor = await self.doctor_for(profile)

        row = await self._one(
            "appointments",
            id=f"eq.{appointment_id}",
            doctor_id=f"eq.{doctor['id']}",
            select="*",
        )

        allowed = {
            "confirmed": {"pending"},
            "rejected": {"pending"},
            "completed": {"confirmed"},
            "no_show": {"confirmed"},
        }

        if row["status"] not in allowed[new_status]:
            raise HTTPException(
                409,
                "Invalid appointment state transition.",
            )

        start = datetime.fromisoformat(
            row["start_at"].replace("Z", "+00:00")
        )

        if (
            new_status in {"completed", "no_show"}
            and start > now_utc()
        ):
            raise HTTPException(
                400,
                "Visit cannot be finalized before it starts.",
            )

        payload = {
            "status": new_status,
        }

        if new_status == "rejected":
            payload["rejection_reason"] = reason

        updated = (
            await self.db.request(
                "PATCH",
                "appointments",
                params={
                    "id": f"eq.{appointment_id}",
                },
                payload=payload,
            )
        )[0]

        if new_status in {"confirmed", "rejected"}:
            await self.emit(
                f"appointment_{new_status}",
                updated["id"],
                updated["patient_profile_id"],
            )

        await self.audit(
            profile.id,
            f"appointment_{new_status}",
            "appointment",
            updated["id"],
        )

        return updated

    async def note_for_doctor(
        self,
        profile,
        appointment_id,
    ):
        doctor = await self.doctor_for(profile)

        appointment = await self._one(
            "appointments",
            id=f"eq.{appointment_id}",
            doctor_id=f"eq.{doctor['id']}",
            select="id,doctor_id,patient_profile_id",
        )

        rows = await self._rows(
            "visit_notes",
            appointment_id=f"eq.{appointment['id']}",
            doctor_id=f"eq.{doctor['id']}",
            select="*",
        )

        return appointment, (
            rows[0] if rows else None
        )

    async def upsert_note(
        self,
        profile,
        appointment_id,
        text,
    ):
        appointment, note = await self.note_for_doctor(
            profile,
            appointment_id,
        )

        if note:
            row = (
                await self.db.request(
                    "PATCH",
                    "visit_notes",
                    params={
                        "id": f"eq.{note['id']}",
                    },
                    payload={
                        "note_text": text,
                    },
                )
            )[0]

            action = "visit_note_updated"

        else:
            row = (
                await self.db.request(
                    "POST",
                    "visit_notes",
                    payload={
                        "appointment_id": appointment["id"],
                        "doctor_id": appointment["doctor_id"],
                        "patient_profile_id": appointment[
                            "patient_profile_id"
                        ],
                        "note_text": text,
                    },
                )
            )[0]

            action = "visit_note_created"

        await self.audit(
            profile.id,
            action,
            "visit_note",
            row["id"],
        )

        return row

    async def doctor_note(
        self,
        profile,
        appointment_id,
    ):
        _, note = await self.note_for_doctor(
            profile,
            appointment_id,
        )

        if not note:
            raise HTTPException(
                404,
                "Visit note not found.",
            )

        return note

    async def patient_note(
        self,
        profile,
        appointment_id,
    ):
        row = await self._one(
            "appointments",
            id=f"eq.{appointment_id}",
            patient_profile_id=f"eq.{profile.id}",
            select="id",
        )

        return await self._one(
            "visit_notes",
            appointment_id=f"eq.{row['id']}",
            patient_profile_id=f"eq.{profile.id}",
            select="*",
        )

    async def patient_history(
        self,
        profile,
        patient_id,
    ):
        doctor = await self.doctor_for(profile)

        history = await self._rows(
            "appointments",
            doctor_id=f"eq.{doctor['id']}",
            patient_profile_id=f"eq.{patient_id}",
            select=(
                "id,start_at,end_at,status,"
                "visit_notes(id,note_text)"
            ),
            order="start_at.desc",
        )

        if not history:
            raise HTTPException(404, "Patient history not found.")

        return history

    async def admin_doctors(self):
        return await self._rows(
            "doctors",
            select=(
                "id,specialty,is_active,created_at,"
                "profiles(id,full_name,email,phone)"
            ),
            order="created_at.desc",
        )

    async def create_doctor(self, admin, data):
        import secrets

        auth_url = (
            self.db.settings.supabase_url.rstrip("/")
        )

        # Create the doctor's Supabase Auth identity.
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{auth_url}/auth/v1/admin/users",
                headers=self.db.headers,
                json={
                    "email": data.email,
                    "password": secrets.token_urlsafe(24),
                    "email_confirm": True,
                },
            )

            if response.is_error:
                raise HTTPException(
                    409,
                    "Doctor identity could not be created.",
                )

            user = response.json()

            user_id = user.get(
                "id",
                user.get("user", {}).get("id"),
            )

            if not user_id:
                raise HTTPException(
                    409,
                    "Doctor identity could not be created.",
                )

            # Generate a secure one-time password setup link.
            link_response = await client.post(
                f"{auth_url}/auth/v1/admin/generate_link",
                headers=self.db.headers,
                json={
                    "type": "recovery",
                    "email": data.email,
                    "redirect_to": (
                        "http://localhost:5173/set-password"
                    ),
                },
            )

        if link_response.is_error:
            raise HTTPException(
                500,
                (
                    "Doctor account was created, but the "
                    "password setup link could not be generated."
                ),
            )

        link_data = link_response.json()

        setup_url = (
            link_data.get("action_link")
            or link_data.get(
                "properties",
                {},
            ).get("action_link")
        )

        if not setup_url:
            raise HTTPException(
                500,
                "Doctor password setup link was not returned.",
            )

        # Update the profile created by the auth trigger.
        await self.db.request(
            "PATCH",
            "profiles",
            params={
                "id": f"eq.{user_id}",
            },
            payload={
                "full_name": data.full_name,
                "phone": data.phone,
                "role": "doctor",
            },
        )

        # Create the clinic doctor record.
        doctor = (
            await self.db.request(
                "POST",
                "doctors",
                payload={
                    "profile_id": user_id,
                    "specialty": data.specialty,
                },
            )
        )[0]

        # Queue the invitation email for n8n.
        await self.db.request(
            "POST",
            "automation_events",
            payload={
                "event_type": "doctor_invitation",
                "aggregate_type": "doctor",
                "aggregate_id": doctor["id"],
                "recipient_profile_id": user_id,
                "recipient_email": data.email,
                "payload": {
                    "setup_url": setup_url,
                },
                "deduplication_key": (
                    f"doctor_invitation:{doctor['id']}"
                ),
            },
        )

        await self.audit(
            admin.id,
            "doctor_created",
            "doctor",
            doctor["id"],
        )

        return doctor

    async def admin_patients(self, search=None):
        params = {
            "role": "eq.patient",
            "select": (
                "id,full_name,email,phone,role,"
                "is_active,created_at"
            ),
            "order": "created_at.desc",
        }

        if search:
            params["or"] = (
                f"(full_name.ilike.*{search}*,"
                f"email.ilike.*{search}*,"
                f"phone.ilike.*{search}*)"
            )

        return await self._rows(
            "profiles",
            **params,
        )

    async def admin_appointments(
        self,
        doctor_id=None,
        day=None,
        status=None,
    ):
        params = {
            "select": (
                "id,patient_profile_id,doctor_id,start_at,"
                "end_at,status,rejection_reason,"
                "cancellation_reason,cancelled_at,created_at,"
                "profiles!appointments_patient_profile_id_fkey"
                "(full_name,email,phone),"
                "doctors(specialty,profiles(full_name))"
            ),
            "order": "start_at.desc",
        }

        if doctor_id:
            params["doctor_id"] = f"eq.{doctor_id}"

        if status:
            params["status"] = f"eq.{status}"

        if day:
            params["start_at"] = (
                f"gte.{day}T00:00:00Z"
            )

        return await self._rows(
            "appointments",
            **params,
        )

    async def deactivate_doctor(
        self,
        admin,
        doctor_id,
    ):
        doctor = await self._one(
            "doctors",
            id=f"eq.{doctor_id}",
            select="*",
        )

        row = (
            await self.db.request(
                "PATCH",
                "doctors",
                params={
                    "id": f"eq.{doctor_id}",
                },
                payload={
                    "is_active": False,
                },
            )
        )[0]

        await self.audit(
            admin.id,
            "doctor_deactivated",
            "doctor",
            doctor["id"],
        )

        return row

    async def dashboard(self):
        today = datetime.now(self.tz).date()

        appointments = await self.admin_appointments(
            day=today
        )

        counts = {}

        for item in appointments:
            key = item["doctor_id"]

            counts.setdefault(
                key,
                {
                    "pending": 0,
                    "confirmed": 0,
                    "completed": 0,
                    "no_show": 0,
                    "cancelled": 0,
                },
            )

            if item["status"] in counts[key]:
                counts[key][item["status"]] += 1

        return {
            "date": str(today),
            "today_appointments": appointments,
            "per_doctor_counts": counts,
        }

    async def expire_pending(self, actor_id):
        return await self.db.rpc(
            "expire_pending_appointments",
            {
                "p_actor_profile_id": str(actor_id),
            },
        )

    async def create_day_before_reminders(self):
        tomorrow = (
            datetime.now(self.tz).date()
            + timedelta(days=1)
        )

        day_after = tomorrow + timedelta(days=1)
        tomorrow_start = datetime.combine(
            tomorrow,
            time.min,
            tzinfo=self.tz,
        ).astimezone(timezone.utc)
        day_after_start = datetime.combine(
            day_after,
            time.min,
            tzinfo=self.tz,
        ).astimezone(timezone.utc)

        rows = await self._rows(
            "appointments",
            status="eq.confirmed",
            and_=(
                f"(start_at.gte.{tomorrow_start.isoformat()},"
                f"start_at.lt.{day_after_start.isoformat()})"
            ),
            select="id,patient_profile_id",
        )

        emitted = 0

        for row in rows:
            try:
                await self.db.request(
                    "POST",
                    "automation_events",
                    payload={
                        "event_type": "appointment_reminder",
                        "aggregate_type": "appointment",
                        "aggregate_id": row["id"],
                        "recipient_profile_id": row[
                            "patient_profile_id"
                        ],
                        "deduplication_key": (
                            "appointment_reminder:"
                            f"{row['id']}"
                        ),
                    },
                )

                emitted += 1

            except httpx.HTTPStatusError:
                pass

        return emitted

    async def availability(self, profile):
        doctor = await self.doctor_for(profile)

        return await self._rows(
            "doctor_availability",
            doctor_id=f"eq.{doctor['id']}",
            select="*",
            order="day_of_week,start_time",
        )

    async def add_availability(
        self,
        profile,
        data,
    ):
        if data.end_time <= data.start_time:
            raise HTTPException(
                400,
                "End time must be after start time.",
            )

        doctor = await self.doctor_for(profile)

        try:
            row = (
                await self.db.request(
                    "POST",
                    "doctor_availability",
                    payload={
                        **data.model_dump(mode="json"),
                        "doctor_id": doctor["id"],
                    },
                )
            )[0]

        except httpx.HTTPStatusError as error:
            raise HTTPException(
                409,
                "Availability overlaps an existing interval.",
            ) from error

        await self.audit(
            profile.id,
            "availability_created",
            "doctor_availability",
            row["id"],
        )

        return row

    async def update_availability(
        self,
        profile,
        availability_id,
        data,
    ):
        if data.end_time <= data.start_time:
            raise HTTPException(
                400,
                "End time must be after start time.",
            )

        doctor = await self.doctor_for(profile)

        row = await self._one(
            "doctor_availability",
            id=f"eq.{availability_id}",
            doctor_id=f"eq.{doctor['id']}",
            select="*",
        )

        try:
            updated = (
                await self.db.request(
                    "PATCH",
                    "doctor_availability",
                    params={
                        "id": f"eq.{row['id']}",
                    },
                    payload=data.model_dump(
                        mode="json"
                    ),
                )
            )[0]

        except httpx.HTTPStatusError as error:
            raise HTTPException(
                409,
                "Availability overlaps an existing interval.",
            ) from error

        await self.audit(
            profile.id,
            "availability_updated",
            "doctor_availability",
            updated["id"],
        )

        return updated

    async def delete_availability(
        self,
        profile,
        availability_id,
    ):
        doctor = await self.doctor_for(profile)

        row = await self._one(
            "doctor_availability",
            id=f"eq.{availability_id}",
            doctor_id=f"eq.{doctor['id']}",
            select="*",
        )

        await self.db.request(
            "DELETE",
            "doctor_availability",
            params={
                "id": f"eq.{row['id']}",
            },
        )

        await self.audit(
            profile.id,
            "availability_deleted",
            "doctor_availability",
            row["id"],
        )

    async def leaves(self, profile):
        doctor = await self.doctor_for(profile)

        return await self._rows(
            "doctor_leaves",
            doctor_id=f"eq.{doctor['id']}",
            select="*",
            order="leave_date",
        )

    async def add_leave(
        self,
        profile,
        data,
    ):
        if (
            data.leave_date
            <= datetime.now(self.tz).date()
        ):
            raise HTTPException(
                400,
                "Leave date must be in the future.",
            )

        doctor = await self.doctor_for(profile)

        try:
            row = (
                await self.db.rpc(
                    "add_doctor_leave",
                    {
                        "p_doctor_id": doctor["id"],
                        "p_leave_date": str(
                            data.leave_date
                        ),
                        "p_reason": data.reason,
                        "p_actor_profile_id": str(
                            profile.id
                        ),
                        "p_clinic_timezone": self.tz.key,
                    },
                )
            )[0]

        except httpx.HTTPStatusError as error:
            raise HTTPException(
                409,
                "Leave conflicts with an existing leave date.",
            ) from error

        return row

    async def delete_leave(
        self,
        profile,
        leave_id,
    ):
        doctor = await self.doctor_for(profile)

        row = await self._one(
            "doctor_leaves",
            id=f"eq.{leave_id}",
            doctor_id=f"eq.{doctor['id']}",
            select="*",
        )

        if (
            date.fromisoformat(row["leave_date"])
            <= datetime.now(self.tz).date()
        ):
            raise HTTPException(
                400,
                "Past leaves cannot be removed.",
            )

        await self.db.request(
            "DELETE",
            "doctor_leaves",
            params={
                "id": f"eq.{row['id']}",
            },
        )

        await self.audit(
            profile.id,
            "leave_deleted",
            "doctor_leave",
            row["id"],
        )

    async def reschedule(
        self,
        profile,
        appointment_id,
        data,
    ):
        existing = await self._one(
            "appointments",
            id=f"eq.{appointment_id}",
            patient_profile_id=f"eq.{profile.id}",
            select="id,status,start_at",
        )

        if existing["status"] not in ACTIVE:
            raise HTTPException(
                409,
                "Appointment cannot be rescheduled in its current state.",
            )

        start = datetime.fromisoformat(
            existing["start_at"].replace(
                "Z",
                "+00:00",
            )
        )

        if (
            start - now_utc()
            <= timedelta(hours=2)
        ):
            raise HTTPException(
                400,
                "Rescheduling is blocked within two hours.",
            )

        await self.validate_slot(
            profile,
            data.doctor_id,
            data.start_at,
            data.end_at,
        )

        try:
            return await self.db.rpc(
                "reschedule_patient_appointment",
                {
                    "p_appointment_id": str(
                        appointment_id
                    ),
                    "p_patient_id": str(
                        profile.id
                    ),
                    "p_doctor_id": str(
                        data.doctor_id
                    ),
                    "p_start_at": (
                        data.start_at.isoformat()
                    ),
                    "p_end_at": (
                        data.end_at.isoformat()
                    ),
                    "p_actor_profile_id": str(
                        profile.id
                    ),
                },
            )

        except httpx.HTTPStatusError as error:
            raise HTTPException(
                409,
                "Appointment could not be rescheduled.",
            ) from error
