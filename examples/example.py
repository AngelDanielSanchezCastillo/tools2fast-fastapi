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

if __name__ == "__main__":
    user = User(name="Test", email="test@example.com")
    print("User ID:", user.id)
    print("User Created At:", user.created_at)
