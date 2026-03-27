"""
Schemas de respuesta estándar para todos los endpoints.

Jerarquía de modelos:

    BaseResponse
    ├── MessageResponse   → success/delete/create sin datos  (data: None)
    ├── DataResponse[T]   → respuestas con payload tipado     (data: T)
    └── ErrorResponse     → errores controlados e inesperados (data: None, success: False)

Factoría:
    APIResponse → métodos estáticos que devuelven los modelos anteriores.
"""

from __future__ import annotations

import logging
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from fastapi import status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ═══════════════════════════════════════════════════════
# Modelo auxiliar
# ═══════════════════════════════════════════════════════

class ErrorDetail(BaseModel):
    """Información estructurada de un error."""

    type: str
    """Nombre de la clase de la excepción, p. ej. ``'ValueError'``."""

    detail: str | None = None
    """Mensaje de detalle. ``null`` en errores no controlados (seguridad)."""


# ═══════════════════════════════════════════════════════
# Jerarquía de respuesta
# ═══════════════════════════════════════════════════════

class BaseResponse(BaseModel):
    """Estructura base compartida por todas las respuestas de la API.

    Todos los endpoints devuelven exactamente estos cuatro campos::

        {
            "success": bool,
            "message": str,
            "error":   {"type": str, "detail": str | null} | null,
            "data":    <T> | null
        }
    """

    success: bool
    message: str
    error: ErrorDetail | None = None
    data: Any = None


class MessageResponse(BaseResponse):
    """Respuesta exitosa **sin** payload de datos.

    Usada en: ``saved()``, ``deleted()``, ``created()`` sin argumento.
    ``data`` está fijado en ``None`` — no admite payload.
    """

    success: bool = True
    data: None = None


class DataResponse(BaseResponse, Generic[T]):
    """Respuesta exitosa **con** payload de datos tipado.

    Usada en: ``ok()``, ``created(data=…)``

    Declara el tipo concreto en el decorador del endpoint::

        response_model=DataResponse[QuotationHeaderRead]
        response_model=DataResponse[list[ClientRead]]
    """

    success: bool = True
    data: T  # type: ignore[assignment]


class ErrorResponse(BaseResponse):
    """Respuesta de error (controlado o inesperado).

    ``success`` siempre es ``False``.
    ``data`` siempre es ``null``.
    """

    success: bool = False
    data: None = None


# ═══════════════════════════════════════════════════════
# Factoría
# ═══════════════════════════════════════════════════════

class APIResponse:
    """Factoría de respuestas con tipado estricto para endpoints FastAPI.

    Métodos de **éxito** → devuelven instancias Pydantic
    (:class:`MessageResponse` / :class:`DataResponse`) que FastAPI serializa
    y documenta automáticamente via ``response_model``.

    Métodos de **error** → devuelven :class:`~fastapi.responses.JSONResponse`
    porque necesitan ``status_code`` variable (400, 404, 500…).

    Constante de clase:
        ``ERROR_RESPONSES`` — dict listo para pasarse al ``APIRouter`` o a
        cualquier decorador de endpoint::

            router = APIRouter(responses=APIResponse.ERROR_RESPONSES)
    """

    ERROR_RESPONSES: dict = {
        400: {"model": ErrorResponse, "description": "Error controlado"},
        500: {"model": ErrorResponse, "description": "Error inesperado del servidor"},
    }

    # ─────────────────────────────────────────────────────────────────────────
    # Éxito
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def ok(data: Any, *, message: str = "OK") -> DataResponse:
        """Respuesta exitosa ``200`` con payload ``data``.

        Args:
            data:    Objeto a devolver. Se serializa con ``.model_dump()``
                     automáticamente si es un modelo Pydantic.
            message: Texto descriptivo. Por defecto ``"OK"``.

        Example::

            return APIResponse.ok(client)
            return APIResponse.ok([item1, item2], message="Listado obtenido")
        """
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        elif isinstance(data, list):
            data = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in data
            ]
        return DataResponse(message=message, data=data)

    @staticmethod
    def saved(*, message: str = "Guardado con éxito") -> MessageResponse:
        """Respuesta ``200`` sin datos para PUT / PATCH.

        Example::

            return APIResponse.saved()
        """
        return MessageResponse(message=message)

    @staticmethod
    def created(
        data: Any = None,
        *,
        message: str = "Creado con éxito",
    ) -> MessageResponse | DataResponse:
        """Respuesta ``201 Created``.

        Sin ``data`` → :class:`MessageResponse` (solo mensaje).
        Con ``data=`` → :class:`DataResponse` con el objeto serializado.

        Example::

            return APIResponse.created()            # solo 201 + mensaje
            return APIResponse.created(new_client)  # 201 + objeto
        """
        if data is None:
            return MessageResponse(message=message)
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        elif isinstance(data, list):
            data = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in data
            ]
        return DataResponse(message=message, data=data)

    @staticmethod
    def deleted(*, message: str = "Eliminado con éxito") -> MessageResponse:
        """Respuesta ``200`` de confirmación de eliminación sin payload.

        ``data`` siempre es ``null`` — no tiene sentido devolver el objeto
        que ya no existe.

        Example::

            return APIResponse.deleted()
        """
        return MessageResponse(message=message)

    # ─────────────────────────────────────────────────────────────────────────
    # Error
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def fail(
        message: str,
        *,
        error: str | dict | None = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> JSONResponse:
        """Error controlado **manual** desde el router.

        Usar para validaciones que el router detecta antes de llamar al service
        (ID inválido, permisos, etc.).

        Args:
            message:     Mensaje legible para el usuario.
            error:       Detalle opcional: ``str`` o ``{"type": …, "detail": …}``.
            status_code: Código HTTP. Por defecto ``400``.

        Example::

            return APIResponse.fail("ID inválido", status_code=422)
        """
        error_detail: ErrorDetail | None = None
        if error is not None:
            if isinstance(error, dict):
                error_detail = ErrorDetail(**error)
            else:
                error_detail = ErrorDetail(type="Error", detail=str(error))

        body = ErrorResponse(message=message, error=error_detail)
        return JSONResponse(status_code=status_code, content=body.model_dump())

    @staticmethod
    def from_exception(
        exc: Exception,
        *,
        controlled: tuple[type[Exception], ...] = (ValueError,),
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> JSONResponse:
        """Convierte una excepción en un :class:`JSONResponse` estandarizado.

        - **Controlada** → expone el mensaje al cliente y lo incluye en ``error.detail``.
        - **No controlada** → mensaje genérico; ``error.detail`` oculto (seguridad);
          traceback completo al logger.

        Args:
            exc:         La excepción capturada.
            controlled:  Tipos "esperados". Por defecto ``(ValueError,)``.
            status_code: Código HTTP para errores controlados.

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
            body = ErrorResponse(message=str(exc), error=error_detail)
            return JSONResponse(status_code=status_code, content=body.model_dump())

        logger.exception("Error inesperado [%s]: %s", type(exc).__name__, exc)
        error_detail.detail = None
        body = ErrorResponse(message="Ha ocurrido un error", error=error_detail)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=body.model_dump(),
        )
