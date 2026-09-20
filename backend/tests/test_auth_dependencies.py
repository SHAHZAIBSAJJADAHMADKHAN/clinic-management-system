import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.dependencies.auth import get_current_profile, get_current_user, require_role
from app.models.roles import UserRole
from app.schemas.auth import AuthenticatedUser, Profile
from app.core.config import Settings
from app.services.jwt_verifier import JwtVerifier, TokenVerificationError


def verifier_settings() -> Settings:
    return Settings(
        supabase_jwt_issuer="https://project.supabase.co/auth/v1",
        supabase_jwks_url="https://project.supabase.co/auth/v1/.well-known/jwks.json",
    )


def es256_key_and_token(
    *,
    kid: str = "current-kid",
    issuer: str = "https://project.supabase.co/auth/v1",
    expires_at: datetime | None = None,
    issued_at: datetime | None = None,
    not_before: datetime | None = None,
) -> tuple[jwt.PyJWK, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": kid, "alg": "ES256", "use": "sig"})
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(uuid4()),
        "iss": issuer,
        "aud": "authenticated",
        "iat": issued_at or now,
        "exp": expires_at or now + timedelta(minutes=5),
    }
    if not_before is not None:
        claims["nbf"] = not_before
    token = jwt.encode(
        claims,
        private_key,
        algorithm="ES256",
        headers={"kid": kid},
    )
    return jwt.PyJWK.from_dict(jwk), token


def test_missing_authorization_header_is_rejected() -> None:
    app = FastAPI()

    @app.get("/protected")
    async def protected(_: AuthenticatedUser = Depends(get_current_user)) -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app).get("/protected")
    assert response.status_code == 401


def test_malformed_bearer_token_is_rejected_without_network_access() -> None:
    app = FastAPI()

    @app.get("/protected")
    async def protected(_: AuthenticatedUser = Depends(get_current_user)) -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app).get("/protected", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


def test_role_dependency_rejects_wrong_role() -> None:
    profile = Profile(
        id=uuid4(), full_name="Test Patient", email="patient@example.test", role=UserRole.PATIENT, is_active=True
    )
    app = FastAPI()
    app.dependency_overrides[get_current_profile] = lambda: profile

    @app.get("/admin")
    async def admin_only(_: Profile = Depends(require_role(UserRole.ADMIN))) -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app).get("/admin")
    assert response.status_code == 403


def test_role_dependency_accepts_matching_role() -> None:
    profile = Profile(id=uuid4(), full_name="Test Admin", email="admin@example.test", role=UserRole.ADMIN, is_active=True)
    app = FastAPI()
    app.dependency_overrides[get_current_profile] = lambda: profile

    @app.get("/admin")
    async def admin_only(_: Profile = Depends(require_role(UserRole.ADMIN))) -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app).get("/admin")
    assert response.status_code == 200


def test_jwt_verifier_refreshes_a_stale_jwks_key_after_signature_failure(monkeypatch) -> None:
    client = SimpleNamespace(
        get_signing_key_from_jwt=lambda _: SimpleNamespace(key="public-key")
    )
    from app.services import jwt_verifier

    jwks_client = Mock(return_value=client)
    jwks_client.cache_clear = Mock()
    monkeypatch.setattr(jwt_verifier, "_jwks_client", jwks_client)
    monkeypatch.setattr(jwt_verifier.jwt, "get_unverified_header", lambda _: {"alg": "ES256", "kid": "current"})
    monkeypatch.setattr(
        jwt_verifier.jwt,
        "decode",
        Mock(
            side_effect=[
                jwt.InvalidSignatureError("stale key"),
                {"sub": str(uuid4()), "exp": 2_000_000_000, "iss": "https://project.supabase.co/auth/v1", "aud": "authenticated"},
            ]
        ),
    )

    user = JwtVerifier(Settings(supabase_jwt_issuer="https://project.supabase.co/auth/v1", supabase_jwks_url="https://project.supabase.co/auth/v1/.well-known/jwks.json")).verify("token")

    assert user.id
    assert jwks_client.cache_clear.called


def test_jwt_verifier_refreshes_jwks_after_an_unknown_kid_lookup(monkeypatch) -> None:
    from app.services import jwt_verifier

    signing_key, token = es256_key_and_token()
    stale_client = SimpleNamespace(
        get_signing_key_from_jwt=Mock(
            side_effect=jwt.PyJWKClientError("Unable to find a signing key")
        )
    )
    fresh_client = SimpleNamespace(
        get_signing_key_from_jwt=Mock(return_value=signing_key)
    )
    jwks_client = Mock(side_effect=[stale_client, fresh_client])
    jwks_client.cache_clear = Mock()
    monkeypatch.setattr(jwt_verifier, "_jwks_client", jwks_client)

    user = JwtVerifier(verifier_settings()).verify(token)

    assert user.id
    assert jwks_client.cache_clear.called
    assert fresh_client.get_signing_key_from_jwt.called


def test_jwt_verifier_rejects_an_unknown_kid_after_one_fresh_jwks_lookup(monkeypatch) -> None:
    from app.services import jwt_verifier

    _, token = es256_key_and_token(kid="unknown-kid")
    client = SimpleNamespace(
        get_signing_key_from_jwt=Mock(
            side_effect=jwt.PyJWKClientError("Unable to find a signing key")
        )
    )
    jwks_client = Mock(return_value=client)
    jwks_client.cache_clear = Mock()
    monkeypatch.setattr(jwt_verifier, "_jwks_client", jwks_client)

    with pytest.raises(TokenVerificationError) as raised:
        JwtVerifier(verifier_settings()).verify(token)

    assert raised.value.code == "jwks_key_lookup"
    assert jwks_client.cache_clear.called


def test_jwt_verifier_accepts_a_real_es256_token_with_matching_jwks_kid(monkeypatch) -> None:
    from app.services import jwt_verifier

    signing_key, token = es256_key_and_token(kid="matching-kid")
    client = SimpleNamespace(
        get_signing_key_from_jwt=Mock(return_value=signing_key)
    )
    monkeypatch.setattr(jwt_verifier, "_jwks_client", Mock(return_value=client))

    user = JwtVerifier(verifier_settings()).verify(token)

    assert user.id
    assert client.get_signing_key_from_jwt.called


@pytest.mark.parametrize("claim", ["iat", "nbf"])
def test_jwt_verifier_accepts_small_future_time_claims_within_leeway(monkeypatch, claim) -> None:
    from app.services import jwt_verifier

    future = datetime.now(timezone.utc) + timedelta(seconds=5)
    signing_key, token = es256_key_and_token(
        issued_at=future if claim == "iat" else None,
        not_before=future if claim == "nbf" else None,
    )
    client = SimpleNamespace(get_signing_key_from_jwt=Mock(return_value=signing_key))
    monkeypatch.setattr(jwt_verifier, "_jwks_client", Mock(return_value=client))

    assert JwtVerifier(verifier_settings()).verify(token).id


@pytest.mark.parametrize("claim", ["iat", "nbf"])
def test_jwt_verifier_rejects_future_time_claims_beyond_leeway(monkeypatch, claim) -> None:
    from app.services import jwt_verifier

    future = datetime.now(timezone.utc) + timedelta(seconds=31)
    signing_key, token = es256_key_and_token(
        issued_at=future if claim == "iat" else None,
        not_before=future if claim == "nbf" else None,
    )
    client = SimpleNamespace(get_signing_key_from_jwt=Mock(return_value=signing_key))
    monkeypatch.setattr(jwt_verifier, "_jwks_client", Mock(return_value=client))

    with pytest.raises(TokenVerificationError) as raised:
        JwtVerifier(verifier_settings()).verify(token)

    assert raised.value.code == "immature_signature"
    assert raised.value.diagnostics["exception"] == "ImmatureSignatureError"


def test_jwt_verifier_rejects_a_real_es256_token_signed_by_a_different_key(monkeypatch) -> None:
    from app.services import jwt_verifier

    _, token = es256_key_and_token(kid="matching-kid")
    wrong_key, _ = es256_key_and_token(kid="matching-kid")
    client = SimpleNamespace(get_signing_key_from_jwt=Mock(return_value=wrong_key))
    monkeypatch.setattr(jwt_verifier, "_jwks_client", Mock(return_value=client))

    with pytest.raises(TokenVerificationError) as raised:
        JwtVerifier(verifier_settings()).verify(token)

    assert raised.value.code == "invalid_signature"


def test_jwt_verifier_rejects_expired_or_wrong_issuer_es256_tokens(monkeypatch) -> None:
    from app.services import jwt_verifier

    expired_key, expired = es256_key_and_token(
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=31)
    )
    wrong_issuer_key, wrong_issuer = es256_key_and_token(
        issuer="https://other-project.supabase.co/auth/v1"
    )
    client = SimpleNamespace(
        get_signing_key_from_jwt=Mock(side_effect=[expired_key, wrong_issuer_key])
    )
    monkeypatch.setattr(jwt_verifier, "_jwks_client", Mock(return_value=client))

    with pytest.raises(TokenVerificationError) as expired_error:
        JwtVerifier(verifier_settings()).verify(expired)
    with pytest.raises(TokenVerificationError) as issuer_error:
        JwtVerifier(verifier_settings()).verify(wrong_issuer)

    assert expired_error.value.code == "expired_signature"
    assert issuer_error.value.code == "invalid_issuer"
    assert expired_error.value.diagnostics["exception"] == "ExpiredSignatureError"
    assert issuer_error.value.diagnostics["exception"] == "InvalidIssuerError"


def test_jwt_verifier_classifies_an_invalid_audience_without_exposing_claim_values(monkeypatch) -> None:
    from app.services import jwt_verifier

    client = SimpleNamespace(
        get_signing_key_from_jwt=lambda _: SimpleNamespace(key="public-key", key_id="matching-kid")
    )
    monkeypatch.setattr(jwt_verifier, "_jwks_client", Mock(return_value=client))
    monkeypatch.setattr(jwt_verifier.jwt, "get_unverified_header", lambda _: {"alg": "ES256", "kid": "matching-kid"})
    monkeypatch.setattr(
        jwt_verifier.jwt,
        "decode",
        Mock(side_effect=[jwt.InvalidAudienceError("wrong audience"), {"iss": "https://project.supabase.co/auth/v1", "aud": "other", "exp": 2_000_000_000, "iat": 1}]),
    )

    with pytest.raises(TokenVerificationError) as raised:
        JwtVerifier(
            Settings(
                supabase_jwt_issuer="https://project.supabase.co/auth/v1",
                supabase_jwks_url="https://project.supabase.co/auth/v1/.well-known/jwks.json",
            )
        ).verify("token")

    assert raised.value.code == "invalid_audience"
    assert raised.value.diagnostics == {
        "alg": "ES256",
        "kid": "present",
        "kid_match": "yes",
        "jwk_alg": "other",
        "jwk_kty": "other",
        "issuer_match": "yes",
        "audience_match": "no",
        "exp": "present",
        "iat": "present",
        "exception": "InvalidAudienceError",
    }


def test_auth_failure_response_remains_generic_without_diagnostic_header(monkeypatch) -> None:
    from app.dependencies import auth as auth_dependencies

    app = FastAPI()
    app.dependency_overrides[auth_dependencies.get_settings] = lambda: Settings(environment="development")

    @app.get("/protected")
    async def protected(_: AuthenticatedUser = Depends(get_current_user)) -> dict[str, bool]:
        return {"ok": True}

    def reject(_: object, __: object) -> AuthenticatedUser:
        raise TokenVerificationError("invalid_signature", {"alg": "ES256", "kid_match": "yes"})

    monkeypatch.setattr(auth_dependencies.JwtVerifier, "verify", reject)
    response = TestClient(app).get("/protected", headers={"Authorization": "Bearer opaque"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired bearer token."}
    assert "x-clinic-auth-diagnostic" not in response.headers
