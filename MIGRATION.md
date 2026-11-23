# Migration Guide — tools2fast-fastapi 0.4.0

## Breaking Changes

### Python 3.12+ Required

**Before**: Python 3.10+
**After**: Python 3.12+

Update your `pyproject.toml`:
```toml
requires-python = ">=3.12"
```

### UUID Primary Keys (UUIDIdMixin)

**Before**: All models used `IdMixin` with auto-incrementing `BigInteger` IDs.
**After**: New models should use `UUIDIdMixin` with UUID v7 primary keys.

#### Migration Steps

1. **New models**: Use `UUIDIdMixin` instead of `IdMixin`:
```python
from tools2fast_fastapi import UUIDIdMixin, TimestampMixin, SQLModel, Field

class MyModel(UUIDIdMixin, TimestampMixin, SQLModel, table=True):
    __tablename__ = "my_models"
    name: str = Field()
```

2. **Existing models**: Gradually migrate from `IdMixin` to `UUIDIdMixin`. See the full migration guide for database migration strategies.

3. **Schemas**: Update response schemas to use `UUIDIdMixin`:
```python
from tools2fast_fastapi.schemas.mixins import UUIDIdMixin, TimestampMixin

class MyModelRead(UUIDIdMixin, TimestampMixin):
    name: str
```

### AuditMixin Uses UUID

**Before**: `created_by` and `updated_by` were `int` (BigInteger).
**After**: `created_by` and `updated_by` are `UUID`.

#### Migration Steps

Update your code to use UUIDs for audit fields:
```python
from uuid import UUID

# Before
created_by: int = current_user.id

# After
created_by: UUID = current_user.id  # current_user.id must be UUID
```

### Soft Delete (SoftDeleteMixin)

**New**: `SoftDeleteMixin` provides logical deletion with `deleted_at` and `deleted_by` fields.

#### Usage

```python
from tools2fast_fastapi import UUIDIdMixin, TimestampMixin, SoftDeleteMixin, SQLModel, Field

class MyModel(UUIDIdMixin, TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
    __tablename__ = "my_models"
    name: str = Field()
```

#### Soft Delete Functions

Use the provided functions for soft-delete operations:

```python
from tools2fast_fastapi import soft_delete, restore, active_only, deleted_only
from sqlmodel import select

# Soft delete a record
await soft_delete(session, MyModel, record_id, deleted_by=current_user.id)

# Restore a deleted record
await restore(session, MyModel, record_id, restored_by=current_user.id)

# Query only active records
stmt = active_only(select(MyModel))
result = await session.exec(stmt)

# Query only deleted records
stmt = deleted_only(select(MyModel))
result = await session.exec(stmt)
```

### IdMixin Deprecated

**Status**: `IdMixin` is deprecated and will be removed in a future version.

**Action**: Migrate to `UUIDIdMixin` for new models. Existing models using `IdMixin` will continue to work but will emit deprecation warnings.

---

## New Features

### UUID v7 Generation

UUID v7 is time-ordered, providing better database index locality compared to UUID v4.

```python
from tools2fast_fastapi.models.mixins import uuid7

new_uuid = uuid7()  # Returns a UUID v7 instance
```

### Soft Delete Functions

Four new functions for managing soft-deleted records:

- `soft_delete(session, model_cls, id, deleted_by)`: Mark a record as deleted
- `restore(session, model_cls, id, restored_by)`: Reactivate a deleted record
- `active_only(query)`: Filter to only non-deleted records
- `deleted_only(query)`: Filter to only deleted records

---

## Migration Checklist

- [ ] Update Python to 3.12+
- [ ] Update `pyproject.toml` to `requires-python = ">=3.12"`
- [ ] Replace `IdMixin` with `UUIDIdMixin` in new models
- [ ] Update schemas to use `UUIDIdMixin`
- [ ] Update `AuditMixin` usage (int → UUID for created_by/updated_by)
- [ ] Add `SoftDeleteMixin` to models that need soft-delete
- [ ] Use `soft_delete()`, `restore()`, `active_only()`, `deleted_only()` functions
- [ ] Run database migrations to convert BigInteger IDs to UUIDs (see database migration guide)
- [ ] Update API responses to use UUID instead of int for IDs

---

## Database Migration

Database migration from BigInteger to UUID is a complex operation. Use the migration helpers provided in `pgsqlasync2fast-fastapi 0.4.0`:

```python
from pgsqlasync2fast_fastapi import migrate_pk_to_uuid, migrate_fk_to_uuid

# Migrate a table's primary key from BigInteger to UUID
await migrate_pk_to_uuid(session, "my_models")

# Migrate a foreign key from int to UUID
await migrate_fk_to_uuid(session, "my_models", "parent_id", "parent_models")
```

**Note**: These migration helpers are deprecated and will be removed in 5 minor versions. Use them only for v0.x → v1.0 migrations.

---

## Timeline

- **0.4.0**: Initial release with UUIDIdMixin, SoftDeleteMixin, and migration helpers
- **0.4.x - 0.9.x**: Migration helpers available with deprecation warnings
- **1.0.0**: Migration helpers removed

---

## Support

For questions or issues, contact the Solautyc Team.
