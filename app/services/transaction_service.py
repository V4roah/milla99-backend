from sqlmodel import Session, select
from app.models.transaction import Transaction, TransactionType
from app.models.verify_mount import VerifyMount
from sqlalchemy import func
from fastapi import HTTPException
import traceback


class TransactionService:
    def __init__(self, session):
        self.session = session

    def create_transaction(self, user_id, income=0, expense=0, type=None, client_request_id=None):
        print("TRACEBACK INICIO:\n", "".join(traceback.format_stack()))
        print(f"DEBUG income: {income}, expense: {expense}, type: {type}")

        # Validación de tipo y monto
        if type == TransactionType.RECHARGE:
            if income <= 0 or expense != 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Las transacciones de tipo {type} solo pueden ser ingresos (income > 0, expense == 0)."
                )
        elif type == TransactionType.SERVICE:
            if expense <= 0 or income != 0:
                raise HTTPException(
                    status_code=400,
                    detail="Las transacciones de tipo SERVICE solo pueden ser egresos (expense > 0, income == 0)."
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Tipo de transacción no soportado o aún no implementado."
            )

        # Validar saldo suficiente para egresos
        if expense > 0:
            verify_mount = self.session.query(VerifyMount).filter(
                VerifyMount.user_id == user_id).first()
            if not verify_mount or verify_mount.mount < expense:
                raise HTTPException(
                    status_code=400,
                    detail="Saldo insuficiente para realizar la transacción."
                )

        transaction = Transaction(
            user_id=user_id,
            income=income,
            expense=expense,
            type=type,
            client_request_id=client_request_id
        )
        self.session.add(transaction)
        self.session.commit()
        self.session.refresh(transaction)

        # Actualizar el mount en VerifyMount para ingresos y egresos
        verify_mount = self.session.query(VerifyMount).filter(
            VerifyMount.user_id == user_id).first()
        print(
            f"DEBUG verify_mount antes: {verify_mount.mount if verify_mount else 'NO EXISTE'}")
        if not verify_mount:
            verify_mount = VerifyMount(user_id=user_id, mount=0)
            self.session.add(verify_mount)
            self.session.commit()
            print("DEBUG verify_mount creado")

        if income > 0:
            print(
                f"DEBUG sumando income {income} a mount {verify_mount.mount}")
            verify_mount.mount += income
        if expense > 0:
            print(
                f"DEBUG restando expense {expense} a mount {verify_mount.mount}")
            verify_mount.mount -= expense
        self.session.add(verify_mount)
        self.session.commit()
        print(f"DEBUG verify_mount después: {verify_mount.mount}")

        amount = income if income > 0 else -expense if expense > 0 else 0
        return {
            "message": "Transacción exitosa",
            "amount": amount,
            "transaction_type": type
        }

    def get_user_balance(self, user_id: int):
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

    def list_transactions(self, user_id: int):
        return self.session.query(Transaction).filter(Transaction.user_id == user_id).order_by(Transaction.date.desc()).all()
