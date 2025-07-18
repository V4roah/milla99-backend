from sqlmodel import Session, select
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException
from app.models.bank_account import (
    BankAccount, BankAccountCreate, BankAccountRead, AccountType
)
from app.models.user import User
from app.models.user_has_roles import UserHasRole, RoleStatus
from datetime import datetime, timedelta
from app.utils.encryption import encryption_service
import traceback


class BankAccountService:
    def __init__(self, session: Session):
        self.session = session

    def verify_user_role(self, user_id: UUID) -> None:
        """
        Verifica que el usuario tenga el rol de CLIENT o DRIVER aprobado.
        """
        user_role = self.session.query(UserHasRole).filter(
            UserHasRole.id_user == user_id,
            UserHasRole.id_rol.in_(["CLIENT", "DRIVER"]),
            UserHasRole.status == RoleStatus.APPROVED
        ).first()
        if not user_role:
            raise HTTPException(
                status_code=403,
                detail="Solo los usuarios aprobados (clientes o conductores) pueden gestionar cuentas bancarias"
            )

    def create_bank_account(self, user_id: UUID, bank_account_data: BankAccountCreate) -> BankAccount:
        """
        Crea una nueva cuenta bancaria para un usuario.
        Valida que el usuario tenga el rol apropiado, que no exista una cuenta idéntica y que los datos sean válidos.
        """
        # Verificar rol del usuario
        self.verify_user_role(user_id)

        # Verificar que el usuario existe
        user = self.session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Limitar a 3 cuentas bancarias por usuario
        count_accounts = self.session.query(BankAccount).filter(
            BankAccount.user_id == user_id,
            BankAccount.is_active == True
        ).count()
        if count_accounts >= 3:
            raise HTTPException(
                status_code=400,
                detail="Solo puede tener hasta 3 cuentas bancarias activas. Desactive una existente para agregar otra."
            )

        # Verificar que no existe una cuenta idéntica para el mismo usuario, banco, tipo de cuenta y número de cuenta
        existing_account = self.session.query(BankAccount).filter(
            BankAccount.user_id == user_id,
            BankAccount.bank_id == bank_account_data.bank_id,
            BankAccount.account_type == bank_account_data.account_type,
            BankAccount.account_number == bank_account_data.account_number
        ).first()
        if existing_account:
            raise HTTPException(
                status_code=400,
                detail="A bank account with these details already exists"
            )

        # Encriptar datos sensibles
        bank_account_data.encrypt_sensitive_data()

        # Crear la cuenta bancaria
        bank_account = BankAccount(
            user_id=user_id,
            **bank_account_data.dict()
        )
        self.session.add(bank_account)
        self.session.commit()
        self.session.refresh(bank_account)
        return bank_account

    def get_bank_accounts(self, user_id: UUID) -> List[BankAccountRead]:
        """
        Obtiene todas las cuentas bancarias activas de un usuario.
        Verifica que el usuario tenga el rol apropiado.
        Los datos sensibles se devuelven enmascarados.
        """
        # Verificar rol del usuario
        self.verify_user_role(user_id)

        accounts = self.session.query(BankAccount).filter(
            BankAccount.user_id == user_id,
            BankAccount.is_active == True
        ).all()
        return [BankAccountRead.from_orm(account) for account in accounts]

    def get_bank_account(self, user_id: UUID, account_id: UUID) -> BankAccount:
        bank_account = (
            self.session.query(BankAccount)
            .filter(BankAccount.id == account_id, BankAccount.user_id == user_id)
            .first()
        )
        if not bank_account:
            raise HTTPException(
                status_code=404, detail="Bank account not found")
        return bank_account

    def update_bank_account(
        self,
        user_id: UUID,
        account_id: UUID,
        update_data: dict
    ) -> BankAccountRead:
        """
        Actualiza una cuenta bancaria.
        Verifica que el usuario tenga el rol apropiado.
        No permite modificar campos sensibles como user_id o is_verified.
        """
        try:
            print(
                f"Service: update_bank_account called with user_id={user_id}, account_id={account_id}")
            print(f"Service: update_data={update_data}")

            # Verificar rol del usuario
            self.verify_user_role(user_id)

            bank_account = self.session.get(BankAccount, account_id)
            print(f"Service: bank_account found: {bank_account is not None}")

            if not bank_account:
                print(f"Service: Bank account not found with ID {account_id}")
                raise HTTPException(
                    status_code=404, detail="Bank account not found")

            if bank_account.user_id != user_id:
                print(
                    f"Service: Bank account belongs to {bank_account.user_id}, not {user_id}")
                raise HTTPException(
                    status_code=403, detail="Not authorized to access this bank account")

            # Verificar si hay retiros pendientes
            from app.models.withdrawal import Withdrawal, WithdrawalStatus
            pending_withdrawals = self.session.query(Withdrawal).filter(
                Withdrawal.bank_account_id == account_id,
                Withdrawal.status == WithdrawalStatus.PENDING
            ).first()

            if pending_withdrawals:
                print(f"Service: Bank account has pending withdrawals")
                raise HTTPException(
                    status_code=400,
                    detail="Cannot update bank account with pending withdrawals"
                )

            # Campos que no se pueden modificar
            protected_fields = {
                "id", "user_id", "created_at", "verification_date"
            }
            for field in protected_fields:
                update_data.pop(field, None)

            print(f"Service: After removing protected fields: {update_data}")

            # Si se modifica el número de cuenta, requiere re-verificación y encriptación
            if "account_number" in update_data:
                print(f"Service: Encrypting account_number")
                update_data["account_number"] = encryption_service.encrypt(
                    update_data["account_number"])
                update_data["verification_date"] = None

            # Si se modifica la cédula, requiere encriptación
            if "identification_number" in update_data:
                print(f"Service: Encrypting identification_number")
                update_data["identification_number"] = encryption_service.encrypt(
                    update_data["identification_number"])

            # Actualizar campos
            print(f"Service: Updating fields: {list(update_data.keys())}")
            for key, value in update_data.items():
                print(f"Service: Setting {key}={value}")
                setattr(bank_account, key, value)

            bank_account.updated_at = datetime.utcnow()
            self.session.add(bank_account)
            self.session.commit()
            self.session.refresh(bank_account)

            print(f"Service: Bank account updated successfully")
            return BankAccountRead.from_orm(bank_account)
        except Exception as e:
            print(f"Service Error: {str(e)}")
            print(traceback.format_exc())
            raise

    def delete_bank_account(self, user_id: UUID, account_id: UUID) -> dict:
        """
        Elimina (desactiva) una cuenta bancaria.
        Verifica que el usuario tenga el rol apropiado.
        No permite eliminar si hay retiros pendientes o recientes.
        """
        # Verificar rol del usuario
        self.verify_user_role(user_id)

        bank_account = self.get_bank_account(user_id, account_id)

        # Verificar si hay retiros pendientes o recientes
        from app.models.withdrawal import Withdrawal, WithdrawalStatus
        recent_withdrawals = self.session.query(Withdrawal).filter(
            Withdrawal.bank_account_id == account_id,
            Withdrawal.withdrawal_date >= datetime.utcnow() - timedelta(days=30)
        ).first()
        if recent_withdrawals:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete bank account with recent or pending withdrawals"
            )

        # En lugar de eliminar, desactivamos la cuenta
        bank_account.is_active = False
        bank_account.updated_at = datetime.utcnow()
        self.session.add(bank_account)
        self.session.commit()
        return {"message": "Bank account deactivated successfully"}

    def verify_bank_account(self, account_id: UUID) -> BankAccount:
        """
        Marca una cuenta bancaria como verificada.
        Solo para uso administrativo.
        """
        bank_account = self.session.get(BankAccount, account_id)
        if not bank_account:
            raise HTTPException(
                status_code=404, detail="Bank account not found")

        bank_account.verification_date = datetime.utcnow()
        bank_account.updated_at = datetime.utcnow()
        self.session.add(bank_account)
        self.session.commit()
        self.session.refresh(bank_account)
        return bank_account

    def get_active_bank_accounts(self, user_id: UUID) -> List[BankAccountRead]:
        """
        Obtiene solo las cuentas bancarias activas de un usuario.
        Verifica que el usuario tenga el rol apropiado.
        Los datos sensibles se devuelven enmascarados.
        """
        # Verificar rol del usuario
        self.verify_user_role(user_id)

        accounts = self.session.query(BankAccount).filter(
            BankAccount.user_id == user_id,
            BankAccount.is_active == True
        ).all()
        return [BankAccountRead.from_orm(account) for account in accounts]

    def get_verified_bank_accounts(self, user_id: UUID) -> List[BankAccount]:
        """
        Obtiene solo las cuentas bancarias verificadas de un usuario.
        Verifica que el usuario tenga el rol apropiado.
        """
        # Verificar rol del usuario
        self.verify_user_role(user_id)

        return self.session.query(BankAccount).filter(
            BankAccount.user_id == user_id,
            BankAccount.verification_date.isnot(None),
            BankAccount.is_active == True
        ).all()
