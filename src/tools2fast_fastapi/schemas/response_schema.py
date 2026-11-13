"""
Schemas de respuesta estándar para todos los endpoints.

Jerarquía de modelos (Phase 1: Unified API Responses):

    BaseSuccessResponse        → HTTP 200/201, success: true
    BaseControlledErrorResponse → HTTP 400/404/etc, success: false, error_type: "controlled"
    BaseUnexpectedErrorResponse → HTTP 500, success: false, error_type: "unexpected"
    BasePaymentRequiredResponse → HTTP 402, success: false, error_type: "payment_required"

Factoría:
    APIResponse → métodos estáticos que devuelven los modelos anteriores.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from tools2fast_fastapi.schemas.mixins import (
    ErrorDetail,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH ERROR — excepción para dependencies
# ═══════════════════════════════════════════════════════════════════════════════


class AuthError(HTTPException):
    """Authentication/authorization failure raised from FastAPI dependencies.

    Dependencies cannot return a ``Response`` to short-circuit the endpoint
    (FastAPI injects it as the dependency value instead). Raising this
    exception, together with :func:`install_auth_error_handler`, produces the
    same envelope and RFC 6750 challenge as :meth:`APIResponse.auth_error`.

    It subclasses :class:`fastapi.HTTPException` on purpose: if an application
    forgets to install the handler, the status code and ``WWW-Authenticate``
    header are still correct (the body falls back to FastAPI's ``detail``
    shape instead of becoming a 500).

    Attributes:
        status_code: HTTP status (usually 401 or 403).
        error_code: Stable discriminator stored in ``error.type``.
        message: User-facing message (Spanish).
        www_authenticate: Optional ``WWW-Authenticate`` value. Defaults to
            ``Bearer`` for 401 responses.
    """

    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        status_code: int = status.HTTP_401_UNAUTHORIZED,
        www_authenticate: str | None = None,
    ) -> None:
        headers: dict[str, str] = {}
        if www_authenticate is not None or status_code == status.HTTP_401_UNAUTHORIZED:
            headers["WWW-Authenticate"] = www_authenticate or "Bearer"

        self.error_code = error_code
        self.message = message
        self.www_authenticate = www_authenticate
        super().__init__(
            status_code=status_code,
            detail=message,
            headers=headers or None,
        )


def install_auth_error_handler(app: FastAPI) -> None:
    """Register the ``AuthError`` handler on a FastAPI application.

    Call once during app startup, before serving requests:

    .. code-block:: python

        from tools2fast_fastapi import install_auth_error_handler

        app = FastAPI()
        install_auth_error_handler(app)

    Args:
        app: The FastAPI application instance.
    """

    @app.exception_handler(AuthError)
    async def _handle_auth_error(_request, exc: AuthError) -> JSONResponse:
        return APIResponse.auth_error(
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
            www_authenticate=exc.www_authenticate,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# RESPUESTAS — Phase 1: Unified API Responses
# ═══════════════════════════════════════════════════════════════════════════════


class BaseSuccessResponse(BaseModel):
    """Respuesta exitosa con payload data (200/201).

    Attributes:
        success: Siempre ``True``.
        message: Mensaje descriptivo. Por defecto ``"Éxito"``.
        data: Payload con los datos de respuesta.
    """

    success: Literal[True] = True
    message: str = "Éxito"
    data: Any = None


class BaseControlledErrorResponse(BaseModel):
    """Respuesta de error controlado (400/404/etc).

    Para errores de validación de negocio, recursos no encontrados, etc.

    Attributes:
        success: Siempre ``False``.
        error_type: Siempre ``"controlled"``.
        message: Mensaje legible para el usuario.
        error: Detalle estructurado del error.
    """

    success: Literal[False] = False
    error_type: Literal["controlled"] = "controlled"
    message: str
    error: ErrorDetail | None = None


class BaseUnexpectedErrorResponse(BaseModel):
    """Respuesta de error inesperado del servidor (500).

    Para errores no manejados que no deberían ocurrir en producción.

    Attributes:
        success: Siempre ``False``.
        error_type: Siempre ``"unexpected"``.
        message: Siempre ``"Ha ocurrido un error"`` (para no exponer detalles).
        error: Detalle estructurado (detail oculto en producción).
    """

    success: Literal[False] = False
    error_type: Literal["unexpected"] = "unexpected"
    message: str = "Ha ocurrido un error"
    error: ErrorDetail | None = None


class BasePaymentRequiredResponse(BaseModel):
    """Respuesta de pago requerido (402).

    Cuando el usuario tiene la subscripción vencida.

    Attributes:
        success: Siempre ``False``.
        error_type: Siempre ``"payment_required"``.
        message: Mensaje legible para el usuario.
        error: Detalle estructurado del error.
    """

    success: Literal[False] = False
    error_type: Literal["payment_required"] = "payment_required"
    message: str = "Pago requerido"
    error: ErrorDetail | None = None


# Rebuild models to resolve Literal forward references
BaseSuccessResponse.model_rebuild()
BaseControlledErrorResponse.model_rebuild()
BaseUnexpectedErrorResponse.model_rebuild()
BasePaymentRequiredResponse.model_rebuild()


# ═══════════════════════════════════════════════════════════════════════════════
# FACTORÍA — APIResponse
# ═══════════════════════════════════════════════════════════════════════════════


class APIResponse:
    """Factoría de respuestas con tipado estricto para endpoints FastAPI.

    Métodos de **éxito** → devuelven instancias Pydantic
    (:class:`BaseSuccessResponse`) que FastAPI serializa y documenta
    automáticamente via ``response_model``.

    Métodos de **error** → devuelven tuplas ``(Model, status_code)`` para
    permitir que el router establezca el código HTTP correcto mientras
    mantiene tipado Pydantic en el cuerpo de la respuesta.

    Constante de clase:
        ``ERROR_RESPONSES`` — dict listo para pasarse al ``APIRouter`` o a
        cualquier decorador de endpoint::

            router = APIRouter(responses=APIResponse.ERROR_RESPONSES)
    """

    ERROR_RESPONSES: dict = {
        400: {"model": BaseControlledErrorResponse, "description": "Error controlado"},
        402: {"model": BasePaymentRequiredResponse, "description": "Pago requerido"},
        404: {"model": BaseControlledErrorResponse, "description": "Recurso no encontrado"},
        500: {"model": BaseUnexpectedErrorResponse, "description": "Error inesperado del servidor"},
    }

    # ─────────────────────────────────────────────────────────────────────────
    # Éxito
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def ok(data: Any = None, *, message: str = "Éxito") -> BaseSuccessResponse:
        """Respuesta exitosa ``200``/``201`` con payload ``data``.

        Args:
            data:    Objeto a devolver. Se serializa con ``.model_dump()``
                     automáticamente si es un modelo Pydantic.
            message: Texto descriptivo. Por defecto ``"Éxito"``.

        Returns:
            :class:`BaseSuccessResponse` — Pydantic model (no JSONResponse).

        Example::

            return APIResponse.ok(client)
            return APIResponse.ok([item1, item2], message="Listado obtenido")
            return APIResponse.ok(data, message="Cliente actualizado")
        """
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        elif isinstance(data, list):
            data = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in data
            ]
        return BaseSuccessResponse(message=message, data=data)

    @staticmethod
    def saved(*, message: str = "Guardado con éxito") -> BaseSuccessResponse:
        """Respuesta ``200`` sin datos para PUT / PATCH.

        Args:
            message: Texto descriptivo. Por defecto ``"Guardado con éxito"``.

        Returns:
            :class:`BaseSuccessResponse` con ``data: None``.

        Example::

            return APIResponse.saved()
            return APIResponse.saved(message="Configuración actualizada")
        """
        return BaseSuccessResponse(message=message, data=None)

    @staticmethod
    def created(
        data: Any = None,
        *,
        message: str = "Creado con éxito",
    ) -> BaseSuccessResponse:
        """Respuesta ``201 Created``.

        Args:
            data:    Objeto creado (opcional).
            message: Texto descriptivo. Por defecto ``"Creado con éxito"``.

        Returns:
            :class:`BaseSuccessResponse` con los datos serializados.

        Example::

            return APIResponse.created()              # solo 201 + mensaje
            return APIResponse.created(new_client)   # 201 + objeto
            return APIResponse.created(new_client, message="Cliente registrado")
        """
        if data is None:
            return BaseSuccessResponse(message=message, data=None)
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        elif isinstance(data, list):
            data = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in data
            ]
        return BaseSuccessResponse(message=message, data=data)

    @staticmethod
    def deleted(*, message: str = "Eliminado con éxito") -> BaseSuccessResponse:
        """Respuesta ``200`` de confirmación de eliminación sin payload.

        Args:
            message: Texto descriptivo. Por defecto ``"Eliminado con éxito"``.

        Returns:
            :class:`BaseSuccessResponse` con ``data: None``.

        Example::

            return APIResponse.deleted()
        """
        return BaseSuccessResponse(message=message, data=None)

    # ─────────────────────────────────────────────────────────────────────────
    # Error
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def fail(
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> tuple[BaseControlledErrorResponse, int]:
        """Error controlado **manual** desde el router.

        Usar para validaciones que el router detecta antes de llamar al service
        (ID inválido, permisos, etc.).

        Args:
            message:     Mensaje legible para el usuario.
            status_code: Código HTTP. Por defecto ``400``.

        Returns:
            Tupla ``(BaseControlledErrorResponse, status_code)`` — el llamador
            debe usar estos para construir la respuesta HTTP.

        Example::

            error_response, http_status = APIResponse.fail("ID inválido", status_code=422)
            return JSONResponse(status_code=http_status, content=error_response.model_dump())
        """
        error_detail = ErrorDetail(type="ControlledError", detail=message)
        return BaseControlledErrorResponse(message=message, error=error_detail), status_code

    @staticmethod
    def auth_error(
        *,
        error_code: str,
        message: str,
        status_code: int = status.HTTP_401_UNAUTHORIZED,
        www_authenticate: str | None = None,
    ) -> JSONResponse:
        """Error de autenticación/autorización listo para retornar.

        Construye un :class:`~fastapi.responses.JSONResponse` con el envelope
        del proyecto y, cuando aplica, el header RFC 6750
        ``WWW-Authenticate``.

        Args:
            error_code: Discriminador estable que viaja en ``error.type``
                (por ejemplo ``"TokenExpired"``, ``"PermissionDenied"``).
                El frontend discrimina por este valor, nunca por el mensaje.
            message: Mensaje legible para el usuario (español).
            status_code: Código HTTP. Por defecto ``401``.
            www_authenticate: Valor del header ``WWW-Authenticate``. Si el
                status es ``401`` y se omite, se usa ``"Bearer"``. Para
                statuses distintos de ``401`` se omite salvo que se pase
                explícitamente.

        Returns:
            ``JSONResponse`` con el envelope del proyecto y los headers
            correspondientes.

        Example::

            return APIResponse.auth_error(
                error_code="TokenExpired",
                message="Token expirado",
                www_authenticate='Bearer error="expired_token"',
            )
        """
        error_detail = ErrorDetail(type=error_code, detail=message)
        body = BaseControlledErrorResponse(message=message, error=error_detail)

        headers: dict[str, str] = {}
        is_unauthorized = status_code == status.HTTP_401_UNAUTHORIZED
        if www_authenticate is not None or is_unauthorized:
            headers["WWW-Authenticate"] = www_authenticate or "Bearer"

        return JSONResponse(
            status_code=status_code,
            content=body.model_dump(),
            headers=headers,
        )

    @staticmethod
    def payment_required(
        message: str = "Pago requerido",
    ) -> tuple[BasePaymentRequiredResponse, int]:
        """Error 402 explícito cuando el usuario debe realizar un pago.

        Args:
            message: Mensaje legible para el usuario.

        Returns:
            Tupla ``(BasePaymentRequiredResponse, 402)``.

        Example::

            error_response, http_status = APIResponse.payment_required()
            return JSONResponse(status_code=http_status, content=error_response.model_dump())
        """
        error_detail = ErrorDetail(type="PaymentRequired", detail=message)
        return BasePaymentRequiredResponse(message=message, error=error_detail), status.HTTP_402_PAYMENT_REQUIRED

    @staticmethod
    def from_exception(
        exc: Exception,
        *,
        controlled: tuple[type[Exception], ...] = (ValueError,),
    ) -> tuple[BaseControlledErrorResponse | BaseUnexpectedErrorResponse, int]:
        """Convierte una excepción en un modelo de error estandarizado.

        - **Controlada** (``ValueError`` y subclases) → expone el mensaje al
          cliente y retorna 400.
        - **No controlada** → mensaje genérico; ``error.detail`` oculto;
          traceback completo al logger; retorna 500.

        Args:
            exc:       La excepción capturada.
            controlled: Tipos "esperados". Por defecto ``(ValueError,)``.

        Returns:
            Tupla ``(BaseControlledErrorResponse, 400)`` para errores
            controlados, o ``(BaseUnexpectedErrorResponse, 500)`` para
            errores inesperados.

        Example::

            try:
                result = await TransactionService.run(session, ...)
                return APIResponse.ok(result)
            except Exception as exc:
                return APIResponse.from_exception(exc)
        """
        error_detail = ErrorDetail(
            type=type(exc).__name__,
            detail=str(exc) if str(exc) else None,
        )

        if isinstance(exc, controlled):
            # Controlled exceptions get 400 with exposed message
            logger.debug("Controlled exception [%s]: %s", type(exc).__name__, exc)
            return BaseControlledErrorResponse(
                message=str(exc), error=error_detail
            ), status.HTTP_400_BAD_REQUEST

        # Unexpected exceptions get 500 with hidden detail
        logger.exception("Error inesperado [%s]: %s", type(exc).__name__, exc)
        error_detail.detail = None
        return BaseUnexpectedErrorResponse(error=error_detail), status.HTTP_500_INTERNAL_SERVER_ERROR


# ═══════════════════════════════════════════════════════════════════════════════
# LEGACY CLASSES — para backwards compatibility durante migración
# ═══════════════════════════════════════════════════════════════════════════════
# WARNING: Estas clases serán removidas cuando todos los routers estén migrados.
# Por favor usa las nuevas clases Base*Response y los mixins.


class BaseResponse(BaseModel):
    """CLASE LEGACY — Usar BaseSuccessResponse en su lugar.

    Estructura base compartida por todas las respuestas de la API.
    """

    success: bool
    message: str
    error: ErrorDetail | None = None
    data: Any = None


class MessageResponse(BaseResponse):
    """CLASE LEGACY — Usar BaseSuccessResponse en su lugar.

    Respuesta exitosa sin payload de datos.
    """

    success: bool = True
    data: None = None


class DataResponse(BaseResponse, Generic[T]):
    """CLASE LEGACY — Usar BaseSuccessResponse en su lugar.

    Respuesta exitosa con payload de datos tipado.
    """

    success: bool = True
    data: T  # type: ignore[assignment]


class ErrorResponse(BaseResponse):
    """CLASE LEGACY — Usar BaseControlledErrorResponse o BaseUnexpectedErrorResponse.

    Respuesta de error (controlado o inesperado).
    """

    success: bool = False
    data: None = None
