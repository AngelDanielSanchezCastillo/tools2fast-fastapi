from datetime import datetime, timezone
from tools2fast_fastapi.schemas.mixins import IdMixin, TimestampMixin

def test_schema_mixins():
    class TestSchema(IdMixin, TimestampMixin):
        name: str

    now = datetime.now(timezone.utc)
    schema = TestSchema(id=1, created_at=now, updated_at=now, name="Test")
    assert schema.id == 1
    assert schema.name == "Test"
    assert schema.created_at == now
