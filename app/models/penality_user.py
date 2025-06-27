from sqlmodel import SQLModel, Field, Relationship
import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
import pytz

COLOMBIA_TZ = pytz.timezone("America/Bogota")

class statusEnum(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"

class PenalityUser(SQLModel, table=True):
    __tablename__ = "penality_user"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True, unique=True)
    id_client_request: UUID = Field(foreign_key="client_request.id", nullable=False)
    id_user: UUID = Field(foreign_key="user.id", nullable=False)
    id_driver_assigned: UUID = Field(foreign_key="user.id", nullable=False)
    id_driver_get_money: UUID = Field(foreign_key="user.id", nullable=True)
    amount: float = Field(nullable=False)
    status: statusEnum = Field(default=statusEnum.PENDING, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(COLOMBIA_TZ), nullable=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(COLOMBIA_TZ)}
    )

    # Relaciones
    user: "User" = Relationship(
        back_populates="penalities",
        sa_relationship_kwargs={"foreign_keys": "PenalityUser.id_user"}
    )
    client_request: "ClientRequest" = Relationship(
        back_populates="penalities",
        sa_relationship_kwargs={"foreign_keys": "PenalityUser.id_client_request"}
    )