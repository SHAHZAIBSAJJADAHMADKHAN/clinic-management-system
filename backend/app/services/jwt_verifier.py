from functools import lru_cache
from uuid import UUID

import jwt
from jwt import PyJWKClient
from jwt import exceptions as jwt_exceptions

from app.core.config import Settings
from app.schemas.auth import AuthenticatedUser


class TokenVerificationError(Exception):
    """Raised when a bearer token cannot be securely verified."""

    def __init__(self, code: str, diagnostics: dict[str, str] | None = None) -> None:
        # Keep the exception message and public API error deliberately generic.
        # Diagnostics contain only non-secret verification facts for local debugging.
        super().__init__("The bearer token is invalid or expired.")
        self.code = code
        self.diagnostics = diagnostics or {}


@lru_cache(maxsize=8)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    """Return a short-lived JWKS client without a second per-kid key cache."""
    return PyJWKClient(
        jwks_url,
        cache_keys=False,
        lifespan=60,
    )


class JwtVerifier:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def verify(self, token: str) -> AuthenticatedUser:
        diagnostics: dict[str, str] = {}
        try:
            # Parse the protected JWT header first.
            # Claims are not trusted until signature verification succeeds.
            header = jwt.get_unverified_header(token)
            diagnostics["alg"] = self._safe_algorithm(header.get("alg"))
            diagnostics["kid"] = "present" if header.get("kid") else "missing"

            if (
                not self._settings.supabase_jwks_url
                or not self._settings.supabase_jwt_issuer
            ):
                raise RuntimeError("JWT verification is not configured.")

            # Fetch the correct public signing key from Supabase JWKS
            # using the token's key ID (kid).
            claims = self._decode(token, header, diagnostics)

            return AuthenticatedUser(
                id=UUID(claims["sub"]),
                email=claims.get("email"),
            )

        except (jwt.PyJWTError, ValueError, KeyError) as error:
            diagnostics.update(self._unverified_claim_diagnostics(token))
            diagnostics["exception"] = type(error).__name__
            raise TokenVerificationError(
                self._error_code(error), diagnostics
            ) from error

    def _decode(
        self, token: str, header: dict, diagnostics: dict[str, str]
    ) -> dict:
        def decode_with_current_key() -> dict:
            signing_key = _jwks_client(
                self._settings.supabase_jwks_url
            ).get_signing_key_from_jwt(token)
            key_id = getattr(signing_key, "key_id", None)
            diagnostics["kid_match"] = (
                "yes" if key_id and key_id == header.get("kid") else "no"
            )
            diagnostics["jwk_alg"] = self._safe_algorithm(
                getattr(signing_key, "algorithm_name", None)
            )
            diagnostics["jwk_kty"] = self._safe_key_type(
                getattr(signing_key, "key_type", None)
            )

            # Verify signature, asymmetric algorithm, issuer, audience,
            # required claims, and expiration.
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                issuer=self._settings.supabase_jwt_issuer,
                audience="authenticated",
                leeway=self._settings.supabase_jwt_leeway_seconds,
                options={
                    "require": ["sub", "exp", "iss"],
                },
            )

        try:
            return decode_with_current_key()
        except (jwt.InvalidSignatureError, jwt_exceptions.PyJWKClientError):
            # Refresh once for either form of key rotation: an existing kid
            # with changed key material, or a newly issued kid absent from a
            # cached JWK set. The second verification remains fully strict.
            _jwks_client.cache_clear()
            return decode_with_current_key()

    def _unverified_claim_diagnostics(self, token: str) -> dict[str, str]:
        """Return only comparison/presence facts; never claim values or the token."""
        try:
            claims = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_aud": False,
                    "verify_iss": False,
                },
            )
        except jwt.PyJWTError:
            return {"claims": "unreadable"}

        audience = claims.get("aud")
        audience_matches = (
            audience == "authenticated"
            or (
                isinstance(audience, list)
                and "authenticated" in audience
            )
        )
        return {
            "issuer_match": "yes"
            if claims.get("iss") == self._settings.supabase_jwt_issuer
            else "no",
            "audience_match": "yes" if audience_matches else "no",
            "exp": "present" if "exp" in claims else "missing",
            "iat": "present" if "iat" in claims else "missing",
        }

    @staticmethod
    def _safe_algorithm(algorithm: object) -> str:
        return algorithm if algorithm in {"RS256", "ES256"} else "other"

    @staticmethod
    def _safe_key_type(key_type: object) -> str:
        return key_type if key_type in {"EC", "RSA"} else "other"

    @staticmethod
    def _error_code(error: Exception) -> str:
        if isinstance(error, jwt_exceptions.ExpiredSignatureError):
            return "expired_signature"
        if isinstance(error, jwt_exceptions.ImmatureSignatureError):
            return "immature_signature"
        if isinstance(error, jwt_exceptions.InvalidSignatureError):
            return "invalid_signature"
        if isinstance(error, jwt_exceptions.InvalidIssuerError):
            return "invalid_issuer"
        if isinstance(error, jwt_exceptions.InvalidAudienceError):
            return "invalid_audience"
        if isinstance(error, jwt_exceptions.InvalidAlgorithmError):
            return "invalid_algorithm"
        if isinstance(error, jwt_exceptions.MissingRequiredClaimError):
            return "missing_required_claim"
        if isinstance(error, (jwt_exceptions.PyJWKClientError, jwt_exceptions.PyJWKError)):
            return "jwks_key_lookup"
        if isinstance(error, jwt_exceptions.DecodeError):
            return "malformed_token"
        if isinstance(error, (ValueError, KeyError)):
            return "invalid_claims"
        return "jwt_verification_error"
