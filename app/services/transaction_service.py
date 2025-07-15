from sqlmodel import Session, select
from app.models.transaction import Transaction, TransactionType
from app.models.verify_mount import VerifyMount
from sqlalchemy import func
from fastapi import HTTPException
from uuid import UUID
from app.models.user import User
from app.utils.balance_notifications import check_and_notify_low_balance


class TransactionService:
    def __init__(self, session):
        self.session = session

    def create_transaction(self, user_id: UUID, income=0, expense=0, type=None, client_request_id=None, description=None):
        verify_mount = self.session.query(VerifyMount).filter(
            VerifyMount.user_id == user_id).first()

        # Validación para RECHARGE
        if type == TransactionType.RECHARGE or type == TransactionType.PENALITY_COMPENSATION:
            if income <= 0 or expense != 0:
                raise HTTPException(
                    status_code=400,
                    detail="Las transacciones de tipo RECHARGE solo pueden ser ingresos (income > 0, expense == 0)."
                )
            if verify_mount:
                verify_mount.mount += income
                check_and_notify_low_balance(
                    self.session, user_id, verify_mount.mount)
            else:
                verify_mount = VerifyMount(user_id=user_id, mount=income)
                self.session.add(verify_mount)
                check_and_notify_low_balance(
                    self.session, user_id, verify_mount.mount)

        # Validación para WITHDRAWAL
        elif type == TransactionType.WITHDRAWAL:
            if income != 0 or expense <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Las transacciones de tipo WITHDRAWAL solo pueden ser egresos (income == 0, expense > 0)."
                )
            if not verify_mount or verify_mount.mount < expense:
                raise HTTPException(
                    status_code=400,
                    detail="Saldo insuficiente para realizar el retiro."
                )
            verify_mount.mount -= expense
            check_and_notify_low_balance(
                self.session, user_id, verify_mount.mount)

        # Permitir egresos para SERVICE
        elif type == TransactionType.SERVICE or type == TransactionType.PENALITY_DEDUCTION:
            if not verify_mount or verify_mount.mount < expense:
                raise HTTPException(
                    status_code=400,
                    detail="Saldo insuficiente para realizar la transacción."
                )
            verify_mount.mount -= expense
            check_and_notify_low_balance(
                self.session, user_id, verify_mount.mount)

        # Validación para SERVICE (solo ingresos)
        elif type == TransactionType.SERVICE:
            if income <= 0 or expense != 0:
                raise HTTPException(
                    status_code=400,
                    detail="Las transacciones de tipo SERVICE solo pueden ser ingresos (income > 0, expense == 0)."
                )
            if verify_mount:
                verify_mount.mount += income
                check_and_notify_low_balance(
                    self.session, user_id, verify_mount.mount)
            else:
                verify_mount = VerifyMount(user_id=user_id, mount=income)
                self.session.add(verify_mount)
                check_and_notify_low_balance(
                    self.session, user_id, verify_mount.mount)

        # Validación para COMMISSION
        elif type == TransactionType.COMMISSION:
            if (income > 0 and expense == 0):
                # Ingreso por comisión (ej: para la empresa)
                if verify_mount:
                    verify_mount.mount += income
                    check_and_notify_low_balance(
                        self.session, user_id, verify_mount.mount)
                else:
                    verify_mount = VerifyMount(user_id=user_id, mount=income)
                    self.session.add(verify_mount)
                    check_and_notify_low_balance(
                        self.session, user_id, verify_mount.mount)
            elif (income == 0 and expense > 0):
                # Egreso por comisión (ej: para el conductor)
                if not verify_mount or verify_mount.mount < expense:
                    raise HTTPException(
                        status_code=400,
                        detail="Saldo insuficiente para realizar la comisión."
                    )
                verify_mount.mount -= expense
                check_and_notify_low_balance(
                    self.session, user_id, verify_mount.mount)
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Las transacciones de tipo COMMISSION solo pueden ser ingresos (income > 0, expense == 0) o egresos (income == 0, expense > 0)."
                )

        # Otros tipos (por defecto solo ingresos)
        elif type != TransactionType.BONUS:
            if income <= 0 or expense != 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Las transacciones de tipo {type} solo pueden ser ingresos (income > 0, expense == 0)."
                )
            if verify_mount:
                verify_mount.mount += income
                check_and_notify_low_balance(
                    self.session, user_id, verify_mount.mount)
            else:
                verify_mount = VerifyMount(user_id=user_id, mount=income)
                self.session.add(verify_mount)
                check_and_notify_low_balance(
                    self.session, user_id, verify_mount.mount)

        transaction = Transaction(
            user_id=user_id,
            income=income,
            expense=expense,
            type=type,
            client_request_id=client_request_id,
            description=description
        )
        self.session.add(transaction)
        # No commit aquí
        if type != TransactionType.BONUS:
            return {
                "message": "Transacción exitosa",
                "amount": verify_mount.mount,
                "transaction_type": type
            }
        else:
            valor = income if income else expense
            return {
                "message": "Transacción exitosa",
                "amount": valor,
                "transaction_type": type
            }

    def get_user_balance(self, user_id: UUID):
        total_income = self.session.query(func.sum(Transaction.income)).filter(
            Transaction.user_id == user_id).scalar() or 0
        total_expense = self.session.query(func.sum(Transaction.expense)).filter(
            Transaction.user_id == user_id).scalar() or 0
        withdrawable_income = self.session.query(func.sum(Transaction.income)).filter(
            Transaction.user_id == user_id, Transaction.type != TransactionType.BONUS).scalar() or 0
        available = total_income - total_expense
        withdrawable = withdrawable_income - total_expense
        withdrawable = max(withdrawable, 0)
        if total_income == withdrawable_income:
            withdrawable = available
        verify_mount = self.session.query(VerifyMount).filter(
            VerifyMount.user_id == user_id).first()
        mount = verify_mount.mount if verify_mount else 0
        return {
            "available": available,
            "withdrawable": withdrawable,
            "mount": mount
        }

    def list_transactions(self, user_id: UUID):
        return self.session.query(Transaction).filter(Transaction.user_id == user_id).order_by(Transaction.date.desc()).all()

    def create_recharge(self, user_id: UUID, amount: int, description: str = "Recarga de saldo"):
        """
        Crea una recarga de saldo para el usuario.
        La transacción se crea como pendiente de aprobación (is_confirmed=False).
        """
        from app.models.project_settings import ProjectSettings
        from app.models.user import User
        from sqlmodel import select

        # Obtener configuración de monto mínimo
        project_settings = self.session.exec(
            select(ProjectSettings).where(ProjectSettings.id == 1)
        ).first()

        if not project_settings:
            raise HTTPException(
                status_code=500,
                detail="Configuración del proyecto no encontrada"
            )

        min_amount = project_settings.min_recharge_amount or 10000

        # Validar monto mínimo
        if amount < min_amount:
            raise HTTPException(
                status_code=400,
                detail=f"El monto mínimo para recargas es ${min_amount:,} pesos"
            )

        # Verificar que el usuario existe y está activo
        user = self.session.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=404,
                detail="Usuario no encontrado"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=400,
                detail="Usuario inactivo"
            )

        # Crear transacción RECHARGE (pendiente de aprobación)
        transaction = Transaction(
            user_id=user_id,
            income=amount,
            expense=0,
            type=TransactionType.RECHARGE,
            description=description,
            is_confirmed=False  # Requiere aprobación de admin
        )

        # Guardar transacción
        self.session.add(transaction)
        self.session.commit()
        self.session.refresh(transaction)

        return {
            "message": "Recarga creada exitosamente. Pendiente de aprobación por administrador.",
            "transaction_id": transaction.id,
            "user_id": user_id,
            "amount_recharged": amount,
            "transaction_type": TransactionType.RECHARGE,
            "created_at": transaction.date
        }

    def confirm_transaction(self, transaction_id: UUID):
        """
        Confirma una transacción y actualiza el verify_mount del usuario.
        """
        transaction = self.session.exec(
            select(Transaction).where(Transaction.id == transaction_id)
        ).first()

        if not transaction:
            raise HTTPException(
                status_code=404,
                detail="Transacción no encontrada"
            )

        if transaction.is_confirmed:
            raise HTTPException(
                status_code=400,
                detail="La transacción ya está confirmada"
            )

        # Confirmar la transacción
        transaction.is_confirmed = True
        self.session.add(transaction)

        # Actualizar verify_mount según el tipo de transacción
        verify_mount = self.session.query(VerifyMount).filter(
            VerifyMount.user_id == transaction.user_id
        ).first()

        if transaction.type == TransactionType.RECHARGE:
            if transaction.income > 0:
                if verify_mount:
                    verify_mount.mount += transaction.income
                else:
                    verify_mount = VerifyMount(
                        user_id=transaction.user_id,
                        mount=transaction.income
                    )
                    self.session.add(verify_mount)
                check_and_notify_low_balance(
                    self.session, transaction.user_id, verify_mount.mount)

        self.session.commit()

        return {
            "message": "Transacción confirmada exitosamente",
            "transaction_id": transaction.id,
            "user_id": transaction.user_id,
            "amount": transaction.income if transaction.income > 0 else transaction.expense,
            "type": transaction.type
        }
