from sqlmodel import Session, select
from app.models.user import User, UserCreate, UserUpdate, UserRead
from app.models.role import Role
from app.models.user_has_roles import UserHasRole, RoleStatus
from app.models.referral_chain import Referral
from typing import List, Optional
from fastapi import HTTPException, status, UploadFile
from sqlalchemy.orm import selectinload
from datetime import datetime
import os
from app.core.config import settings
import uuid
from uuid import UUID
from app.models.verify_mount import VerifyMount
from phonenumbers.phonenumberutil import NumberParseException
import phonenumbers


class UserService:
    def __init__(self, session: Session):
        self.session = session

    def create_user(self, user_data: UserCreate) -> User:
        # Validación personalizada de número de teléfono colombiano
        full_number = f"{user_data.country_code}{user_data.phone_number}"
        try:
            parsed = phonenumbers.parse(full_number, None)
            if phonenumbers.region_code_for_number(parsed) != "CO":
                raise ValueError("El número debe ser colombiano (+57).")
            if not str(parsed.national_number).startswith("3"):
                raise ValueError(
                    "El número móvil colombiano debe empezar con 3.")
            # Validar prefijo válido (300-399)
            prefix = int(str(parsed.national_number)[:3])
            if prefix < 300 or prefix > 399:
                raise ValueError(
                    "El prefijo del número móvil colombiano no es válido (debe estar entre 300 y 399).")
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError("El número de teléfono no es válido.")
        except NumberParseException as e:
            if e.error_type == NumberParseException.INVALID_COUNTRY_CODE:
                raise ValueError(
                    "Código de país inválido. Usa +57 para Colombia.")
            elif e.error_type == NumberParseException.NOT_A_NUMBER:
                raise ValueError(
                    "El valor ingresado no es un número de teléfono.")
            elif e.error_type == NumberParseException.TOO_SHORT_NSN:
                raise ValueError("El número es demasiado corto para Colombia.")
            elif e.error_type == NumberParseException.TOO_LONG:
                raise ValueError("El número es demasiado largo para Colombia.")
            else:
                raise ValueError("Número de teléfono inválido.")

        with self.session.begin():
            # Check for existing phone (country_code + phone_number)
            existing_user = self.session.exec(
                select(User).where(
                    User.country_code == user_data.country_code,
                    User.phone_number == user_data.phone_number
                )
            ).first()

            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User with this phone number already exists."
                )

            user = User.model_validate(user_data.model_dump())
            self.session.add(user)
            self.session.flush()  # Para obtener el id antes del commit

            # Asignar el rol CLIENT por defecto
            client_role = self.session.exec(
                select(Role).where(Role.id == "CLIENT")).first()
            if not client_role:
                raise HTTPException(
                    status_code=500, detail="Rol CLIENT no existe")

            # La relación se crea automáticamente a través del link_model
            user.roles.append(client_role)

            # Si hay un  referido, validarlo y crear la relación de referido
            if user_data.referral_phone:
                referral_user = self.session.exec(
                    select(User).where(
                        User.phone_number == user_data.referral_phone
                    )
                ).first()
                if referral_user:
                    referral = Referral(
                        user_id=user.id, referred_by_id=referral_user.id)
                    self.session.add(referral)

            # Actualizar el estado de la relación a través del link_model
            user_role = self.session.exec(
                select(UserHasRole).where(
                    UserHasRole.id_user == user.id,
                    UserHasRole.id_rol == client_role.id
                )
            ).first()
            if user_role:
                user_role.is_verified = True
                user_role.status = RoleStatus.APPROVED
                user_role.verified_at = datetime.utcnow()
                self.session.add(user_role)

            self.session.add(user)
            # El commit se hace automáticamente al salir del with

            # Crear VerifyMount con mount=0 si no existe
            verify_mount = self.session.exec(
                select(VerifyMount).where(VerifyMount.user_id == user.id)
            ).first()
            if not verify_mount:
                verify_mount = VerifyMount(user_id=user.id, mount=0)
                self.session.add(verify_mount)

        return user

    def _save_user_selfie(self, uploader, user_id: UUID, selfie: UploadFile):
        """Guarda la selfie en static/uploads/users/{user_id}/selfie_<uuid>.jpg"""
        selfie_dir = os.path.join("static", "uploads", "users", str(user_id))
        os.makedirs(selfie_dir, exist_ok=True)
        ext = os.path.splitext(selfie.filename)[1] or ".jpg"
        unique_name = f"selfie_{uuid.uuid4().hex}{ext}"
        selfie_path = os.path.join(selfie_dir, unique_name)
        with open(selfie_path, "wb") as f:
            f.write(selfie.file.read())
        url = f"{settings.STATIC_URL_PREFIX}/users/{user_id}/{unique_name}"
        return {"url": url}

    def get_users(self) -> list[User]:
        return self.session.exec(select(User)).all()

    def get_user(self, user_id: UUID) -> User:
        # Cargar el usuario con sus relaciones
        user = self.session.exec(
            select(User)
            .options(selectinload(User.roles), selectinload(User.driver_info))
            .where(User.id == user_id)
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        # Consultar si el usuario tiene el rol DRIVER aprobado
        driver_role = self.session.exec(
            select(UserHasRole).where(
                UserHasRole.id_user == user_id,
                UserHasRole.id_rol == "DRIVER",
                UserHasRole.status == RoleStatus.APPROVED
            )
        ).first()

        # También consultar si tiene rol DRIVER (aprobado o no)
        has_driver_role = self.session.exec(
            select(UserHasRole).where(
                UserHasRole.id_user == user_id,
                UserHasRole.id_rol == "DRIVER"
            )
        ).first()

        # Construir manualmente el diccionario con todos los campos necesarios
        user_dict = {
            "id": user.id,
            "country_code": user.country_code,
            "phone_number": user.phone_number,
            "is_verified_phone": user.is_verified_phone,
            "is_active": user.is_active,
            "full_name": user.full_name,
            "selfie_url": user.selfie_url,
            "roles": user.roles,  # Incluir los roles cargados
            "driver_info": user.driver_info,  # Incluir driver_info cargado
            "is_driver_approved": bool(driver_role) if has_driver_role else None
        }

        # Usar UserRead para la respuesta
        return UserRead.model_validate(user_dict, from_attributes=True)

    def update_user(self, user_id: UUID, user_data: UserUpdate) -> User:
        user = self.get_user(user_id)
        user_data_dict = user_data.model_dump(exclude_unset=True)
        user.sqlmodel_update(user_data_dict)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def delete_user(self, user_id: UUID) -> dict:
        user = self.get_user(user_id)
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already inactive."
            )
        user.is_active = False
        self.session.add(user)
        self.session.commit()
        return {"message": "User deactivated (soft deleted) successfully"}

    def verify_user(self, user_id: UUID) -> User:
        user = self.get_user(user_id)
        if user.is_verified_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already verified."
            )
        user.is_verified_phone = True
        user.is_active = True
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def update_selfie(self, user_id: UUID, selfie: UploadFile):
        user = self.get_user(user_id)
        selfie_info = self._save_user_selfie(None, user.id, selfie)
        user.selfie_url = selfie_info["url"]
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return {"selfie_url": user.selfie_url}
