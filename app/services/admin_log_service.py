from sqlmodel import Session, select, func, and_, or_, desc, asc
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
import pytz
from app.models.admin_log import (
    AdminLog, AdminLogCreate, AdminLogRead, AdminLogUpdate,
    AdminLogFilter, AdminLogStatistics, AdminActionType, LogSeverity
)
from app.models.administrador import Administrador, AdminRole
from app.core.db import SessionDep

# Timezone para Colombia
COLOMBIA_TZ = pytz.timezone("America/Bogota")


class AdminLogService:
    """Servicio para manejar logs de administrador"""

    def __init__(self, db: Session):
        self.db = db

    def create_admin_log(self, log_data: AdminLogCreate) -> AdminLog:
        """Crear un nuevo log de administrador"""
        try:
            # Verificar que el administrador existe
            admin = self.db.get(Administrador, log_data.admin_id)
            if not admin:
                raise ValueError(
                    f"Administrador con ID {log_data.admin_id} no encontrado")

            # Crear el log
            admin_log = AdminLog(**log_data.model_dump())
            self.db.add(admin_log)
            self.db.commit()
            self.db.refresh(admin_log)

            return admin_log
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Error al crear log de administrador: {str(e)}")

    def get_admin_logs(self, filters: AdminLogFilter) -> Dict[str, Any]:
        """Obtener logs con filtros y paginación"""
        try:
            # Construir query base
            query = select(AdminLog)

            # Aplicar filtros
            conditions = []

            if filters.admin_id:
                conditions.append(AdminLog.admin_id == filters.admin_id)

            if filters.action_type:
                conditions.append(AdminLog.action_type == filters.action_type)

            if filters.resource_type:
                conditions.append(AdminLog.resource_type ==
                                  filters.resource_type)

            if filters.severity:
                conditions.append(AdminLog.severity == filters.severity)

            if filters.start_date:
                conditions.append(AdminLog.created_at >= filters.start_date)

            if filters.end_date:
                conditions.append(AdminLog.created_at <= filters.end_date)

            # Aplicar condiciones
            if conditions:
                query = query.where(and_(*conditions))

            # Ordenar por fecha de creación (más reciente primero)
            query = query.order_by(desc(AdminLog.created_at))

            # Contar total de registros
            total_query = select(func.count()).select_from(query.subquery())
            total = self.db.exec(total_query).first()

            # Aplicar paginación
            offset = (filters.page - 1) * filters.limit
            query = query.offset(offset).limit(filters.limit)

            # Ejecutar query
            logs = self.db.exec(query).all()

            return {
                "logs": logs,
                "total": total,
                "page": filters.page,
                "limit": filters.limit,
                "total_pages": (total + filters.limit - 1) // filters.limit
            }

        except Exception as e:
            raise Exception(
                f"Error al obtener logs de administrador: {str(e)}")

    def get_admin_log_by_id(self, log_id: UUID) -> Optional[AdminLog]:
        """Obtener un log específico por ID"""
        try:
            return self.db.get(AdminLog, log_id)
        except Exception as e:
            raise Exception(f"Error al obtener log por ID: {str(e)}")

    def get_admin_logs_by_admin(self, admin_id: UUID, current_admin_role: int, limit: int = 50) -> List[AdminLogRead]:
        """Obtener logs según el rol del administrador actual con email del admin"""
        try:
            if current_admin_role == AdminRole.SUPER.value:  # Super usuario - ve todos los logs
                query = select(AdminLog, Administrador.email).join(Administrador).order_by(
                    desc(AdminLog.created_at)).limit(limit)
            elif current_admin_role == AdminRole.SYSTEM.value:  # Admin del sistema - ve logs de nivel 1 + propios
                # Obtener logs de admins con role 1 (BASIC) + sus propios logs
                query = select(AdminLog, Administrador.email).join(Administrador).where(
                    or_(
                        Administrador.role == AdminRole.BASIC.value,  # Logs de Role 1
                        AdminLog.admin_id == admin_id  # Sus propios logs
                    )
                ).order_by(desc(AdminLog.created_at)).limit(limit)
            else:  # Admin básico - solo ve sus propios logs
                query = select(AdminLog, Administrador.email).join(Administrador).where(
                    AdminLog.admin_id == admin_id
                ).order_by(desc(AdminLog.created_at)).limit(limit)

            results = self.db.exec(query).all()
            
            # Convertir a AdminLogRead con email
            logs_with_email = []
            for log, admin_email in results:
                log_read = AdminLogRead.from_orm_with_admin(log, admin_email)
                logs_with_email.append(log_read)
            
            return logs_with_email
        except Exception as e:
            raise Exception(
                f"Error al obtener logs del administrador: {str(e)}")

    def get_logs_by_severity(self, severity: LogSeverity, limit: int = 50) -> List[AdminLog]:
        """Obtener logs por nivel de severidad"""
        try:
            query = select(AdminLog).where(
                AdminLog.severity == severity
            ).order_by(desc(AdminLog.created_at)).limit(limit)

            return self.db.exec(query).all()
        except Exception as e:
            raise Exception(f"Error al obtener logs por severidad: {str(e)}")

    def get_logs_by_action_type(self, action_type: AdminActionType, limit: int = 50) -> List[AdminLog]:
        """Obtener logs por tipo de acción"""
        try:
            query = select(AdminLog).where(
                AdminLog.action_type == action_type
            ).order_by(desc(AdminLog.created_at)).limit(limit)

            return self.db.exec(query).all()
        except Exception as e:
            raise Exception(
                f"Error al obtener logs por tipo de acción: {str(e)}")

    def get_admin_log_statistics(self, days: int = 30) -> AdminLogStatistics:
        """Obtener estadísticas de logs"""
        try:
            # Fecha límite
            start_date = datetime.now(COLOMBIA_TZ) - timedelta(days=days)

            # Total de logs
            total_logs = self.db.exec(
                select(func.count(AdminLog.id)).where(
                    AdminLog.created_at >= start_date)
            ).first()

            # Logs por severidad
            severity_query = select(
                AdminLog.severity,
                func.count(AdminLog.id)
            ).where(AdminLog.created_at >= start_date).group_by(AdminLog.severity)

            logs_by_severity = {}
            for severity, count in self.db.exec(severity_query).all():
                logs_by_severity[severity] = count

            # Logs por tipo de acción
            action_query = select(
                AdminLog.action_type,
                func.count(AdminLog.id)
            ).where(AdminLog.created_at >= start_date).group_by(AdminLog.action_type)

            logs_by_action_type = {}
            for action_type, count in self.db.exec(action_query).all():
                logs_by_action_type[action_type] = count

            # Logs por administrador
            admin_query = select(
                AdminLog.admin_id,
                func.count(AdminLog.id)
            ).where(AdminLog.created_at >= start_date).group_by(AdminLog.admin_id)

            logs_by_admin = {}
            for admin_id, count in self.db.exec(admin_query).all():
                logs_by_admin[str(admin_id)] = count

            # Actividad reciente
            recent_query = select(AdminLog).where(
                AdminLog.created_at >= start_date
            ).order_by(desc(AdminLog.created_at)).limit(10)

            recent_activity = self.db.exec(recent_query).all()

            return AdminLogStatistics(
                total_logs=total_logs or 0,
                logs_by_severity=logs_by_severity,
                logs_by_action_type=logs_by_action_type,
                logs_by_admin=logs_by_admin,
                recent_activity=recent_activity
            )

        except Exception as e:
            raise Exception(f"Error al obtener estadísticas: {str(e)}")

    def log_admin_action(
        self,
        admin_id: UUID,
        action_type: AdminActionType,
        resource_type: str,
        resource_id: Optional[str] = None,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        description: Optional[str] = None,
        severity: LogSeverity = LogSeverity.MEDIUM
    ) -> AdminLog:
        """Función helper para loggear acciones de administrador"""
        try:
            log_data = AdminLogCreate(
                admin_id=admin_id,
                action_type=action_type,
                resource_type=resource_type,
                resource_id=resource_id,
                old_values=old_values,
                new_values=new_values,
                ip_address=ip_address,
                user_agent=user_agent,
                description=description,
                severity=severity
            )

            return self.create_admin_log(log_data)

        except Exception as e:
            raise Exception(
                f"Error al loggear acción de administrador: {str(e)}")


# ============================================================================
# FUNCIONES DE AUDITORÍA ESPECÍFICAS
# ============================================================================

def log_admin_login_success(
    db: Session,
    admin_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AdminLog:
    """Loggear login exitoso de administrador"""
    service = AdminLogService(db)
    return service.log_admin_action(
        admin_id=admin_id,
        action_type=AdminActionType.ADMIN_LOGIN_SUCCESS,
        resource_type="auth",
        ip_address=ip_address,
        user_agent=user_agent,
        description="Login exitoso de administrador",
        severity=LogSeverity.CRITICAL
    )


def log_admin_login_failed(
    db: Session,
    email: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AdminLog:
    """Loggear intento fallido de login de administrador"""
    service = AdminLogService(db)
    return service.log_admin_action(
        admin_id=UUID('00000000-0000-0000-0000-000000000000'),  # ID temporal
        action_type=AdminActionType.ADMIN_LOGIN_FAILED,
        resource_type="auth",
        ip_address=ip_address,
        user_agent=user_agent,
        description=f"Intento fallido de login para email: {email}",
        severity=LogSeverity.HIGH
    )


def log_admin_logout(
    db: Session,
    admin_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AdminLog:
    """Loggear logout de administrador"""
    service = AdminLogService(db)
    return service.log_admin_action(
        admin_id=admin_id,
        action_type=AdminActionType.ADMIN_LOGOUT,
        resource_type="auth",
        ip_address=ip_address,
        user_agent=user_agent,
        description="Logout de administrador",
        severity=LogSeverity.MEDIUM
    )


def log_user_suspension(
    db: Session,
    admin_id: UUID,
    user_id: UUID,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AdminLog:
    """Loggear suspensión de usuario"""
    service = AdminLogService(db)
    return service.log_admin_action(
        admin_id=admin_id,
        action_type=AdminActionType.USER_SUSPENDED,
        resource_type="user",
        resource_id=str(user_id),
        description=f"Usuario suspendido. Razón: {reason or 'No especificada'}",
        ip_address=ip_address,
        user_agent=user_agent,
        severity=LogSeverity.HIGH
    )


def log_user_activation(
    db: Session,
    admin_id: UUID,
    user_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AdminLog:
    """Loggear activación de usuario"""
    service = AdminLogService(db)
    return service.log_admin_action(
        admin_id=admin_id,
        action_type=AdminActionType.USER_ACTIVATED,
        resource_type="user",
        resource_id=str(user_id),
        description="Usuario activado",
        ip_address=ip_address,
        user_agent=user_agent,
        severity=LogSeverity.HIGH
    )


def log_driver_approval(
    db: Session,
    admin_id: UUID,
    driver_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AdminLog:
    """Loggear aprobación de conductor"""
    service = AdminLogService(db)
    return service.log_admin_action(
        admin_id=admin_id,
        action_type=AdminActionType.DRIVER_FORCE_APPROVED,
        resource_type="driver",
        resource_id=str(driver_id),
        description="Conductor aprobado manualmente",
        ip_address=ip_address,
        user_agent=user_agent,
        severity=LogSeverity.CRITICAL
    )


def log_withdrawal_approval(
    db: Session,
    admin_id: UUID,
    withdrawal_id: UUID,
    amount: float,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AdminLog:
    """Loggear aprobación de retiro"""
    service = AdminLogService(db)
    return service.log_admin_action(
        admin_id=admin_id,
        action_type=AdminActionType.WITHDRAWAL_APPROVED,
        resource_type="withdrawal",
        resource_id=str(withdrawal_id),
        description=f"Retiro aprobado por ${amount:,.2f}",
        ip_address=ip_address,
        user_agent=user_agent,
        severity=LogSeverity.CRITICAL
    )


def log_withdrawal_rejection(
    db: Session,
    admin_id: UUID,
    withdrawal_id: UUID,
    reason: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AdminLog:
    """Loggear rechazo de retiro"""
    service = AdminLogService(db)
    return service.log_admin_action(
        admin_id=admin_id,
        action_type=AdminActionType.WITHDRAWAL_REJECTED,
        resource_type="withdrawal",
        resource_id=str(withdrawal_id),
        description=f"Retiro rechazado. Razón: {reason}",
        ip_address=ip_address,
        user_agent=user_agent,
        severity=LogSeverity.CRITICAL
    )


def log_project_settings_update(
    db: Session,
    admin_id: UUID,
    old_values: Dict,
    new_values: Dict,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AdminLog:
    """Loggear actualización de configuraciones del proyecto"""
    service = AdminLogService(db)
    return service.log_admin_action(
        admin_id=admin_id,
        action_type=AdminActionType.PROJECT_SETTINGS_UPDATED,
        resource_type="project_settings",
        old_values=old_values,
        new_values=new_values,
        description="Configuraciones del proyecto actualizadas",
        ip_address=ip_address,
        user_agent=user_agent,
        severity=LogSeverity.CRITICAL
    )


def log_document_verification(
    db: Session,
    admin_id: UUID,
    document_id: UUID,
    status: str,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AdminLog:
    """Loggear verificación de documento"""
    service = AdminLogService(db)
    action_type = AdminActionType.DOCUMENT_APPROVED if status == "approved" else AdminActionType.DOCUMENT_REJECTED

    return service.log_admin_action(
        admin_id=admin_id,
        action_type=action_type,
        resource_type="document",
        resource_id=str(document_id),
        description=f"Documento {status}. Razón: {reason or 'No especificada'}",
        ip_address=ip_address,
        user_agent=user_agent,
        severity=LogSeverity.HIGH
    )


# ============================================================================
# FUNCIONES DE MONITOREO
# ============================================================================

def detect_suspicious_activity(db: Session, admin_id: UUID, hours: int = 24) -> List[AdminLog]:
    """Detectar actividad sospechosa de un administrador"""
    service = AdminLogService(db)

    # Obtener logs de las últimas horas
    start_time = datetime.now(COLOMBIA_TZ) - timedelta(hours=hours)

    query = select(AdminLog).where(
        and_(
            AdminLog.admin_id == admin_id,
            AdminLog.created_at >= start_time,
            AdminLog.severity.in_([LogSeverity.HIGH, LogSeverity.CRITICAL])
        )
    ).order_by(desc(AdminLog.created_at))

    return db.exec(query).all()


def get_high_severity_logs(db: Session, hours: int = 24) -> List[AdminLog]:
    """Obtener logs de alta severidad de las últimas horas"""
    service = AdminLogService(db)

    start_time = datetime.now(COLOMBIA_TZ) - timedelta(hours=hours)

    query = select(AdminLog).where(
        and_(
            AdminLog.created_at >= start_time,
            AdminLog.severity.in_([LogSeverity.HIGH, LogSeverity.CRITICAL])
        )
    ).order_by(desc(AdminLog.created_at))

    return db.exec(query).all()


def get_critical_actions_by_admin(db: Session, admin_id: UUID, days: int = 7) -> List[AdminLog]:
    """Obtener acciones críticas de un administrador"""
    service = AdminLogService(db)

    start_date = datetime.now(COLOMBIA_TZ) - timedelta(days=days)

    query = select(AdminLog).where(
        and_(
            AdminLog.admin_id == admin_id,
            AdminLog.created_at >= start_date,
            AdminLog.severity == LogSeverity.CRITICAL
        )
    ).order_by(desc(AdminLog.created_at))

    return db.exec(query).all()
