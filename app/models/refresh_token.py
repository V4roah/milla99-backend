from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from uuid import UUID, uuid4
import pytz

COLOMBIA_TZ = pytz.timezone("America/Bogota")


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_token"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    # Hash del token para seguridad
    token_hash: str = Field(max_length=255, index=True)
    expires_at: datetime = Field(index=True)
    is_revoked: bool = Field(default=False, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ))

    # Información adicional para auditoría
    user_agent: Optional[str] = Field(default=None, max_length=500)
    ip_address: Optional[str] = Field(default=None, max_length=45)

    # Relación con el usuario
    user: "User" = Relationship(back_populates="refresh_tokens")

    class Config:
        arbitrary_types_allowed = True
