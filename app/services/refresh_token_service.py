import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID, uuid4
from fastapi import HTTPException, status
from sqlmodel import Session, select
from jose import jwt, JWTError
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.core.config import settings


class RefreshTokenService:
    def __init__(self, session: Session):
        self.session = session

    def generate_refresh_token(self, user_id: UUID, user_agent: Optional[str] = None, ip_address: Optional[str] = None) -> tuple[str, RefreshToken]:
        """
        Genera un nuevo refresh token para un usuario
        Returns: (token_plain, refresh_token_record)
        """
        # Generar token aleatorio seguro
        token_plain = secrets.token_urlsafe(64)

        # Crear hash del token para almacenar en BD
        token_hash = hashlib.sha256(token_plain.encode()).hexdigest()

        # Calcular fecha de expiración
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        # Crear registro en BD
        refresh_token = RefreshToken(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address
        )

        self.session.add(refresh_token)
        self.session.commit()
        self.session.refresh(refresh_token)

        return token_plain, refresh_token

    def validate_refresh_token(self, token: str) -> Optional[RefreshToken]:
        """
        Valida un refresh token y retorna el registro si es válido
        """
        # Crear hash del token recibido
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Buscar el token en BD
        refresh_token = self.session.exec(
            select(RefreshToken)
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.expires_at > datetime.utcnow(),
                RefreshToken.is_revoked == False
            )
        ).first()

        return refresh_token

    def revoke_refresh_token(self, token: str) -> bool:
        """
        Revoca un refresh token específico
        """
        refresh_token = self.validate_refresh_token(token)
        if not refresh_token:
            return False

        refresh_token.is_revoked = True
        refresh_token.updated_at = datetime.utcnow()
        self.session.add(refresh_token)
        self.session.commit()

        return True

    def revoke_all_user_tokens(self, user_id: UUID) -> int:
        """
        Revoca todos los refresh tokens de un usuario
        Returns: número de tokens revocados
        """
        result = self.session.exec(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False
            )
        ).all()

        count = 0
        for token in result:
            token.is_revoked = True
            token.updated_at = datetime.utcnow()
            self.session.add(token)
            count += 1

        self.session.commit()
        return count

    def get_user_active_tokens(self, user_id: UUID) -> List[RefreshToken]:
        """
        Obtiene todos los refresh tokens activos de un usuario
        """
        return self.session.exec(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.expires_at > datetime.utcnow(),
                RefreshToken.is_revoked == False
            )
            .order_by(RefreshToken.created_at.desc())
        ).all()

    def cleanup_expired_tokens(self) -> int:
        """
        Elimina tokens expirados de la base de datos
        Returns: número de tokens eliminados
        """
        expired_tokens = self.session.exec(
            select(RefreshToken)
            .where(RefreshToken.expires_at <= datetime.utcnow())
        ).all()

        count = len(expired_tokens)
        for token in expired_tokens:
            self.session.delete(token)

        self.session.commit()
        return count

    def create_access_token_from_refresh(self, refresh_token: RefreshToken) -> str:
        """
        Crea un nuevo access token a partir de un refresh token válido
        """
        # Verificar que el usuario existe
        user = self.session.get(User, refresh_token.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Crear payload para el access token
        to_encode = {
            "sub": str(user.id),
            "type": "access"
        }

        # Calcular expiración
        expires_delta = timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES_NEW)
        expire = datetime.utcnow() + expires_delta
        to_encode.update({"exp": expire})

        # Generar JWT
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )

        return encoded_jwt

    def rotate_refresh_token(self, old_token: str, user_agent: Optional[str] = None, ip_address: Optional[str] = None) -> tuple[str, str]:
        """
        Rota un refresh token (crea uno nuevo y revoca el anterior)
        Returns: (new_access_token, new_refresh_token)
        """
        # Validar token actual
        old_refresh_token = self.validate_refresh_token(old_token)
        if not old_refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        # Crear nuevo access token
        new_access_token = self.create_access_token_from_refresh(
            old_refresh_token)

        # Crear nuevo refresh token si la rotación está habilitada
        if settings.REFRESH_TOKEN_ROTATION:
            new_refresh_token_plain, new_refresh_token_record = self.generate_refresh_token(
                old_refresh_token.user_id,
                user_agent,
                ip_address
            )

            # Revocar el token anterior
            self.revoke_refresh_token(old_token)

            return new_access_token, new_refresh_token_plain
        else:
            # Sin rotación, solo retornar el access token
            return new_access_token, old_token
