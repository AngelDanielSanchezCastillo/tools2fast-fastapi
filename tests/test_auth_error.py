"""
Tests for ``APIResponse.auth_error`` — standardized auth error responses.

The helper builds a ready-to-return ``JSONResponse`` carrying the project
envelope (``success=False, error_type="controlled", message, error``) and, for
401 responses, the RFC 6750 ``WWW-Authenticate`` header.
"""

import json

from fastapi.responses import JSONResponse

from tools2fast_fastapi.schemas.response_schema import APIResponse


def _payload(response: JSONResponse) -> dict:
    """Decode the JSON body of a JSONResponse."""
    return json.loads(response.body.decode())


class TestAuthErrorDefaults:
    """Default behavior: 401 with a bare Bearer challenge."""

    def test_returns_json_response(self):
        """RED: auth_error returns a JSONResponse instance."""
        response = APIResponse.auth_error(
            error_code="TokenExpired",
            message="Token expirado",
        )
        assert isinstance(response, JSONResponse)

    def test_default_status_is_401(self):
        """RED: default HTTP status must be 401."""
        response = APIResponse.auth_error(
            error_code="TokenExpired",
            message="Token expirado",
        )
        assert response.status_code == 401

    def test_default_www_authenticate_is_bearer(self):
        """RED: 401 without explicit challenge defaults to ``Bearer``."""
        response = APIResponse.auth_error(
            error_code="TokenMissing",
            message="Token requerido",
        )
        assert response.headers.get("www-authenticate") == "Bearer"

    def test_envelope_shape(self):
        """RED: body follows the project envelope with error.type as code."""
        response = APIResponse.auth_error(
            error_code="TokenInvalid",
            message="Token inválido",
        )
        body = _payload(response)
        assert body["success"] is False
        assert body["error_type"] == "controlled"
        assert body["message"] == "Token inválido"
        assert body["error"]["type"] == "TokenInvalid"
        assert body["error"]["detail"] == "Token inválido"


class TestAuthErrorChallenge:
    """Custom RFC 6750 challenge values."""

    def test_custom_expired_token_challenge(self):
        """RED: explicit ``error="expired_token"`` challenge is preserved."""
        response = APIResponse.auth_error(
            error_code="TokenExpired",
            message="Token expirado",
            status_code=401,
            www_authenticate='Bearer error="expired_token"',
        )
        assert (
            response.headers.get("www-authenticate") == 'Bearer error="expired_token"'
        )

    def test_custom_invalid_token_challenge(self):
        """RED: explicit ``error="invalid_token"`` challenge is preserved."""
        response = APIResponse.auth_error(
            error_code="TokenInvalid",
            message="Token inválido",
            www_authenticate='Bearer error="invalid_token"',
        )
        assert (
            response.headers.get("www-authenticate") == 'Bearer error="invalid_token"'
        )


class TestAuthErrorForbidden:
    """403 is authorization, not authentication: no Bearer challenge."""

    def test_forbidden_status(self):
        """RED: 403 status is honored."""
        response = APIResponse.auth_error(
            error_code="PermissionDenied",
            message="Permisos insuficientes",
            status_code=403,
        )
        assert response.status_code == 403

    def test_forbidden_has_no_www_authenticate(self):
        """RED: 403 must not advertise a Bearer challenge."""
        response = APIResponse.auth_error(
            error_code="PermissionDenied",
            message="Permisos insuficientes",
            status_code=403,
        )
        assert response.headers.get("www-authenticate") is None

    def test_forbidden_envelope_shape(self):
        """RED: 403 keeps the same envelope and error code."""
        response = APIResponse.auth_error(
            error_code="TenantRequired",
            message="Se requiere un tenant",
            status_code=403,
        )
        body = _payload(response)
        assert body["success"] is False
        assert body["error"]["type"] == "TenantRequired"


from fastapi import FastAPI
from fastapi.testclient import TestClient

from tools2fast_fastapi import AuthError, install_auth_error_handler


class TestAuthErrorException:
    """AuthError is raised from dependencies to short-circuit the endpoint."""

    def test_defaults(self):
        """RED: default status is 401 and no explicit challenge."""
        exc = AuthError(error_code="TokenMissing", message="Credenciales requeridas")
        assert exc.status_code == 401
        assert exc.error_code == "TokenMissing"
        assert exc.message == "Credenciales requeridas"
        assert exc.www_authenticate is None


class TestInstallAuthErrorHandler:
    """The handler turns AuthError into the project envelope."""

    def _app(self) -> FastAPI:
        app = FastAPI()
        install_auth_error_handler(app)

        @app.get("/unauthorized")
        async def unauthorized() -> None:
            raise AuthError(
                error_code="TokenExpired",
                message="Token expirado",
                www_authenticate='Bearer error="expired_token"',
            )

        @app.get("/forbidden")
        async def forbidden() -> None:
            raise AuthError(
                error_code="PermissionDenied",
                message="Permisos insuficientes",
                status_code=403,
            )

        return app

    def test_401_envelope_and_challenge(self):
        """RED: AuthError becomes a 401 envelope with the challenge header."""
        response = TestClient(self._app()).get("/unauthorized")

        assert response.status_code == 401
        body = response.json()
        assert body["success"] is False
        assert body["error"]["type"] == "TokenExpired"
        assert (
            response.headers.get("www-authenticate") == 'Bearer error="expired_token"'
        )

    def test_403_envelope_without_challenge(self):
        """RED: AuthError becomes a 403 envelope without Bearer challenge."""
        response = TestClient(self._app()).get("/forbidden")

        assert response.status_code == 403
        body = response.json()
        assert body["error"]["type"] == "PermissionDenied"
        assert response.headers.get("www-authenticate") is None
