from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum
import pytz

COLOMBIA_TZ = pytz.timezone("America/Bogota")


class AdminRole(int, Enum):
    """Roles de administrador con diferentes niveles de acceso"""
    BASIC = 1      # Admin básico - Solo sus propios logs
    SYSTEM = 2     # Admin sistema - Logs de admins nivel 1
    SUPER = 3      # Super admin - Todos los logs


class Administrador(SQLModel, table=True):
    id: Optional[UUID] = Field(
        default_factory=uuid4, primary_key=True, unique=True)
    email: str = Field(index=True, unique=True, nullable=False)
    password: str = Field(nullable=False)
    role: int = Field(nullable=False, default=AdminRole.BASIC.value)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ), nullable=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(COLOMBIA_TZ)}
    )

    # Relación con logs de administrador
    admin_logs: List["AdminLog"] = Relationship(back_populates="admin")

    @property
    def admin_role(self) -> AdminRole:
        """Obtener el enum AdminRole basado en el valor numérico"""
        return AdminRole(self.role)

    @admin_role.setter
    def admin_role(self, value: AdminRole):
        """Establecer el valor numérico basado en el enum"""
        self.role = value.value
