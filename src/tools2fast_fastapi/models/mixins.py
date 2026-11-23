from datetime import datetime, timezone
from uuid import UUID
import time
import secrets

from sqlalchemy import DateTime, func, event
from sqlmodel import BigInteger, Field


def uuid7() -> UUID:
    """
    Generate a UUID version 7 (time-ordered).
    
    UUID v7 structure (RFC 9562):
    - 48 bits: Unix timestamp in milliseconds
    - 4 bits: version (0111 = 7)
    - 12 bits: random
    - 2 bits: variant (10)
    - 62 bits: random
    
    Returns:
        UUID version 7
    """
    import os
    
    # Get current timestamp in milliseconds (48 bits)
    timestamp_ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    
    # Generate 10 bytes of random data (80 bits)
    random_bytes = os.urandom(10)
    random_int = int.from_bytes(random_bytes, 'big')
    
    # Construct the UUID (128 bits total)
    # Bits 0-47: timestamp (48 bits)
    # Bits 48-51: version (4 bits) = 0111
    # Bits 52-63: random (12 bits)
    # Bits 64-65: variant (2 bits) = 10
    # Bits 66-127: random (62 bits)
    
    # Start with timestamp in the high 48 bits
    uuid_int = timestamp_ms << 80
    
    # Add version (0111) at bits 48-51
    uuid_int |= (0b0111 << 76)
    
    # Add random bits at bits 52-63 (12 bits)
    uuid_int |= (random_int & 0xFFF) << 64
    
    # Add variant (10) at bits 64-65
    uuid_int |= (0b10 << 62)
    
    # Add random bits at bits 66-127 (62 bits)
    uuid_int |= (random_int >> 12) & 0x3FFFFFFFFFFFFFFF
    
    return UUID(int=uuid_int)


class IdMixin:
    """
    DEPRECATED: Use UUIDIdMixin instead.
    
    Mixin para proveer clave primaria autoincremental tipo BigInteger.
    
    .. deprecated:: 0.4.0
        Use :class:`UUIDIdMixin` for new models. IdMixin will be removed in a future version.
    """

    def __init_subclass__(cls, **kwargs):
        """Emit deprecation warning when subclassed."""
        import warnings
        warnings.warn(
            "IdMixin is deprecated and will be removed in a future version. "
            "Use UUIDIdMixin instead for UUID v7 primary keys.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init_subclass__(**kwargs)

    id: int | None = Field(default=None, primary_key=True, index=True, sa_type=BigInteger)


class UUIDIdMixin:
    """Mixin para proveer clave primaria tipo UUID v7 (time-ordered)."""

    id: UUID = Field(default_factory=uuid7, primary_key=True, index=True)


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

    created_by: UUID | None = Field(
        default=None,
        index=True,
        description="ID of the user who created this record.",
    )
    updated_by: UUID | None = Field(
        default=None,
        index=True,
        description="ID of the user who last updated this record.",
    )


class SoftDeleteMixin:
    """
    Mixin para borrado lógico (soft delete).
    
    Agrega:
      - deleted_at (datetime | None): Timestamp de cuándo se borró el registro.
      - deleted_by (UUID | None): ID del usuario que borró el registro.
    
    Uso:
        class MyModel(UUIDIdMixin, TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
            __tablename__ = "my_models"
            name: str = Field()
    
    El registro se considera "borrado" cuando deleted_at no es None.
    Para filtrar registros activos, usar active_only(query).
    Para filtrar registros borrados, usar deleted_only(query).
    """

    deleted_at: datetime | None = Field(
        default=None,
        index=True,
        description="Timestamp when the record was soft-deleted. None means active.",
        sa_type=DateTime(timezone=True),
    )
    deleted_by: UUID | None = Field(
        default=None,
        description="ID of the user who soft-deleted this record.",
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