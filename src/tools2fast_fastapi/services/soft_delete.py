"""Soft-delete functions for logical deletion and restoration of records."""
from datetime import datetime, timezone
from typing import TypeVar
from uuid import UUID

from sqlalchemy import Select
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# Type variable for SQLModel classes
SQLModelType = TypeVar("SQLModelType", bound=SQLModel)


async def soft_delete(
    session: AsyncSession,
    model_cls: "type[SQLModelType] | SQLModelType",
    id: UUID | None = None,
    deleted_by: UUID | None = None,
) -> None:
    """
    Mark a record as soft-deleted.

    Two supported call shapes (backward compatible):
      - ``soft_delete(session, Model, id, deleted_by)``  (by class + id)
      - ``soft_delete(session, instance)``               (by live instance)

    Sets ``deleted_at`` to now and ``deleted_by`` when provided.

    Raises:
        ValueError: If the record does not exist or is already deleted
    """
    if isinstance(model_cls, type):
        record = await session.get(model_cls, id)
        name = model_cls.__name__
        if record is None:
            raise ValueError(f"{name} with id {id} not found")
    else:
        record = model_cls
        name = type(record).__name__

    # Check if already deleted
    if hasattr(record, "deleted_at") and record.deleted_at is not None:
        raise ValueError(f"{name} is already deleted")

    # Mark as deleted
    record.deleted_at = datetime.now(timezone.utc)
    if deleted_by is not None:
        record.deleted_by = deleted_by

    session.add(record)
    await session.commit()


async def restore(
    session: AsyncSession,
    model_cls: "type[SQLModelType] | SQLModelType",
    id: UUID | None = None,
    restored_by: UUID | None = None,
) -> None:
    """
    Restore a soft-deleted record.

    Two supported call shapes (backward compatible):
      - ``restore(session, Model, id, restored_by)``
      - ``restore(session, instance)``
    """
    if isinstance(model_cls, type):
        record = await session.get(model_cls, id)
        name = model_cls.__name__
        if record is None:
            raise ValueError(f"{name} with id {id} not found")
    else:
        record = model_cls
        name = type(record).__name__

    if not hasattr(record, "deleted_at") or record.deleted_at is None:
        raise ValueError(f"{name} is not deleted")

    record.deleted_at = None
    record.deleted_by = None
    if getattr(record, "updated_by", None) is not None:
        record.updated_by = restored_by

    session.add(record)
    await session.commit()


def active_only(query: Select) -> Select:
    """
    Filter a query to only return active (non-deleted) records.
    
    Adds WHERE deleted_at IS NULL to the query.
    
    Args:
        query: SQLAlchemy Select query
    
    Returns:
        Modified query with active filter applied
    
    Example:
        stmt = active_only(select(User))
        result = await session.exec(stmt)
    """
    # Get the model class from the query
    # The query should be like select(Model) or select(Model.id, ...)
    if not query.column_descriptions:
        raise ValueError("Query must have column descriptions")
    
    # Get the first entity (model class)
    first_entity = query.column_descriptions[0].get('entity')
    if first_entity is None:
        raise ValueError("Query must select from a model class")
    
    # Add the filter for deleted_at IS NULL
    return query.where(first_entity.deleted_at.is_(None))


def deleted_only(query: Select) -> Select:
    """
    Filter a query to only return deleted records.
    
    Adds WHERE deleted_at IS NOT NULL to the query.
    
    Args:
        query: SQLAlchemy Select query
    
    Returns:
        Modified query with deleted filter applied
    
    Example:
        stmt = deleted_only(select(User))
        result = await session.exec(stmt)
    """
    # Get the model class from the query
    if not query.column_descriptions:
        raise ValueError("Query must have column descriptions")
    
    # Get the first entity (model class)
    first_entity = query.column_descriptions[0].get('entity')
    if first_entity is None:
        raise ValueError("Query must select from a model class")
    
    # Add the filter for deleted_at IS NOT NULL
    return query.where(first_entity.deleted_at.isnot(None))
