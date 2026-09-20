-- RLS is defense-in-depth. Operational mutations are performed by FastAPI using server credentials.
alter table public.profiles enable row level security;
alter table public.doctors enable row level security;
alter table public.doctor_availability enable row level security;
alter table public.doctor_leaves enable row level security;
alter table public.appointments enable row level security;
alter table public.visit_notes enable row level security;
alter table public.audit_logs enable row level security;
alter table public.automation_events enable row level security;

create policy profiles_select_own on public.profiles for select to authenticated using (id = auth.uid());
create policy doctors_select_own on public.doctors for select to authenticated using (profile_id = auth.uid());
create policy availability_select_own_doctor on public.doctor_availability for select to authenticated using (
  exists (select 1 from public.doctors d where d.id = doctor_id and d.profile_id = auth.uid())
);
create policy leaves_select_own_doctor on public.doctor_leaves for select to authenticated using (
  exists (select 1 from public.doctors d where d.id = doctor_id and d.profile_id = auth.uid())
);
create policy appointments_select_involved on public.appointments for select to authenticated using (
  patient_profile_id = auth.uid()
  or exists (select 1 from public.doctors d where d.id = doctor_id and d.profile_id = auth.uid())
);
create policy visit_notes_select_involved_only on public.visit_notes for select to authenticated using (
  patient_profile_id = auth.uid()
  or exists (select 1 from public.doctors d where d.id = doctor_id and d.profile_id = auth.uid())
);
create policy visit_notes_insert_involved_doctor_only on public.visit_notes for insert to authenticated with check (
  exists (select 1 from public.doctors d where d.id = doctor_id and d.profile_id = auth.uid())
);
create policy visit_notes_update_involved_doctor_only on public.visit_notes for update to authenticated
  using (exists (select 1 from public.doctors d where d.id = doctor_id and d.profile_id = auth.uid()))
  with check (exists (select 1 from public.doctors d where d.id = doctor_id and d.profile_id = auth.uid()));

-- No policies are intentionally created for audit_logs or automation_events. No client role can read them.
-- No direct client mutation policies exist for profiles, doctors, availability, leaves, or appointments.
