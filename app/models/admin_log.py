from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from enum import Enum
from datetime import datetime
from uuid import UUID, uuid4
import pytz
from pydantic import BaseModel

# Timezone para Colombia
COLOMBIA_TZ = pytz.timezone("America/Bogota")


class AdminActionType(str, Enum):
    # CRÍTICO
    ADMIN_LOGIN_SUCCESS = "ADMIN_LOGIN_SUCCESS"
    ADMIN_LOGIN_FAILED = "ADMIN_LOGIN_FAILED"
    ADMIN_LOGOUT = "ADMIN_LOGOUT"
    ADMIN_PASSWORD_CHANGED = "ADMIN_PASSWORD_CHANGED"
    PROJECT_SETTINGS_UPDATED = "PROJECT_SETTINGS_UPDATED"
    CONFIG_SERVICE_VALUE_UPDATED = "CONFIG_SERVICE_VALUE_UPDATED"
    WITHDRAWAL_APPROVED = "WITHDRAWAL_APPROVED"
    WITHDRAWAL_REJECTED = "WITHDRAWAL_REJECTED"
    BALANCE_ADJUSTED = "BALANCE_ADJUSTED"
    TRANSACTION_CREATED = "TRANSACTION_CREATED"
    DRIVER_FORCE_APPROVED = "DRIVER_FORCE_APPROVED"
    DRIVER_SUSPENDED = "DRIVER_SUSPENDED"
    DRIVER_REACTIVATED = "DRIVER_REACTIVATED"
    BATCH_SUSPENSIONS_LIFTED = "BATCH_SUSPENSIONS_LIFTED"

    # ALTO
    DOCUMENT_APPROVED = "DOCUMENT_APPROVED"
    DOCUMENT_REJECTED = "DOCUMENT_REJECTED"
    DOCUMENT_EXPIRED_UPDATED = "DOCUMENT_EXPIRED_UPDATED"
    MULTIPLE_DOCUMENTS_UPDATED = "MULTIPLE_DOCUMENTS_UPDATED"
    USER_SUSPENDED = "USER_SUSPENDED"
    USER_ACTIVATED = "USER_ACTIVATED"
    USER_ROLE_CHANGED = "USER_ROLE_CHANGED"
    USER_VERIFIED = "USER_VERIFIED"
    SENSITIVE_DATA_ACCESSED = "SENSITIVE_DATA_ACCESSED"
    STATISTICS_EXPORTED = "STATISTICS_EXPORTED"
    USER_DATA_VIEWED = "USER_DATA_VIEWED"
    FINANCIAL_REPORT_GENERATED = "FINANCIAL_REPORT_GENERATED"
    VEHICLE_TYPE_CONFIG_UPDATED = "VEHICLE_TYPE_CONFIG_UPDATED"
    SERVICE_CONFIG_UPDATED = "SERVICE_CONFIG_UPDATED"
    REFERRAL_CONFIG_UPDATED = "REFERRAL_CONFIG_UPDATED"

    # MEDIO
    DRIVER_INFO_VIEWED = "DRIVER_INFO_VIEWED"
    DRIVER_DOCUMENTS_VIEWED = "DRIVER_DOCUMENTS_VIEWED"
    DRIVER_STATUS_CHECKED = "DRIVER_STATUS_CHECKED"
    DRIVER_STATISTICS_VIEWED = "DRIVER_STATISTICS_VIEWED"
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_INFO_VIEWED = "USER_INFO_VIEWED"
    USER_LIST_VIEWED = "USER_LIST_VIEWED"
    WITHDRAWAL_LIST_VIEWED = "WITHDRAWAL_LIST_VIEWED"
    WITHDRAWAL_DETAILS_VIEWED = "WITHDRAWAL_DETAILS_VIEWED"
    WITHDRAWAL_FILTERED = "WITHDRAWAL_FILTERED"
    STATISTICS_SUMMARY_VIEWED = "STATISTICS_SUMMARY_VIEWED"
    DRIVER_ANALYTICS_VIEWED = "DRIVER_ANALYTICS_VIEWED"
    FINANCIAL_METRICS_VIEWED = "FINANCIAL_METRICS_VIEWED"
    SERVICE_STATS_VIEWED = "SERVICE_STATS_VIEWED"

    # BAJO
    PROJECT_SETTINGS_VIEWED = "PROJECT_SETTINGS_VIEWED"
    CONFIG_VALUES_VIEWED = "CONFIG_VALUES_VIEWED"
    PENDING_DOCS_VIEWED = "PENDING_DOCS_VIEWED"
    APPROVED_DOCS_VIEWED = "APPROVED_DOCS_VIEWED"
    VERIFICATION_STATUS_VIEWED = "VERIFICATION_STATUS_VIEWED"
    EXPIRING_DOCS_CHECKED = "EXPIRING_DOCS_CHECKED"
    METRICS_VIEWED = "METRICS_VIEWED"
    HEALTH_CHECK_VIEWED = "HEALTH_CHECK_VIEWED"
    ADMIN_DASHBOARD_ACCESSED = "ADMIN_DASHBOARD_ACCESSED"
    REPORTS_SECTION_ACCESSED = "REPORTS_SECTION_ACCESSED"
    SETTINGS_SECTION_ACCESSED = "SETTINGS_SECTION_ACCESSED"
    USERS_SECTION_ACCESSED = "USERS_SECTION_ACCESSED"


class LogSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AdminLog(SQLModel, table=True):
    __tablename__ = "admin_logs"

    id: Optional[UUID] = Field(
        default_factory=uuid4, primary_key=True, unique=True)
    admin_id: UUID = Field(foreign_key="administrador.id")
    action_type: AdminActionType = Field(
        description="Tipo de acción realizada")
    resource_type: str = Field(description="Tipo de recurso afectado")
    resource_id: Optional[str] = Field(
        default=None, description="ID del recurso afectado")
    old_values: Optional[dict] = Field(
        default=None, description="Valores anteriores (JSON)")
    new_values: Optional[dict] = Field(
        default=None, description="Valores nuevos (JSON)")
    ip_address: Optional[str] = Field(
        default=None, description="Dirección IP del administrador")
    user_agent: Optional[str] = Field(
        default=None, description="User-Agent del navegador")
    description: Optional[str] = Field(
        default=None, description="Descripción detallada de la acción")
    severity: LogSeverity = Field(
        default=LogSeverity.MEDIUM,
        description="Nivel de severidad del log"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ),
        nullable=False,
        description="Fecha y hora de creación del log"
    )

    # Relación con administrador
    admin: Optional["Administrador"] = Relationship(
        back_populates="admin_logs")


class AdminLogCreate(SQLModel):
    admin_id: UUID = Field(description="ID del administrador")
    action_type: AdminActionType = Field(
        description="Tipo de acción realizada")
    resource_type: str = Field(description="Tipo de recurso afectado")
    resource_id: Optional[str] = Field(
        default=None, description="ID del recurso afectado")
    old_values: Optional[dict] = Field(
        default=None, description="Valores anteriores")
    new_values: Optional[dict] = Field(
        default=None, description="Valores nuevos")
    ip_address: Optional[str] = Field(default=None, description="Dirección IP")
    user_agent: Optional[str] = Field(default=None, description="User-Agent")
    description: Optional[str] = Field(default=None, description="Descripción")
    severity: LogSeverity = Field(
        default=LogSeverity.MEDIUM, description="Nivel de severidad")


class AdminLogRead(BaseModel):
    id: UUID
    admin_id: UUID
    action_type: AdminActionType
    resource_type: str
    resource_id: Optional[str]
    old_values: Optional[dict]
    new_values: Optional[dict]
    ip_address: Optional[str]
    user_agent: Optional[str]
    description: Optional[str]
    severity: LogSeverity
    created_at: datetime

    class Config:
        from_attributes = True


class AdminLogUpdate(SQLModel):
    description: Optional[str] = None
    severity: Optional[LogSeverity] = None


class AdminLogFilter(BaseModel):
    admin_id: Optional[UUID] = None
    action_type: Optional[AdminActionType] = None
    resource_type: Optional[str] = None
    severity: Optional[LogSeverity] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = 1
    limit: int = 50


class AdminLogStatistics(BaseModel):
    total_logs: int
    logs_by_severity: dict
    logs_by_action_type: dict
    logs_by_admin: dict
    recent_activity: List[AdminLogRead]

    class Config:
        from_attributes = True
