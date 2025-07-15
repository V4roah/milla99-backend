import functools
from typing import Optional, Callable, Any, Dict
from uuid import UUID
from fastapi import Request, Depends
from sqlmodel import Session
from app.models.admin_log import AdminActionType, LogSeverity
from app.core.db import SessionDep
from app.core.dependencies.admin_auth import get_current_admin_user
import json


def log_withdrawal_approval():
    """
    Decorador para aprobación de retiros con detalles específicos
    Complementa el middleware que registra la acción automáticamente
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            *args,
            request: Request,
            session: SessionDep,
            current_admin=Depends(get_current_admin_user),
            **kwargs
        ):
            # Ejecutar la función original
            result = await func(*args, request=request, session=session, current_admin=current_admin, **kwargs)

            try:
                # Importar el servicio aquí para evitar circular imports
                from app.services.admin_log_service import AdminLogService

                # Extraer detalles específicos de la función
                withdrawal_id = kwargs.get('withdrawal_id') or kwargs.get('id')
                amount = kwargs.get('amount')
                reason = kwargs.get('reason', 'No especificada')

                # Capturar datos de la request
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

                # Crear descripción detallada
                description = f"Retiro aprobado - ID: {withdrawal_id}"
                if amount:
                    description += f", Monto: ${amount:,.2f}"
                description += f", Razón: {reason}"

                # Crear el log específico (complementa el middleware)
                service = AdminLogService(session)
                service.log_admin_action(
                    admin_id=current_admin.id,
                    action_type=AdminActionType.WITHDRAWAL_APPROVED,
                    resource_type="withdrawal",
                    resource_id=str(withdrawal_id) if withdrawal_id else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    description=description,
                    severity=LogSeverity.CRITICAL
                )

            except Exception as e:
                # No fallar la función principal si el logging falla
                print(f"Error al loggear aprobación de retiro: {str(e)}")

            return result

        return wrapper
    return decorator


def log_withdrawal_rejection():
    """
    Decorador para rechazo de retiros con detalles específicos
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            *args,
            request: Request,
            db: Session = Depends(SessionDep),
            current_admin=Depends(get_current_admin_user),
            **kwargs
        ):
            # Ejecutar la función original
            result = await func(*args, request=request, db=db, current_admin=current_admin, **kwargs)

            try:
                # Importar el servicio aquí para evitar circular imports
                from app.services.admin_log_service import AdminLogService

                # Extraer detalles específicos
                withdrawal_id = kwargs.get('withdrawal_id') or kwargs.get('id')
                reason = kwargs.get('reason', 'No especificada')

                # Capturar datos de la request
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

                # Crear descripción detallada
                description = f"Retiro rechazado - ID: {withdrawal_id}, Razón: {reason}"

                # Crear el log específico
                service = AdminLogService(db)
                service.log_admin_action(
                    admin_id=current_admin.id,
                    action_type=AdminActionType.WITHDRAWAL_REJECTED,
                    resource_type="withdrawal",
                    resource_id=str(withdrawal_id) if withdrawal_id else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    description=description,
                    severity=LogSeverity.CRITICAL
                )

            except Exception as e:
                print(f"Error al loggear rechazo de retiro: {str(e)}")

            return result

        return wrapper
    return decorator


def log_balance_adjustment():
    """
    Decorador para ajustes de balance con detalles específicos
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            *args,
            request: Request,
            db: Session = Depends(SessionDep),
            current_admin=Depends(get_current_admin_user),
            **kwargs
        ):
            # Ejecutar la función original
            result = await func(*args, request=request, db=db, current_admin=current_admin, **kwargs)

            try:
                # Importar el servicio aquí para evitar circular imports
                from app.services.admin_log_service import AdminLogService

                # Extraer detalles específicos
                user_id = kwargs.get('user_id')
                old_balance = kwargs.get('old_balance')
                new_balance = kwargs.get('new_balance')
                reason = kwargs.get('reason', 'No especificada')

                # Capturar datos de la request
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

                # Crear descripción detallada
                description = f"Ajuste de balance - Usuario: {user_id}"
                if old_balance is not None and new_balance is not None:
                    difference = new_balance - old_balance
                    description += f", Balance anterior: ${old_balance:,.2f}, Nuevo: ${new_balance:,.2f}, Diferencia: ${difference:,.2f}"
                description += f", Razón: {reason}"

                # Crear el log específico
                service = AdminLogService(db)
                service.log_admin_action(
                    admin_id=current_admin.id,
                    action_type=AdminActionType.BALANCE_ADJUSTED,
                    resource_type="user",
                    resource_id=str(user_id) if user_id else None,
                    old_values={
                        "balance": old_balance} if old_balance is not None else None,
                    new_values={
                        "balance": new_balance} if new_balance is not None else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    description=description,
                    severity=LogSeverity.CRITICAL
                )

            except Exception as e:
                print(f"Error al loggear ajuste de balance: {str(e)}")

            return result

        return wrapper
    return decorator


def log_project_settings_update():
    """
    Decorador para actualización de configuraciones del proyecto
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            *args,
            request: Request,
            db: Session = Depends(SessionDep),
            current_admin=Depends(get_current_admin_user),
            **kwargs
        ):
            # Ejecutar la función original
            result = await func(*args, request=request, db=db, current_admin=current_admin, **kwargs)

            try:
                # Importar el servicio aquí para evitar circular imports
                from app.services.admin_log_service import AdminLogService

                # Capturar datos de la request
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

                # Intentar extraer datos del body de la request
                old_values = None
                new_values = None

                try:
                    body = await request.json()
                    new_values = body
                except:
                    pass

                # Crear descripción
                description = "Configuraciones del proyecto actualizadas"
                if new_values:
                    description += f" - Configuraciones: {json.dumps(new_values, indent=2)}"

                # Crear el log específico
                service = AdminLogService(db)
                service.log_admin_action(
                    admin_id=current_admin.id,
                    action_type=AdminActionType.PROJECT_SETTINGS_UPDATED,
                    resource_type="project_settings",
                    old_values=old_values,
                    new_values=new_values,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    description=description,
                    severity=LogSeverity.CRITICAL
                )

            except Exception as e:
                print(
                    f"Error al loggear actualización de configuraciones: {str(e)}")

            return result

        return wrapper
    return decorator


def log_admin_password_change():
    """
    Decorador para cambio de contraseña de administrador
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            *args,
            request: Request,
            db: Session = Depends(SessionDep),
            current_admin=Depends(get_current_admin_user),
            **kwargs
        ):
            # Ejecutar la función original
            result = await func(*args, request=request, db=db, current_admin=current_admin, **kwargs)

            try:
                # Importar el servicio aquí para evitar circular imports
                from app.services.admin_log_service import AdminLogService

                # Capturar datos de la request
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

                # Crear descripción
                description = f"Contraseña de administrador cambiada - Admin: {current_admin.email}"

                # Crear el log específico
                service = AdminLogService(db)
                service.log_admin_action(
                    admin_id=current_admin.id,
                    action_type=AdminActionType.ADMIN_PASSWORD_CHANGED,
                    resource_type="auth",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    description=description,
                    severity=LogSeverity.CRITICAL
                )

            except Exception as e:
                print(f"Error al loggear cambio de contraseña: {str(e)}")

            return result

        return wrapper
    return decorator


def log_driver_force_approval():
    """
    Decorador para aprobación forzada de conductor
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            *args,
            request: Request,
            db: Session = Depends(SessionDep),
            current_admin=Depends(get_current_admin_user),
            **kwargs
        ):
            # Ejecutar la función original
            result = await func(*args, request=request, db=db, current_admin=current_admin, **kwargs)

            try:
                # Importar el servicio aquí para evitar circular imports
                from app.services.admin_log_service import AdminLogService

                # Extraer detalles específicos
                driver_id = kwargs.get('driver_id') or kwargs.get('id')
                reason = kwargs.get('reason', 'Aprobación manual')

                # Capturar datos de la request
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

                # Crear descripción detallada
                description = f"Conductor aprobado manualmente - ID: {driver_id}, Razón: {reason}"

                # Crear el log específico
                service = AdminLogService(db)
                service.log_admin_action(
                    admin_id=current_admin.id,
                    action_type=AdminActionType.DRIVER_FORCE_APPROVED,
                    resource_type="driver",
                    resource_id=str(driver_id) if driver_id else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    description=description,
                    severity=LogSeverity.CRITICAL
                )

            except Exception as e:
                print(f"Error al loggear aprobación de conductor: {str(e)}")

            return result

        return wrapper
    return decorator


def log_document_verification():
    """
    Decorador para verificación de documentos
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            *args,
            request: Request,
            db: Session = Depends(SessionDep),
            current_admin=Depends(get_current_admin_user),
            **kwargs
        ):
            # Ejecutar la función original
            result = await func(*args, request=request, db=db, current_admin=current_admin, **kwargs)

            try:
                # Importar el servicio aquí para evitar circular imports
                from app.services.admin_log_service import AdminLogService

                # Extraer detalles específicos
                document_id = kwargs.get('document_id') or kwargs.get('id')
                status = kwargs.get('status', 'approved')
                reason = kwargs.get('reason', 'No especificada')

                # Determinar tipo de acción
                action_type = AdminActionType.DOCUMENT_APPROVED if status == "approved" else AdminActionType.DOCUMENT_REJECTED

                # Capturar datos de la request
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

                # Crear descripción detallada
                description = f"Documento {status} - ID: {document_id}, Razón: {reason}"

                # Crear el log específico
                service = AdminLogService(db)
                service.log_admin_action(
                    admin_id=current_admin.id,
                    action_type=action_type,
                    resource_type="document",
                    resource_id=str(document_id) if document_id else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    description=description,
                    severity=LogSeverity.HIGH
                )

            except Exception as e:
                print(f"Error al loggear verificación de documento: {str(e)}")

            return result

        return wrapper
    return decorator


def log_user_suspension():
    """
    Decorador para suspensión de usuario
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            *args,
            request: Request,
            db: Session = Depends(SessionDep),
            current_admin=Depends(get_current_admin_user),
            **kwargs
        ):
            # Ejecutar la función original
            result = await func(*args, request=request, db=db, current_admin=current_admin, **kwargs)

            try:
                # Importar el servicio aquí para evitar circular imports
                from app.services.admin_log_service import AdminLogService

                # Extraer detalles específicos
                user_id = kwargs.get('user_id') or kwargs.get('id')
                reason = kwargs.get('reason', 'No especificada')

                # Capturar datos de la request
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

                # Crear descripción detallada
                description = f"Usuario suspendido - ID: {user_id}, Razón: {reason}"

                # Crear el log específico
                service = AdminLogService(db)
                service.log_admin_action(
                    admin_id=current_admin.id,
                    action_type=AdminActionType.USER_SUSPENDED,
                    resource_type="user",
                    resource_id=str(user_id) if user_id else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    description=description,
                    severity=LogSeverity.HIGH
                )

            except Exception as e:
                print(f"Error al loggear suspensión de usuario: {str(e)}")

            return result

        return wrapper
    return decorator


def log_user_activation():
    """
    Decorador para activación de usuario
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            *args,
            request: Request,
            db: Session = Depends(SessionDep),
            current_admin=Depends(get_current_admin_user),
            **kwargs
        ):
            # Ejecutar la función original
            result = await func(*args, request=request, db=db, current_admin=current_admin, **kwargs)

            try:
                # Importar el servicio aquí para evitar circular imports
                from app.services.admin_log_service import AdminLogService

                # Extraer detalles específicos
                user_id = kwargs.get('user_id') or kwargs.get('id')
                reason = kwargs.get('reason', 'Activación manual')

                # Capturar datos de la request
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

                # Crear descripción detallada
                description = f"Usuario activado - ID: {user_id}, Razón: {reason}"

                # Crear el log específico
                service = AdminLogService(db)
                service.log_admin_action(
                    admin_id=current_admin.id,
                    action_type=AdminActionType.USER_ACTIVATED,
                    resource_type="user",
                    resource_id=str(user_id) if user_id else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    description=description,
                    severity=LogSeverity.HIGH
                )

            except Exception as e:
                print(f"Error al loggear activación de usuario: {str(e)}")

            return result

        return wrapper
    return decorator


def log_transaction_approval():
    """
    Decorador para aprobación de transacciones con detalles específicos
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            *args,
            request: Request,
            session: SessionDep,
            current_admin=Depends(get_current_admin_user),
            **kwargs
        ):
            # Ejecutar la función original
            result = await func(*args, request=request, session=session, current_admin=current_admin, **kwargs)

            try:
                # Importar el servicio aquí para evitar circular imports
                from app.services.admin_log_service import AdminLogService

                # Extraer detalles específicos de la función
                transaction_id = kwargs.get(
                    'transaction_id') or kwargs.get('id')
                amount = kwargs.get('amount')
                transaction_type = kwargs.get(
                    'transaction_type', 'No especificado')

                # Capturar datos de la request
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

                # Crear descripción detallada
                description = f"Transacción aprobada - ID: {transaction_id}, Tipo: {transaction_type}"
                if amount:
                    description += f", Monto: ${amount:,}"

                # Crear el log específico
                service = AdminLogService(session)
                service.log_admin_action(
                    admin_id=current_admin.id,
                    action_type=AdminActionType.TRANSACTION_APPROVED,
                    resource_type="transaction",
                    resource_id=str(
                        transaction_id) if transaction_id else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    description=description,
                    severity=LogSeverity.CRITICAL
                )

            except Exception as e:
                # No fallar la función principal si el logging falla
                print(f"Error al loggear aprobación de transacción: {str(e)}")

            return result

        return wrapper
    return decorator


# ============================================================================
# DECORADORES DE UTILIDAD
# ============================================================================

def log_critical_action(action_type: AdminActionType, resource_type: str):
    """
    Decorador genérico para acciones críticas
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            *args,
            request: Request,
            db: Session = Depends(SessionDep),
            current_admin=Depends(get_current_admin_user),
            **kwargs
        ):
            # Ejecutar la función original
            result = await func(*args, request=request, db=db, current_admin=current_admin, **kwargs)

            try:
                # Importar el servicio aquí para evitar circular imports
                from app.services.admin_log_service import AdminLogService

                # Capturar datos de la request
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

                # Crear descripción
                description = f"Acción crítica ejecutada - {action_type.value}"

                # Crear el log específico
                service = AdminLogService(db)
                service.log_admin_action(
                    admin_id=current_admin.id,
                    action_type=action_type,
                    resource_type=resource_type,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    description=description,
                    severity=LogSeverity.CRITICAL
                )

            except Exception as e:
                print(f"Error al loggear acción crítica: {str(e)}")

            return result

        return wrapper
    return decorator


def log_with_details(
    action_type: AdminActionType,
    resource_type: str,
    severity: LogSeverity = LogSeverity.MEDIUM
):
    """
    Decorador genérico con captura de detalles
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            *args,
            request: Request,
            db: Session = Depends(SessionDep),
            current_admin=Depends(get_current_admin_user),
            **kwargs
        ):
            # Ejecutar la función original
            result = await func(*args, request=request, db=db, current_admin=current_admin, **kwargs)

            try:
                # Importar el servicio aquí para evitar circular imports
                from app.services.admin_log_service import AdminLogService

                # Capturar datos de la request
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

                # Intentar extraer datos del body
                new_values = None
                try:
                    body = await request.json()
                    new_values = body
                except:
                    pass

                # Crear descripción
                description = f"Acción ejecutada - {action_type.value}"
                if new_values:
                    description += f" - Detalles: {json.dumps(new_values, indent=2)}"

                # Crear el log específico
                service = AdminLogService(db)
                service.log_admin_action(
                    admin_id=current_admin.id,
                    action_type=action_type,
                    resource_type=resource_type,
                    new_values=new_values,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    description=description,
                    severity=severity
                )

            except Exception as e:
                print(f"Error al loggear acción con detalles: {str(e)}")

            return result

        return wrapper
    return decorator
