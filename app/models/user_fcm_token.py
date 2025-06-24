from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime


class UserFCMToken(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")  # Relación foránea a User
    fcm_token: str = Field(
        max_length=512, description="Token FCM del dispositivo")
    device_type: str = Field(
        max_length=20, description="Tipo de dispositivo: android, ios, web")
    device_name: Optional[str] = Field(
        default=None, max_length=100, description="Nombre del dispositivo (opcional)")
    is_active: bool = Field(
        default=True, description="Si el token está activo")
    last_used: Optional[datetime] = Field(
        default_factory=datetime.utcnow, description="Última vez que se usó el token")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow,
                                 nullable=False, sa_column_kwargs={"onupdate": datetime.utcnow})

    # Relación inversa (opcional, si quieres acceder desde User)
    # user: Optional["User"] = Relationship(back_populates="fcm_tokens")
