from datetime import datetime, timezone

from sqlalchemy import DateTime, func, event
from sqlmodel import BigInteger, Field


class IdMixin:
    """Mixin para proveer clave primaria autoincremental tipo BigInteger."""

    id: int | None = Field(default=None, primary_key=True, index=True, sa_type=BigInteger)


class TimestampMixin:
    """Mixin reutilizable para marcas de tiempo en UTC."""

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"onupdate": func.now()},
    )


class AuditMixin:
    """Mixin para rastrear el usuario que crea y actualiza un registro."""

    created_by: int | None = Field(
        default=None,
        index=True,
        description="ID of the user who created this record.",
        sa_type=BigInteger,
    )
    updated_by: int | None = Field(
        default=None,
        index=True,
        description="ID of the user who last updated this record.",
        sa_type=BigInteger,
    )

class NumberMixin:
    """
    Mixin para proveer un campo `number` que actúa como un identificador continuo 
    independiente de la clave primaria (ID).
    
    Sirve para mostrar un número de registro humano-legible (ej. "Cotización #123"),
    permitiendo que un mismo registro lógico pueda tener múltiples versiones 
    o revisiones manteniendo el mismo `number` consecutivo.
    """

    number: int = Field(index=True)

class NumberUniqueMixin:
    """
    Mixin para proveer un campo `number` que actúa como un identificador único 
    independiente de la clave primaria (ID).
    
    Sirve para mostrar un número de registro humano-legible (ej. "Cotización #123"),
    """

    number: int = Field(index=True, unique=True)

class RevisionMixin(NumberMixin):
    """
    Mixin reutilizable para cualquier tabla SQLModel que necesite versionado.

    Agrega:
      - revision (int): Número de revisión del registro (comienza en 1, incrementa con cada cambio).

    La "revisión actual" es siempre la que tenga el mayor valor de `revision`
    para un mismo `number`. No existe campo de status — la más reciente es la vigente.

    Uso:
        class MyModel(RevisionMixin, TenantModel, table=True):
            __tablename__ = "my_models"
            __table_args__ = (
                UniqueConstraint("number", "revision", name="uq_my_model_number_revision"),
            )
            ...
    """

    revision: int = Field(default=1, ge=1, index=True)


class AuditTimestampMixin(AuditMixin, TimestampMixin):
    """
    Combines AuditMixin (created_by, updated_by) + TimestampMixin (created_at, updated_at)
    with SQLAlchemy events that auto-populate audit fields.
    
    Events read from tenant2fast_fastapi's user context to set
    created_by/updated_by automatically on inserts and updates.
    
    Usage:
        class MyModel(AuditTimestampMixin, IdTenantModel, table=True):
            __abstract__ = True
    """

    __abstract__ = True


@event.listens_for(AuditTimestampMixin, "before_insert", propagate=True)
def _audit_before_insert(mapper, connection, target):
    """Auto-populate created_by from user context on insert."""
    # Lazy import to avoid circular dependency with tenant2fast_fastapi
    try:
        from tenant2fast_fastapi.dependencies import get_user_context
        user = get_user_context()
        if user is not None:
            user_id = getattr(user, 'id', None)
            if user_id is not None and getattr(target, 'created_by', None) is None:
                target.created_by = user_id
    except (ImportError, AttributeError):
        # tenant2fast_fastapi not available or user has no 'id' attribute, skip auto-population
        pass


@event.listens_for(AuditTimestampMixin, "before_update", propagate=True)
def _audit_before_update(mapper, connection, target):
    """Auto-populate updated_by and updated_at from user context on update."""
    # Lazy import to avoid circular dependency with tenant2fast_fastapi
    try:
        from tenant2fast_fastapi.dependencies import get_user_context
        user = get_user_context()
        if user is not None:
            user_id = getattr(user, 'id', None)
            if user_id is not None:
                target.updated_by = user_id
    except (ImportError, AttributeError):
        # tenant2fast_fastapi not available or user has no 'id' attribute, skip auto-population
        pass
    
    # Always update updated_at when entity has changes
    target.updated_at = datetime.now(timezone.utc)