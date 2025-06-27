from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from uuid import UUID, uuid4
import pytz

COLOMBIA_TZ = pytz.timezone("America/Bogota")


class PaymentMethod(SQLModel, table=True):
    __tablename__ = "payment_method"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(
        COLOMBIA_TZ), nullable=False, sa_column_kwargs={"onupdate": lambda: datetime.now(COLOMBIA_TZ)})

    # Relaciones
    client_requests: List["ClientRequest"] = Relationship(
        back_populates="payment_method")
