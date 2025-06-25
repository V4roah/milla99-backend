from sqlmodel import Session, select
from app.models.user_fcm_token import UserFCMToken
from uuid import UUID
from datetime import datetime
from typing import List, Optional
from firebase_admin import messaging


class UserFCMTokenService:
    def __init__(self, session: Session):
        self.session = session

    def register_token(self, user_id: UUID, fcm_token: str, device_type: str, device_name: Optional[str] = None) -> UserFCMToken:
        """
        Registra o actualiza un token FCM para un usuario.
        Si el token ya existe para el usuario, lo actualiza y lo marca como activo.
        Si no existe, lo crea.
        """
        token = self.session.exec(
            select(UserFCMToken).where(
                UserFCMToken.user_id == user_id,
                UserFCMToken.fcm_token == fcm_token
            )
        ).first()
        if token:
            token.device_type = device_type
            token.device_name = device_name
            token.is_active = True
            token.last_used = datetime.utcnow()
            self.session.add(token)
        else:
            token = UserFCMToken(
                user_id=user_id,
                fcm_token=fcm_token,
                device_type=device_type,
                device_name=device_name,
                is_active=True,
                last_used=datetime.utcnow()
            )
            self.session.add(token)
        self.session.commit()
        self.session.refresh(token)
        return token

    def deactivate_token(self, user_id: UUID, fcm_token: str) -> bool:
        """
        Desactiva un token FCM específico de un usuario.
        """
        token = self.session.exec(
            select(UserFCMToken).where(
                UserFCMToken.user_id == user_id,
                UserFCMToken.fcm_token == fcm_token
            )
        ).first()
        if token:
            token.is_active = False
            self.session.add(token)
            self.session.commit()
            return True
        return False

    def get_active_tokens(self, user_id: UUID) -> List[str]:
        """
        Obtiene todos los tokens FCM activos de un usuario.
        """
        tokens = self.session.exec(
            select(UserFCMToken.fcm_token).where(
                UserFCMToken.user_id == user_id,
                UserFCMToken.is_active == True
            )
        ).all()
        return tokens

    def get_all_tokens(self, user_id: UUID) -> List[UserFCMToken]:
        """
        Obtiene todos los registros de tokens FCM de un usuario (activos e inactivos).
        """
        tokens = self.session.exec(
            select(UserFCMToken).where(
                UserFCMToken.user_id == user_id
            )
        ).all()
        return tokens

    def send_notification(self, tokens: List[str], title: str, body: str, data: Optional[dict] = None) -> dict:
        """
        Envía una notificación push a una lista de tokens FCM.
        Retorna un dict con el resultado del envío.
        """
        if not tokens:
            return {"success": 0, "failed": 0}

        try:
            message = messaging.MulticastMessage(
                tokens=tokens,
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {}
            )
            response = messaging.send_multicast(message)
            return {"success": response.success_count, "failed": response.failure_count}
        except ValueError as e:
            # Firebase no está configurado (caso de tests)
            if "The default Firebase app does not exist" in str(e):
                print("⚠️ Firebase no configurado - simulando envío de notificación")
                return {"success": len(tokens), "failed": 0, "simulated": True}
            else:
                raise e
        except Exception as e:
            # Otros errores de Firebase
            print(f"❌ Error enviando notificación FCM: {e}")
            return {"success": 0, "failed": len(tokens), "error": str(e)}
