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
    model_cls: type[SQLModelType],
    id: UUID,
    deleted_by: UUID,
) -> None:
    """
    Mark a record as soft-deleted.
    
    Sets deleted_at to current timestamp and deleted_by to the provided user ID.
    
    Args:
        session: Async database session
        model_cls: SQLModel class to delete
        id: UUID of the record to delete
        deleted_by: UUID of the user performing the deletion
    
    Raises:
        ValueError: If the record does not exist or is already deleted
    """
    # Fetch the record
    record = await session.get(model_cls, id)
    if record is None:
        raise ValueError(f"{model_cls.__name__} with id {id} not found")
    
    # Check if already deleted
    if hasattr(record, "deleted_at") and record.deleted_at is not None:
        raise ValueError(f"{model_cls.__name__} with id {id} is already deleted")
    
    # Mark as deleted
    record.deleted_at = datetime.now(timezone.utc)
    record.deleted_by = deleted_by
    
    session.add(record)
    await session.commit()


async def restore(
    session: AsyncSession,
    model_cls: type[SQLModelType],
    id: UUID,
    restored_by: UUID,
) -> None:
    """
    Restore a soft-deleted record.
    
    Sets deleted_at and deleted_by to None, and updates updated_by to the restorer.
    
    Args:
        session: Async database session
        model_cls: SQLModel class to restore
        id: UUID of the record to restore
        restored_by: UUID of the user performing the restoration
    
    Raises:
        ValueError: If the record does not exist or is not deleted
    """
    # Fetch the record
    record = await session.get(model_cls, id)
    if record is None:
        raise ValueError(f"{model_cls.__name__} with id {id} not found")
    
    # Check if actually deleted
    if not hasattr(record, "deleted_at") or record.deleted_at is None:
        raise ValueError(f"{model_cls.__name__} with id {id} is not deleted")
    
    # Restore the record
    record.deleted_at = None
    record.deleted_by = None
    
    # Update updated_by to track who restored it
    if hasattr(record, "updated_by"):
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
