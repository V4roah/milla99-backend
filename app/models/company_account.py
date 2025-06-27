from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, String
from typing import Optional, TYPE_CHECKING
from enum import Enum
from datetime import datetime, timezone
from sqlalchemy.orm import relationship
from uuid import UUID, uuid4
import pytz

if TYPE_CHECKING:
    from .user import User
    from .client_request import ClientRequest


class cashflow(str, Enum):
    SERVICE = "SERVICE"
    WITHDRAWS = "WITHDRAWS"
    ADDITIONAL = "ADDITIONAL"


class CompanyAccount(SQLModel, table=True):
    __tablename__ = "company_account"
    id: Optional[UUID] = Field(
        default_factory=uuid4, primary_key=True, unique=True)
    income: Optional[int] = Field(default=0)
    expense: Optional[int] = Field(default=0)
    type: cashflow

    client_request_id: Optional[UUID] = Field(
        default=None, foreign_key="client_request.id")
    date: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=lambda: datetime.now(
        pytz.timezone("America/Bogota")), nullable=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(pytz.timezone("America/Bogota")),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(
            pytz.timezone("America/Bogota"))}
    )

    # Relaciones
    client_request: Optional["ClientRequest"] = Relationship(
        back_populates="company_accounts")
