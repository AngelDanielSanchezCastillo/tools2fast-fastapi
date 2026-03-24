from sqlmodel import Field, MetaData, SQLModel
from tools2fast_fastapi.models.mixins import IdMixin, TimestampMixin

metadata = MetaData()


class BasicModel(TimestampMixin, SQLModel):
    """Base model without predefined primary key, but with timestamps."""

    __abstract__ = True
    metadata = metadata


class CoreModel(IdMixin, BasicModel):
    """Default base model with BigInteger primary key and timestamps."""

    __abstract__ = True


class SampleModel(CoreModel, table=True):
    name: str = Field(default="Test")


def test_model_creation():
    model = SampleModel()
    assert model.name == "Test"
    assert model.created_at is not None
    assert model.updated_at is not None
    assert model.id is None  # Initialized without it being set yet in DB
