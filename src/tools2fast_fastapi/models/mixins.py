from datetime import datetime, timezone

from sqlalchemy import DateTime, func
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