from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
import pytz

COLOMBIA_TZ = pytz.timezone("America/Bogota")


class VerificationBase(SQLModel):
    user_id: UUID = Field(foreign_key="user.id")
    verification_code: str
    expires_at: datetime
    is_verified: bool = Field(default=False)
    attempts: int = Field(default=0)


class Verification(VerificationBase, table=True):
    id: Optional[UUID] = Field(
        default_factory=uuid4, primary_key=True, unique=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ), nullable=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(COLOMBIA_TZ)}
    )


class VerificationCreate(VerificationBase):
    pass
