from fastapi import Request, HTTPException, status, Path
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.core.config import settings
from app.core.db import SessionDep
from app.models.user import User
from app.models.administrador import AdminRole
from sqlmodel import select
from uuid import UUID

bearer_scheme = HTTPBearer()


def user_is_owner():
    def dependency(
        user_id: int = Path(...),  # FastAPI inyecta el parámetro de la ruta
        request: Request = None
    ):
        if request.state.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para acceder a este recurso"
            )
    return dependency


def get_current_user(request: Request, session: SessionDep, credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autorizado como usuario",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise credentials_exception

        # Establecer el user_id en el estado de la solicitud
        request.state.user_id = UUID(user_id)

        role = payload.get("role")
        if role == AdminRole.BASIC.value:  # Si es admin, no permitir acceso
            raise credentials_exception

        # Obtener el usuario real desde la base de datos
        user = session.exec(select(User).where(
            User.id == UUID(user_id))).first()
        if not user:
            raise credentials_exception

        return user
    except JWTError:
        raise credentials_exception
