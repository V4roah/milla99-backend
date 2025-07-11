from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.core.config import settings
from app.models.administrador import Administrador, AdminRole
from app.core.db import SessionDep
from typing import Optional
from uuid import UUID

bearer_scheme = HTTPBearer()


def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autorizado como administrador",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        role = payload.get("role")
        if role not in [AdminRole.BASIC.value, AdminRole.SYSTEM.value, AdminRole.SUPER.value]:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return payload


def get_current_admin_user(session: SessionDep, credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Obtener el administrador actual como objeto Administrador"""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autorizado como administrador",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        user_id_str = payload.get("sub")
        role = payload.get("role")

        if not user_id_str or role not in [AdminRole.BASIC.value, AdminRole.SYSTEM.value, AdminRole.SUPER.value]:
            raise credentials_exception

        # Convertir string a UUID
        user_id = UUID(user_id_str)

        # Buscar el administrador en la base de datos
        admin = session.get(Administrador, user_id)
        if not admin:
            raise credentials_exception

        return admin
    except (JWTError, ValueError) as e:
        raise credentials_exception


def get_current_super_admin(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Verifica que el admin tenga role 3 (Super Admin)"""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Se requiere permisos de Super Administrador",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        role = payload.get("role")
        if role != AdminRole.SUPER.value:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return payload


def get_current_system_admin(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Verifica que el admin tenga role 2 o 3 (System Admin o Super Admin)"""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Se requiere permisos de Administrador del Sistema o Super Administrador",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        role = payload.get("role")
        if role not in [AdminRole.SYSTEM.value, AdminRole.SUPER.value]:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return payload


def get_admin_with_minimum_role(minimum_role: AdminRole):
    """Factory function para crear dependencias que requieren un role mínimo"""
    def get_admin_with_role(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
        token = credentials.credentials
        credentials_exception = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Se requiere role mínimo {minimum_role.name}",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, settings.SECRET_KEY,
                                 algorithms=[settings.ALGORITHM])
            role = payload.get("role")
            if role < minimum_role.value:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
        return payload
    return get_admin_with_role
