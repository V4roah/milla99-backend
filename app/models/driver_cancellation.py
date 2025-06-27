from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, Index
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
import pytz

COLOMBIA_TZ = pytz.timezone("America/Bogota")


class DriverCancellation(SQLModel, table=True):
    __tablename__ = "driver_cancellation"

    id: Optional[UUID] = Field(
        default_factory=uuid4,
        primary_key=True,
        unique=True
    )
    id_driver: UUID = Field(foreign_key="user.id")
    id_client_request: UUID = Field(foreign_key="client_request.id")
    cancelled_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    __table_args__ = (
        Index('idx_driver_cancellation_date', 'id_driver', 'cancelled_at'),
    )
