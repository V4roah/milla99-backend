from fastapi import APIRouter, Depends, status, HTTPException, Request
from ..core.db import SessionDep
from ..services.auth_service import AuthService
from pydantic import BaseModel
from app.models.user import UserRead
from app.core.dependencies.auth import get_current_user
import logging


router = APIRouter(prefix="/auth", tags=["auth"])

# Crear un router con prefijo '/whatsapp' y etiqueta para la documentación


# Modelo para la solicitud de verificación (cuando el usuario envía el código)
class VerificationRequest(BaseModel):
    code: str


# Endpoint para enviar el código de verificación
class VerifResponseCode(BaseModel):
    message: str
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
    user: UserRead | None = None


# Endpoint para enviar el código de verificación
class VerificationResponse(BaseModel):
    message: str


class SMSMessage(BaseModel):
    phone_number: str
    message: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str


@router.post(
    "/verify/{country_code}/{phone_number}/send",
    response_model=VerificationResponse,
    status_code=status.HTTP_201_CREATED,
    description="""
Envía un código de verificación vía WhatsApp al número de teléfono proporcionado.

**Parámetros:**
- `country_code`: Código de país del usuario.
- `phone_number`: Número de teléfono del usuario.

**Respuesta:**
Devuelve un mensaje indicando que el código de verificación fue enviado exitosamente.
"""
)
# ID del usuario que se va a verificar, Sesión de base de datos (inyectada automáticamente)
async def send_verification(country_code: str, phone_number: str, session: SessionDep):
    """Send verification code via WhatsApp"""
    service = AuthService(
        session)                                          # Crear una instancia del servicio
    # Llamar al método para crear y enviar la verificación
    verification, codigo = await service.create_verification(country_code, phone_number)
    # Retornar mensaje de éxito
    return VerificationResponse(message=f"Verification code sent successfully {codigo}")


@router.post(
    "/verify/{country_code}/{phone_number}/code",
    response_model=VerifResponseCode,
    description="""
Verifica el código recibido vía WhatsApp para el número de teléfono proporcionado.

**Parámetros:**
- `country_code`: Código de país del usuario.
- `phone_number`: Número de teléfono del usuario.
- `code`: Código de verificación recibido por el usuario.

**Respuesta:**
Devuelve un mensaje indicando si la verificación fue exitosa, junto con el token de acceso y la información del usuario si aplica.
"""
)
async def verify_code(
    country_code: str,
    phone_number: str,                                   # ID del usuario
    # Datos de la solicitud (el código)
    verification: VerificationRequest,
    session: SessionDep                             # Sesión de base de datos
):
    """Verify the code sent via WhatsApp"""
    service = AuthService(session)  # crear instancia del servicio
    try:
        result, access_token, refresh_token, user = service.verify_code(
            country_code, phone_number, verification.code)
        return VerifResponseCode(
            message="Code verified successfully",
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=UserRead.model_validate(user, from_attributes=True)
        )
    except HTTPException as e:
        # Errores esperados (usuario no encontrado, código inválido, etc.)
        raise e
    except Exception as e:
        # Loguear el error inesperado
        logging.exception("Unexpected error verifying code")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(
    data: RefreshTokenRequest,
    request: Request,
    session: SessionDep
):
    """Renueva el access token usando un refresh token válido."""
    service = AuthService(session)
    try:
        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host if request.client else None
        access_token, new_refresh_token = service.refresh_access_token(
            data.refresh_token, user_agent, ip_address
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.exception("Unexpected error refreshing token")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/logout", response_model=MessageResponse)
async def logout_endpoint(
    data: RefreshTokenRequest,
    session: SessionDep
):
    """Revoca el refresh token actual."""
    service = AuthService(session)
    revoked = service.revoke_refresh_token(data.refresh_token)
    if revoked:
        return MessageResponse(message="Refresh token revoked")
    else:
        raise HTTPException(
            status_code=400, detail="Invalid or already revoked refresh token")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all_endpoint(
    current_user=Depends(get_current_user),
    session: SessionDep = Depends()
):
    """Revoca todos los refresh tokens del usuario autenticado."""
    service = AuthService(session)
    count = service.revoke_all_user_tokens(current_user.id)
    return MessageResponse(message=f"Revoked {count} refresh tokens for user.")
