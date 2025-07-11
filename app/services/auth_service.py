import random
import httpx
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlmodel import Session, select
from ..models.w_verification import Verification, VerificationCreate
from ..models.user import User, VehicleTypeRead, VehicleInfoRead, UserRead, RoleRead, DriverInfoRead
from ..models.vehicle_info import VehicleInfo
from ..models.driver_info import DriverInfo
from ..models.user_has_roles import UserHasRole, RoleStatus
from ..core.config import settings
from jose import jwt
import clicksend_client
from clicksend_client import SmsMessage
from clicksend_client.rest import ApiException
from sqlalchemy.orm import joinedload
from uuid import UUID
from .refresh_token_service import RefreshTokenService


class AuthService:
    def __init__(self, session: Session):
        self.session = session

    def generate_verification_code(self) -> str:
        return ''.join(random.choices('0123456789', k=6))

    async def send_whatsapp_message(self, to_phone: str, message: str) -> bool:
        headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}",
            "Content-Type": "application/json"
        }

        # Extraer solo el código de verificación del mensaje
        verification_code = message.split(":")[1].split(".")[0].strip()

        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": "auth_log_99drive",
                "language": {
                    "code": "es_CO"
                },
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {
                                "type": "text",
                                "text": verification_code
                            }
                        ]
                    },
                    {
                        "type": "button",
                        "sub_type": "url",
                        "index": 0,
                        "parameters": [
                            {
                                "type": "text",
                                "text": verification_code  # O cualquier valor que la plantilla espera
                            }
                        ]
                    }
                ]
            }
        }
        print("saber que se envia:",
              f"{settings.WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_ID}/messages")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_ID}/messages",
                    headers=headers,
                    json=payload
                )
                print("Payload enviado:", payload)
                print("Respuesta de WhatsApp:",
                      response.status_code, response.text)
                response.raise_for_status()
                return True
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send WhatsApp message: {str(e)}"
            )

    async def create_verification(self, country_code: str, phone_number: str) -> tuple[Verification, str]:
        # Verificar usuario existente
        user = self.session.exec(
            select(User).where(
                User.country_code == country_code,
                User.phone_number == phone_number
            )
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Generar código y fecha de expiración
        verification_code = self.generate_verification_code()
        expires_at = datetime.utcnow(
        ) + timedelta(minutes=settings.VERIFICATION_CODE_EXPIRY_MINUTES)

        # Buscar si ya existe una verificación para este usuario
        existing_verification = self.session.exec(
            select(Verification).where(Verification.user_id == user.id)
        ).first()

        if existing_verification:
            # Actualizar el registro existente
            existing_verification.is_verified = False
            existing_verification.verification_code = verification_code
            existing_verification.expires_at = expires_at
            existing_verification.attempts = 0
            self.session.add(existing_verification)
            self.session.commit()
            self.session.refresh(existing_verification)
            verif = existing_verification
        else:
            # Crear la nueva verificación
            verif = Verification(
                user_id=user.id,
                verification_code=verification_code,
                expires_at=expires_at,
                is_verified=False
            )
            self.session.add(verif)
            self.session.commit()
            self.session.refresh(verif)

        try:
            # Enviar mensaje WhatsApp   message = f"Your verification code is: {verification_code}. This code will expire in {settings.VERIFICATION_CODE_EXPIRY_MINUTES} minutes."

            full_phone = f"{country_code}{phone_number}"
            message = f"code is: {verification_code}. "

            # await self.send_whatsapp_message(full_phone, message)
            # await self.generate_mns_verification(full_phone, message)

            return verif, verification_code
        except Exception as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Your verification code is: {verification_code}. This code will expire in {settings.VERIFICATION_CODE_EXPIRY_MINUTES} minutes."
            )

    def verify_code(self, country_code: str, phone_number: str, code: str, user_agent: str = None, ip_address: str = None) -> tuple[bool, str, str, UserRead]:
        """
        Verifica el código y retorna tokens + datos del usuario
        Returns: (success, access_token, refresh_token, user_data)
        """
        # Buscar el usuario primero
        user = self.session.exec(
            select(User).where(
                User.country_code == country_code,
                User.phone_number == phone_number
            )
        ).first()

        if not user:  # retirna si el telefono y pais no corresponde
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        verification = self.session.exec(  # busca codigo  si el tiempo de ducracion no a expirado
            select(Verification)
            .where(
                Verification.user_id == user.id,
                Verification.expires_at > datetime.utcnow(),
                Verification.is_verified == False
            )
        ).first()

        if not verification:  # si el tiempo expiró verificacion esta vacio
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active verification found"
            )

        if verification.attempts >= settings.MAX_VERIFICATION_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum verification attempts exceeded"
            )

        verification.attempts += 1

        if verification.verification_code != code:
            self.session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code"
            )

        verification.is_verified = True
        self.session.commit()

        # Aprobar automáticamente el rol CLIENT si está en PENDING
        client_role = self.session.exec(
            select(UserHasRole).where(
                UserHasRole.id_user == user.id,
                UserHasRole.id_rol == "CLIENT"
            )
        ).first()
        if client_role:
            if client_role.status == RoleStatus.PENDING:
                client_role.status = RoleStatus.APPROVED
            if client_role.status == RoleStatus.APPROVED:
                client_role.is_verified = True
            self.session.add(client_role)
            self.session.commit()

        # Actualizar estado de verificación del usuario
        if not user.is_verified_phone:
            user.is_verified_phone = True
        if not user.is_active:
            user.is_active = True

        self.session.commit()

        # Generar tokens (access token + refresh token)
        access_token, refresh_token = self.create_tokens_pair(
            user.id, user_agent, ip_address)

        # Preparar datos de vehículo y driver_info (si aplica)
        vehicle_info_data = None
        driver_info_data = None
        is_driver = any(role.id == "DRIVER" for role in user.roles)

        if is_driver:
            driver_info = self.session.exec(
                select(DriverInfo).where(DriverInfo.user_id == user.id)
            ).first()

            if driver_info:
                # DriverInfo
                driver_info_data = DriverInfoRead.model_validate(
                    driver_info, from_attributes=True)

                # VehicleInfo
                vehicle_info = self.session.exec(
                    select(VehicleInfo)
                    .where(VehicleInfo.driver_info_id == driver_info.id)
                    .options(joinedload(VehicleInfo.vehicle_type))
                ).first()

                if vehicle_info:
                    vehicle_type_data = None
                    if vehicle_info.vehicle_type:
                        vehicle_type_data = VehicleTypeRead.model_validate(
                            vehicle_info.vehicle_type, from_attributes=True)
                    vehicle_info_data = VehicleInfoRead.model_validate(
                        vehicle_info, from_attributes=True)
                    vehicle_info_data.vehicle_type = vehicle_type_data

        # Convertir roles a RoleRead
        roles_data = [RoleRead.model_validate(
            role, from_attributes=True) for role in user.roles]

        # Calcular is_driver_approved
        driver_role_approved = self.session.exec(
            select(UserHasRole).where(
                UserHasRole.id_user == user.id,
                UserHasRole.id_rol == "DRIVER",
                UserHasRole.status == RoleStatus.APPROVED
            )
        ).first()

        has_driver_role = self.session.exec(
            select(UserHasRole).where(
                UserHasRole.id_user == user.id,
                UserHasRole.id_rol == "DRIVER"
            )
        ).first()

        is_driver_approved = bool(
            driver_role_approved) if has_driver_role and driver_role_approved else False

        # Construir el usuario de respuesta
        user_data = UserRead(
            id=user.id,
            country_code=user.country_code,
            phone_number=user.phone_number,
            is_verified_phone=user.is_verified_phone,
            is_active=user.is_active,
            full_name=user.full_name,
            roles=roles_data,
            vehicle_info=vehicle_info_data,
            driver_info=driver_info_data,
            is_driver_approved=is_driver_approved
        )

        return True, access_token, refresh_token, user_data

    def create_access_token(self, user_id: UUID):
        to_encode = {"sub": str(user_id)}
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = datetime.utcnow() + expires_delta
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    def create_tokens_pair(self, user_id: UUID, user_agent: str = None, ip_address: str = None) -> tuple[str, str]:
        """
        Crea un par de tokens (access token + refresh token)
        Returns: (access_token, refresh_token)
        """
        # Crear access token
        access_token = self.create_access_token(user_id)

        # Crear refresh token
        refresh_token_service = RefreshTokenService(self.session)
        refresh_token_plain, _ = refresh_token_service.generate_refresh_token(
            user_id, user_agent, ip_address
        )

        return access_token, refresh_token_plain

    def refresh_access_token(self, refresh_token: str, user_agent: str = None, ip_address: str = None) -> tuple[str, str]:
        """
        Renueva un access token usando un refresh token válido
        Returns: (new_access_token, new_refresh_token)
        """
        refresh_token_service = RefreshTokenService(self.session)
        return refresh_token_service.rotate_refresh_token(refresh_token, user_agent, ip_address)

    def revoke_refresh_token(self, refresh_token: str) -> bool:
        """
        Revoca un refresh token específico
        """
        refresh_token_service = RefreshTokenService(self.session)
        return refresh_token_service.revoke_refresh_token(refresh_token)

    def revoke_all_user_tokens(self, user_id: UUID) -> int:
        """
        Revoca todos los refresh tokens de un usuario
        """
        refresh_token_service = RefreshTokenService(self.session)
        return refresh_token_service.revoke_all_user_tokens(user_id)

    async def generate_mns_verification(self, to_phone: str, message: str) -> dict:
        try:
            # Asegurarse de que el número tenga el formato correcto
            if not to_phone.startswith('+'):
                to_phone = f'+{to_phone}'

            configuration = clicksend_client.Configuration()
            configuration.username = settings.CLICK_SEND_USERNAME
            configuration.password = settings.CLICK_SEND_PASSWORD

            # Crear instancia de la API     para instalar pip install clicksend-client
            api_instance = clicksend_client.SMSApi(
                clicksend_client.ApiClient(configuration))

            message_list = {
                "messages": [
                    {
                        "source": "milla99",
                        "body": message,
                        "to": to_phone,
                        "from": settings.CLICK_SEND_PHONE
                    }
                ]
            }

            # Enviar mensaje
            api_response = api_instance.sms_send_post(message_list)
            print(str(api_response))

        except Exception as e:
            print(f"Error sending SMS: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send SMS: {str(e)}"
            )
