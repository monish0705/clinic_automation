from datetime import datetime
from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.orm import declarative_base, declared_attr

class CustomBase:
    """Base class for all SQLAlchemy models with automatic tablename and audit timestamps."""

    @declared_attr
    def __tablename__(cls) -> str:
        # Converts CamelCase to snake_case table name
        name = cls.__name__
        return "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip("_") + "s"

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


Base = declarative_base(cls=CustomBase)
