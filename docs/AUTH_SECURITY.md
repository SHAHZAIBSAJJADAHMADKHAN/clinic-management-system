# Authentication and Security Foundation

Supabase Auth owns credentials and user identity. A secure `auth.users` trigger creates an application `profiles` record with the fixed `patient` role for normal signup; metadata may populate display data but can never grant `doctor` or `admin`.

FastAPI accepts only HTTP Bearer tokens. The reusable verifier obtains signing keys from the configured Supabase JWKS URL using PyJWT's cached JWKS client, verifies the signature, requires subject/issuer/expiration claims, validates the configured issuer, and parses the Supabase user UUID only after verification. It does not use unsigned JWT decoding, client-supplied roles, or local-storage role values as authorization authority.

Future endpoints use `get_current_user`, `get_current_profile`, and `require_role(...)` / `require_admin`, `require_doctor`, or `require_patient`. Profile lookup happens server-side. Inactive or missing profiles are rejected.

`SUPABASE_PUBLISHABLE_KEY` is suitable only for constrained public operations. `SUPABASE_SECRET_KEY` is server-only, is used solely by the profile repository foundation, and must never enter a `VITE_` variable, client response, log, or public document. The frontend API helper can accept an access token for its Authorization header but has no role bypass.
