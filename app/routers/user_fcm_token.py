from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlmodel import Session
from app.core.db import SessionDep
from app.core.dependencies.auth import get_current_user
from app.services.user_fcm_token_service import UserFCMTokenService
from app.services.notification_service import NotificationService
from app.models.user_fcm_token import UserFCMToken
from app.models.user import User
from pydantic import BaseModel
from uuid import UUID
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/fcm-token", tags=["FCM Token"])

# Esquema para registrar token


class FCMTokenRegisterRequest(BaseModel):
    fcm_token: str
    device_type: str
    device_name: Optional[str] = None

# Esquema para respuesta de token


class FCMTokenResponse(BaseModel):
    id: UUID
    fcm_token: str
    device_type: str
    device_name: Optional[str]
    is_active: bool
    last_used: Optional[datetime]
    created_at: datetime
    updated_at: datetime

# Esquema para respuesta de lista de tokens


class FCMTokenListResponse(BaseModel):
    tokens: List[FCMTokenResponse]

# Esquema para testing de notificaciones de negocio


class BusinessNotificationTestRequest(BaseModel):
    notification_type: str
    request_id: Optional[UUID] = None
    driver_id: Optional[UUID] = None
    fare: Optional[float] = None
    estimated_time: Optional[int] = None
    reason: Optional[str] = None


@router.post("/register", response_model=FCMTokenResponse, status_code=status.HTTP_201_CREATED, description="""
Registra o actualiza un token FCM para el usuario autenticado.

**Propósito:**
Permite que la app móvil/web registre el token FCM del dispositivo para recibir notificaciones push.

**Parámetros:**
- `fcm_token`: Token FCM generado por Firebase para el dispositivo (obligatorio).
- `device_type`: Tipo de dispositivo (`android`, `ios` o `web`).
- `device_name`: Nombre del dispositivo (opcional, ejemplo: "Honor 90").

**Respuesta:**
Devuelve el token registrado o actualizado con toda su información.

**Notas:**
- El endpoint requiere autenticación (Bearer token).
- Si el token ya existe para el usuario, se actualiza y se marca como activo.
- Si es nuevo, se crea.
""")
def register_fcm_token(
    request: Request,
    data: FCMTokenRegisterRequest,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Registra o actualiza un token FCM para el usuario autenticado."""
    service = UserFCMTokenService(session)
    token = service.register_token(
        user_id=current_user.id,
        fcm_token=data.fcm_token,
        device_type=data.device_type,
        device_name=data.device_name
    )
    return FCMTokenResponse.model_validate(token, from_attributes=True)


@router.delete("/deactivate", status_code=status.HTTP_200_OK, description="""
Desactiva un token FCM específico del usuario autenticado.

**Propósito:**
Permite que la app elimine/desactive el token FCM cuando el usuario cierra sesión o desinstala la app.

**Parámetros:**
- `fcm_token`: Token FCM a desactivar (en query string).

**Respuesta:**
Mensaje de confirmación si el token fue desactivado correctamente.

**Notas:**
- El endpoint requiere autenticación (Bearer token).
- Si el token no existe, devuelve error 404.
""")
def deactivate_fcm_token(
    session: SessionDep,
    fcm_token: str = Query(..., description="Token FCM a desactivar"),
    current_user: User = Depends(get_current_user)
):
    """Desactiva un token FCM específico del usuario autenticado."""
    service = UserFCMTokenService(session)
    success = service.deactivate_token(
        user_id=current_user.id, fcm_token=fcm_token)
    if not success:
        raise HTTPException(status_code=404, detail="Token FCM no encontrado")
    return {"detail": "Token FCM desactivado exitosamente"}


@router.get("/my-tokens", response_model=FCMTokenListResponse, description="""
Obtiene todos los tokens FCM (activos e inactivos) del usuario autenticado.

**Propósito:**
Permite al usuario ver todos los dispositivos donde tiene la app activa y sus tokens FCM registrados.

**Respuesta:**
Lista de todos los tokens FCM del usuario, con información de cada dispositivo.

**Notas:**
- El endpoint requiere autenticación (Bearer token).
- Útil para mostrar en el perfil del usuario o para debugging.
""")
def get_my_fcm_tokens(
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Obtiene todos los tokens FCM activos del usuario autenticado."""
    service = UserFCMTokenService(session)
    tokens = service.get_all_tokens(user_id=current_user.id)
    return FCMTokenListResponse(tokens=[FCMTokenResponse.model_validate(t, from_attributes=True) for t in tokens])


@router.post("/test-notification", description="""
Envía una notificación de prueba a todos los dispositivos del usuario autenticado.

**Propósito:**
Permite verificar que el sistema de notificaciones push funciona correctamente para el usuario.

**Respuesta:**
Mensaje de confirmación y resultado del envío (cantidad de notificaciones exitosas y fallidas).

**Notas:**
- El endpoint requiere autenticación (Bearer token).
- Útil solo para testing y debugging.
""")
def send_test_notification(
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Envía una notificación de prueba a todos los dispositivos del usuario autenticado."""
    service = UserFCMTokenService(session)
    tokens = service.get_active_tokens(user_id=current_user.id)
    if not tokens:
        raise HTTPException(
            status_code=404, detail="No hay tokens FCM activos para este usuario")
    result = service.send_notification(
        tokens=tokens,
        title="Notificación de prueba",
        body="¡Esta es una notificación de prueba desde Milla99!",
        data={"type": "test"}
    )
    return {"detail": "Notificación enviada", "result": result}


@router.post("/test-business-notification", description="""
Envía una notificación de prueba específica de negocio para Milla99.

**Propósito:**
Permite probar cada tipo de notificación de negocio con datos simulados.

**Parámetros:**
- `notification_type`: Tipo de notificación a probar:
  - `driver_offer`: Nueva oferta de conductor
  - `driver_assigned`: Conductor asignado
  - `driver_on_the_way`: Conductor en camino
  - `driver_arrived`: Conductor llegó
  - `trip_started`: Viaje iniciado
  - `trip_finished`: Viaje terminado
  - `trip_cancelled_by_driver`: Cancelación por conductor
  - `trip_assigned`: Viaje asignado al conductor
  - `trip_cancelled_by_client`: Cancelación por cliente
  - `payment_received`: Pago recibido
- `request_id`: ID de la solicitud (opcional, se genera uno si no se proporciona)
- `driver_id`: ID del conductor (opcional, se usa el usuario autenticado si no se proporciona)
- `fare`: Tarifa (opcional, para notificaciones que la requieren)
- `estimated_time`: Tiempo estimado en minutos (opcional)
- `reason`: Razón de cancelación (opcional)

**Respuesta:**
Mensaje de confirmación y resultado del envío.

**Notas:**
- El endpoint requiere autenticación (Bearer token).
- Útil solo para testing y debugging.
- Los datos son simulados si no se proporcionan.
""")
def send_business_notification_test(
    data: BusinessNotificationTestRequest,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    try:
        notification_service = NotificationService(session)

        # Generar datos de prueba si no se proporcionan
        request_id = data.request_id or UUID(
            '550e8400-e29b-41d4-a716-446655440000')
        driver_id = data.driver_id or current_user.id
        fare = data.fare or 25000.0
        estimated_time = data.estimated_time or 15

        result = None

        # Enviar notificación según el tipo
        if data.notification_type == "driver_offer":
            result = notification_service.notify_driver_offer(
                request_id=request_id,
                driver_id=driver_id,
                fare=fare
            )
        elif data.notification_type == "driver_assigned":
            result = notification_service.notify_driver_assigned(
                request_id=request_id,
                driver_id=driver_id
            )
        elif data.notification_type == "driver_on_the_way":
            result = notification_service.notify_driver_status_change(
                request_id=request_id,
                status="ON_THE_WAY",
                estimated_time=estimated_time
            )
        elif data.notification_type == "driver_arrived":
            result = notification_service.notify_driver_status_change(
                request_id=request_id,
                status="ARRIVED"
            )
        elif data.notification_type == "trip_started":
            result = notification_service.notify_driver_status_change(
                request_id=request_id,
                status="TRAVELLING"
            )
        elif data.notification_type == "trip_finished":
            result = notification_service.notify_driver_status_change(
                request_id=request_id,
                status="FINISHED"
            )
        elif data.notification_type == "trip_cancelled_by_driver":
            result = notification_service.notify_trip_cancelled_by_driver(
                request_id=request_id,
                reason=data.reason
            )
        elif data.notification_type == "trip_assigned":
            result = notification_service.notify_trip_assigned(
                request_id=request_id,
                driver_id=driver_id
            )
        elif data.notification_type == "trip_cancelled_by_client":
            result = notification_service.notify_trip_cancelled_by_client(
                request_id=request_id,
                driver_id=driver_id
            )
        elif data.notification_type == "payment_received":
            result = notification_service.notify_payment_received(
                request_id=request_id,
                driver_id=driver_id,
                amount=fare
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de notificación '{data.notification_type}' no válido"
            )

        return {
            "detail": f"Notificación de prueba '{data.notification_type}' enviada",
            "notification_type": data.notification_type,
            "result": result
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error enviando notificación de prueba: {str(e)}"
        )
