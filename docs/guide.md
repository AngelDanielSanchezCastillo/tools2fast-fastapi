# Usage Guide

This package provides standard mixins for SQLModel.

## Mixins

To use the mixins, simply inherit from them when defining your models.

```python
from sqlmodel import Field, MetaData, SQLModel
from tools2fast_fastapi.models.mixins import AuditMixin, IdMixin, TimestampMixin

metadata = MetaData()

class BasicModel(TimestampMixin, SQLModel):
    """Base model without predefined primary key, but with timestamps."""

    __abstract__ = True
    metadata = metadata


class CoreModel(IdMixin, BasicModel):
    """Default base model with BigInteger primary key and timestamps."""

    __abstract__ = True


class User(CoreModel, AuditMixin, table=True):
    name: str = Field(index=True)
    email: str = Field(unique=True, index=True)
```

The `CoreModel` automatically includes the `IdMixin` and `TimestampMixin`, giving your model an `id`, `created_at`, and `updated_at`. By including `AuditMixin`, you also track `created_by` and `updated_by`.
