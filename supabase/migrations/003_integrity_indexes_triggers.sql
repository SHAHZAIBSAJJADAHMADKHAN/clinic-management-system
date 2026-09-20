-- Cross-table integrity, query indexes, and shared updated_at triggers.
create function public.ensure_doctor_profile_role()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1 from public.profiles where id = new.profile_id and role = 'doctor'
  ) then
    raise exception 'Doctor record requires a profile with doctor role';
  end if;
  return new;
end;
$$;

create trigger doctors_require_doctor_profile
before insert or update of profile_id on public.doctors
for each row execute function public.ensure_doctor_profile_role();

create function public.prevent_doctor_profile_role_demotion()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.role <> 'doctor' and exists (select 1 from public.doctors where profile_id = new.id) then
    raise exception 'A profile linked to a doctor record must retain the doctor role';
  end if;
  return new;
end;
$$;

create trigger profiles_prevent_doctor_role_demotion
before update of role on public.profiles
for each row execute function public.prevent_doctor_profile_role_demotion();

create function public.ensure_appointment_patient_role()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1 from public.profiles where id = new.patient_profile_id and role = 'patient'
  ) then
    raise exception 'Appointment patient must have the patient role';
  end if;
  return new;
end;
$$;

create trigger appointments_require_patient_profile
before insert or update of patient_profile_id on public.appointments
for each row execute function public.ensure_appointment_patient_role();

create function public.ensure_visit_note_matches_appointment()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1 from public.appointments
    where id = new.appointment_id
      and doctor_id = new.doctor_id
      and patient_profile_id = new.patient_profile_id
  ) then
    raise exception 'Visit note doctor and patient must match its appointment';
  end if;
  return new;
end;
$$;

create trigger visit_notes_match_appointment
before insert or update of appointment_id, doctor_id, patient_profile_id on public.visit_notes
for each row execute function public.ensure_visit_note_matches_appointment();

create index appointments_doctor_start_at_idx on public.appointments (doctor_id, start_at);
create index appointments_patient_start_at_idx on public.appointments (patient_profile_id, start_at);
create index appointments_status_start_at_idx on public.appointments (status, start_at);
create index doctor_availability_lookup_idx on public.doctor_availability (doctor_id, day_of_week);
create index doctor_leaves_lookup_idx on public.doctor_leaves (doctor_id, leave_date);
create index audit_logs_entity_lookup_idx on public.audit_logs (entity_type, entity_id, created_at desc);
create index automation_events_pending_idx on public.automation_events (available_at)
  where status in ('pending', 'failed');

create trigger profiles_set_updated_at before update on public.profiles
for each row execute function public.set_updated_at();
create trigger doctors_set_updated_at before update on public.doctors
for each row execute function public.set_updated_at();
create trigger doctor_availability_set_updated_at before update on public.doctor_availability
for each row execute function public.set_updated_at();
create trigger appointments_set_updated_at before update on public.appointments
for each row execute function public.set_updated_at();
create trigger visit_notes_set_updated_at before update on public.visit_notes
for each row execute function public.set_updated_at();
create trigger automation_events_set_updated_at before update on public.automation_events
for each row execute function public.set_updated_at();
