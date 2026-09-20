-- Public signup can only create a patient profile. Elevated roles require a privileged server flow.
create function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
begin
  insert into public.profiles (id, full_name, email, phone, role)
  values (
    new.id,
    coalesce(nullif(left(trim(new.raw_user_meta_data ->> 'full_name'), 200), ''), 'New patient'),
    coalesce(nullif(left(trim(new.email), 320), ''), 'unknown-' || new.id::text || '@invalid.local'),
    nullif(left(trim(new.raw_user_meta_data ->> 'phone'), 50), ''),
    'patient'
  );
  return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_auth_user();
