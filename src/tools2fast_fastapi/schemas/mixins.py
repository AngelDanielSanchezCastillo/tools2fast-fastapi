from datetime import datetime

from sqlmodel import SQLModel


class IdMixin(SQLModel):
    """Schema mixin for resources that have an integer ID."""

    id: int


class TimestampMixin(SQLModel):
    """Schema mixin for resources that include created and updated timestamps."""

    created_at: datetime
    updated_at: datetime


class AuditMixin(SQLModel):
    """Schema mixin for resources that include audit user IDs."""

    created_by: int | None = None
    updated_by: int | None = None


class NumberMixin(SQLModel):
    """Schema mixin for resources that use a continuous sequence number."""

    number: int


class RevisionMixin(NumberMixin):
    """Schema mixin for resources that include a revision number."""

    revision: int
