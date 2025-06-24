from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session
from app.core.db import SessionDep
from app.core.dependencies.auth import get_current_user
from app.services.user_fcm_token_service import UserFCMTokenService
from app.models.user_fcm_token import UserFCMToken
from app.models.user import User
from pydantic import BaseModel
from uuid import UUID
from typing import List, Optional

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
    last_used: Optional[str]
    created_at: str
    updated_at: str

# Esquema para respuesta de lista de tokens


class FCMTokenListResponse(BaseModel):
    tokens: List[FCMTokenResponse]


@router.post("/register", response_model=FCMTokenResponse, status_code=status.HTTP_201_CREATED)
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


@router.delete("/deactivate", status_code=status.HTTP_200_OK)
def deactivate_fcm_token(
    fcm_token: str,
    session: SessionDep = Depends(SessionDep),
    current_user: User = Depends(get_current_user)
):
    """Desactiva un token FCM específico del usuario autenticado."""
    service = UserFCMTokenService(session)
    success = service.deactivate_token(
        user_id=current_user.id, fcm_token=fcm_token)
    if not success:
        raise HTTPException(status_code=404, detail="Token FCM no encontrado")
    return {"detail": "Token FCM desactivado exitosamente"}


@router.get("/my-tokens", response_model=FCMTokenListResponse)
def get_my_fcm_tokens(
    session: SessionDep = Depends(SessionDep),
    current_user: User = Depends(get_current_user)
):
    """Obtiene todos los tokens FCM activos del usuario autenticado."""
    service = UserFCMTokenService(session)
    tokens = service.get_all_tokens(user_id=current_user.id)
    return FCMTokenListResponse(tokens=[FCMTokenResponse.model_validate(t, from_attributes=True) for t in tokens])


@router.post("/test-notification")
def send_test_notification(
    session: SessionDep = Depends(SessionDep),
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
