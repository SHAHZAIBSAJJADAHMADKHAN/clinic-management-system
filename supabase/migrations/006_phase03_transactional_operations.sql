-- Phase 03 atomic operations. Execute after 001-005; does not alter existing constraints or RLS.
create or replace function public.add_doctor_leave(
  p_doctor_id uuid, p_leave_date date, p_reason text, p_actor_profile_id uuid, p_clinic_timezone text default 'UTC'
) returns setof public.doctor_leaves language plpgsql security definer set search_path = public as $$
declare v_leave public.doctor_leaves; v_appointment public.appointments;
begin
  insert into doctor_leaves (doctor_id, leave_date, reason) values (p_doctor_id,p_leave_date,p_reason) returning * into v_leave;
  for v_appointment in
    update appointments set status='cancelled', cancelled_at=now(), cancellation_reason='Doctor leave'
    where doctor_id=p_doctor_id and (start_at at time zone p_clinic_timezone)::date = p_leave_date
      and status in ('pending','confirmed') returning *
  loop
    insert into automation_events(event_type,aggregate_type,aggregate_id,recipient_profile_id,deduplication_key)
      values ('appointment_cancelled_leave','appointment',v_appointment.id,v_appointment.patient_profile_id,'appointment_cancelled_leave:'||v_appointment.id)
      on conflict (deduplication_key) do nothing;
    insert into audit_logs(actor_profile_id,action,entity_type,entity_id) values(p_actor_profile_id,'appointment_cancelled_leave','appointment',v_appointment.id);
  end loop;
  insert into audit_logs(actor_profile_id,action,entity_type,entity_id) values(p_actor_profile_id,'leave_created','doctor_leave',v_leave.id);
  return next v_leave;
end; $$;

-- Reminder deduplication is enforced by automation_events.deduplication_key; the API
-- selects only confirmed appointments in the clinic's next-day window.

create or replace function public.reschedule_patient_appointment(
 p_appointment_id uuid,p_patient_id uuid,p_doctor_id uuid,p_start_at timestamptz,p_end_at timestamptz,p_actor_profile_id uuid
) returns public.appointments language plpgsql security definer set search_path = public as $$
declare v_old public.appointments; v_new public.appointments;
begin
 select * into v_old from appointments where id=p_appointment_id and patient_profile_id=p_patient_id for update;
 if not found then raise exception 'appointment not found'; end if;
 if v_old.status not in ('pending','confirmed') or v_old.start_at <= now()+interval '2 hours' then raise exception 'appointment cannot be rescheduled'; end if;
 update appointments set doctor_id=p_doctor_id,start_at=p_start_at,end_at=p_end_at,status='pending',rejection_reason=null,cancellation_reason=null,cancelled_at=null where id=p_appointment_id returning * into v_new;
 insert into automation_events(event_type,aggregate_type,aggregate_id,recipient_profile_id,deduplication_key) values ('appointment_rescheduled','appointment',v_new.id,p_patient_id,'appointment_rescheduled:'||v_new.id||':'||v_new.updated_at) on conflict (deduplication_key) do nothing;
 insert into audit_logs(actor_profile_id,action,entity_type,entity_id) values(p_actor_profile_id,'appointment_rescheduled','appointment',v_new.id);
 return v_new;
end; $$;

create or replace function public.expire_pending_appointments(p_actor_profile_id uuid default null)
returns integer language plpgsql security definer set search_path = public as $$
declare r public.appointments; n integer:=0;
begin
 for r in update appointments set status='cancelled',cancelled_at=now(),cancellation_reason='Pending appointment expired' where status='pending' and start_at<=now() returning * loop
  insert into automation_events(event_type,aggregate_type,aggregate_id,recipient_profile_id,deduplication_key) values ('appointment_pending_expired','appointment',r.id,r.patient_profile_id,'appointment_pending_expired:'||r.id) on conflict (deduplication_key) do nothing;
  n:=n+1;
 end loop; return n;
end; $$;

-- These SECURITY DEFINER functions are invoked only by the server's service-role credentials.
-- Signatures below exactly match the definitions above (defaults are not part of a signature).
revoke all on function public.add_doctor_leave(uuid,date,text,uuid,text) from public;
revoke all on function public.reschedule_patient_appointment(uuid,uuid,uuid,timestamptz,timestamptz,uuid) from public;
revoke all on function public.expire_pending_appointments(uuid) from public;
revoke all on function public.add_doctor_leave(uuid,date,text,uuid,text) from anon, authenticated;
revoke all on function public.reschedule_patient_appointment(uuid,uuid,uuid,timestamptz,timestamptz,uuid) from anon, authenticated;
revoke all on function public.expire_pending_appointments(uuid) from anon, authenticated;
grant execute on function public.add_doctor_leave(uuid,date,text,uuid,text) to service_role;
grant execute on function public.reschedule_patient_appointment(uuid,uuid,uuid,timestamptz,timestamptz,uuid) to service_role;
grant execute on function public.expire_pending_appointments(uuid) to service_role;
