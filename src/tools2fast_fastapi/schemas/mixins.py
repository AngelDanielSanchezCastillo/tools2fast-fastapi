from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlmodel import SQLModel


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR DETAIL — estructurado
# ═══════════════════════════════════════════════════════════════════════════════


class ErrorDetail(BaseModel):
    """Información estructurada de un error.

    Attributes:
        type: Nombre de la clase de la excepción (e.g., ``'ValueError'``).
        detail: Mensaje de detalle. ``None`` en errores no controlados (seguridad).
    """

    type: str
    detail: str | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE MIXINS — Pydantic BaseModels para herencia
# ═══════════════════════════════════════════════════════════════════════════════


class SuccessResponseMixin(BaseModel):
    """Mixin para respuestas exitosas.

    Los proyectos pueden heredar de esta clase para agregar los fields
    ``success`` y ``message`` a sus modelos de respuesta.

    Example::

        class ClientResponse(ClientRead, SuccessResponseMixin):
            '''Respuesta exitosa para GET /clients/{id}'''
            pass
    """

    success: Literal[True] = True
    message: str = "Éxito"


class ControlledErrorMixin(BaseModel):
    """Mixin para errores controlados (fail).

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


class UnexpectedErrorMixin(BaseModel):
    """Mixin para errores inesperados (from_exception).

    Attributes:
        success: Siempre ``False``.
        error_type: Siempre ``"unexpected"``.
        message: Siempre ``"Ha ocurrido un error"``.
        error: Detalle estructurado (detail oculto en producción).
    """

    success: Literal[False] = False
    error_type: Literal["unexpected"] = "unexpected"
    message: str = "Ha ocurrido un error"
    error: ErrorDetail | None = None


class PaymentRequiredMixin(BaseModel):
    """Mixin para errores de subscripción vencida (payment_required).

    Attributes:
        success: Siempre ``False``.
        error_type: Siempre ``"payment_required"``.
        message: Siempre ``"Pago requerido"``.
        error: Detalle estructurado del error.
    """

    success: Literal[False] = False
    error_type: Literal["payment_required"] = "payment_required"
    message: str = "Pago requerido"
    error: ErrorDetail | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL MIXINS — para SQLModel (recursos de base de datos)
# ═══════════════════════════════════════════════════════════════════════════════


class IdMixin(SQLModel):
    """Schema mixin para recursos que tienen un ID entero."""

    id: int


class TimestampMixin(SQLModel):
    """Schema mixin para recursos que incluyen timestamps de creación y actualización."""

    created_at: datetime
    updated_at: datetime


class AuditMixin(SQLModel):
    """Schema mixin para recursos que incluyen IDs de usuario auditables."""

    created_by: int | None = None
    updated_by: int | None = None


class NumberMixin(SQLModel):
    """Schema mixin para recursos que usan un número de secuencia continuo."""

    number: int


class RevisionMixin(NumberMixin):
    """Schema mixin para recursos que incluyen número de revisión."""

    revision: int


class NumberUniqueMixin(SQLModel):
    """Schema mixin para recursos con número único por tenant."""

    number: int
    tenant_id: int
