"""Tests for UUID and soft-delete mixins (ODD-1)."""
import warnings
from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlmodel import Field, SQLModel, select

from tools2fast_fastapi import (
    UUIDIdMixin,
    SoftDeleteMixin,
    AuditMixin,
    TimestampMixin,
    soft_delete,
    restore,
    active_only,
    deleted_only,
)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class TestModel(UUIDIdMixin, TimestampMixin, SQLModel, table=True):
    """Test model with UUID primary key."""
    __tablename__ = "test_models"
    name: str = Field()


class TestSoftDeleteModel(UUIDIdMixin, TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
    """Test model with UUID primary key and soft-delete."""
    __tablename__ = "test_soft_delete_models"
    name: str = Field()


class TestSoftDeleteWithAuditModel(UUIDIdMixin, TimestampMixin, AuditMixin, SoftDeleteMixin, SQLModel, table=True):
    """Test model with UUID primary key, audit, and soft-delete."""
    __tablename__ = "test_soft_delete_with_audit_models"
    name: str = Field()


class TestAuditModel(UUIDIdMixin, TimestampMixin, AuditMixin, SQLModel, table=True):
    """Test model with UUID primary key and audit fields."""
    __tablename__ = "test_audit_models"
    name: str = Field()


# ═══════════════════════════════════════════════════════════════════════════════
# UUIDIdMixin TESTS
# ═══════════════════════════════════════════════════════════════════════════════


def test_uuid_id_mixin_generates_uuid7():
    """UUIDIdMixin should generate a UUID v7 by default."""
    model = TestModel(name="Test")
    assert model.id is not None
    assert isinstance(model.id, UUID)
    # UUID v7 should be version 7
    assert model.id.version == 7


def test_uuid_id_mixin_accepts_custom_uuid():
    """UUIDIdMixin should accept a custom UUID."""
    custom_uuid = UUID("0190a7e3-8c4a-7d0b-9c8e-3f4a5b6c7d8e")
    model = TestModel(id=custom_uuid, name="Test")
    assert model.id == custom_uuid


def test_uuid_id_mixin_primary_key():
    """UUIDIdMixin should define id as primary key."""
    # Check that the field is marked as primary key
    field_info = TestModel.model_fields["id"]
    assert field_info.primary_key is True


# ═══════════════════════════════════════════════════════════════════════════════
# SoftDeleteMixin TESTS
# ═══════════════════════════════════════════════════════════════════════════════


def test_soft_delete_mixin_defaults_to_none():
    """SoftDeleteMixin should default deleted_at and deleted_by to None."""
    model = TestSoftDeleteModel(name="Test")
    assert model.deleted_at is None
    assert model.deleted_by is None


def test_soft_delete_mixin_accepts_datetime():
    """SoftDeleteMixin should accept datetime for deleted_at."""
    now = datetime.now(timezone.utc)
    deleted_by = UUID("0190a7e3-8c4a-7d0b-9c8e-3f4a5b6c7d8e")
    model = TestSoftDeleteModel(name="Test", deleted_at=now, deleted_by=deleted_by)
    assert model.deleted_at == now
    assert model.deleted_by == deleted_by


# ═══════════════════════════════════════════════════════════════════════════════
# AuditMixin TESTS (UUID version)
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_mixin_uses_uuid():
    """AuditMixin should use UUID for created_by and updated_by."""
    user_uuid = UUID("0190a7e3-8c4a-7d0b-9c8e-3f4a5b6c7d8e")
    model = TestAuditModel(name="Test", created_by=user_uuid, updated_by=user_uuid)
    assert isinstance(model.created_by, UUID)
    assert isinstance(model.updated_by, UUID)
    assert model.created_by == user_uuid
    assert model.updated_by == user_uuid


def test_audit_mixin_defaults_to_none():
    """AuditMixin should default created_by and updated_by to None."""
    model = TestAuditModel(name="Test")
    assert model.created_by is None
    assert model.updated_by is None


# ═══════════════════════════════════════════════════════════════════════════════
# SOFT DELETE FUNCTIONS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_soft_delete_function(session):
    """soft_delete() should mark a record as deleted."""
    # Create a test record
    model = TestSoftDeleteModel(name="Test")
    session.add(model)
    await session.commit()
    await session.refresh(model)
    
    # Verify not deleted initially
    assert model.deleted_at is None
    assert model.deleted_by is None
    
    # Soft delete the record
    deleter_uuid = UUID("0190a7e3-8c4a-7d0b-9c8e-3f4a5b6c7d8e")
    await soft_delete(session, TestSoftDeleteModel, model.id, deleter_uuid)
    
    # Verify deleted
    await session.refresh(model)
    assert model.deleted_at is not None
    assert model.deleted_by == deleter_uuid


@pytest.mark.asyncio
async def test_restore_function(session):
    """restore() should reactivate a deleted record."""
    # Create and soft delete a test record
    model = TestSoftDeleteWithAuditModel(name="Test")
    session.add(model)
    await session.commit()
    await session.refresh(model)
    
    deleter_uuid = UUID("0190a7e3-8c4a-7d0b-9c8e-3f4a5b6c7d8e")
    await soft_delete(session, TestSoftDeleteWithAuditModel, model.id, deleter_uuid)
    await session.refresh(model)
    
    # Verify deleted
    assert model.deleted_at is not None
    
    # Restore the record
    restorer_uuid = UUID("0190a7e3-8c4a-7d0b-9c8e-3f4a5b6c7d8f")
    await restore(session, TestSoftDeleteWithAuditModel, model.id, restorer_uuid)
    
    # Verify restored
    await session.refresh(model)
    assert model.deleted_at is None
    assert model.deleted_by is None
    # updated_by should be the restorer
    assert model.updated_by == restorer_uuid


@pytest.mark.asyncio
async def test_active_only_filter(session):
    """active_only() should filter to only non-deleted records."""
    # Create two records
    active_model = TestSoftDeleteModel(name="Active")
    deleted_model = TestSoftDeleteModel(name="Deleted")
    session.add(active_model)
    session.add(deleted_model)
    await session.commit()
    await session.refresh(active_model)
    await session.refresh(deleted_model)
    
    # Soft delete one
    deleter_uuid = UUID("0190a7e3-8c4a-7d0b-9c8e-3f4a5b6c7d8e")
    await soft_delete(session, TestSoftDeleteModel, deleted_model.id, deleter_uuid)
    
    # Query with active_only filter
    stmt = active_only(select(TestSoftDeleteModel))
    result = await session.exec(stmt)
    records = result.all()
    
    # Should only return the active record
    assert len(records) == 1
    assert records[0].name == "Active"


@pytest.mark.asyncio
async def test_deleted_only_filter(session):
    """deleted_only() should filter to only deleted records."""
    # Create two records
    active_model = TestSoftDeleteModel(name="Active")
    deleted_model = TestSoftDeleteModel(name="Deleted")
    session.add(active_model)
    session.add(deleted_model)
    await session.commit()
    await session.refresh(active_model)
    await session.refresh(deleted_model)
    
    # Soft delete one
    deleter_uuid = UUID("0190a7e3-8c4a-7d0b-9c8e-3f4a5b6c7d8e")
    await soft_delete(session, TestSoftDeleteModel, deleted_model.id, deleter_uuid)
    
    # Query with deleted_only filter
    stmt = deleted_only(select(TestSoftDeleteModel))
    result = await session.exec(stmt)
    records = result.all()
    
    # Should only return the deleted record
    assert len(records) == 1
    assert records[0].name == "Deleted"
