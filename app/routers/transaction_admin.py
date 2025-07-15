from fastapi import APIRouter, Depends, Request, status, HTTPException
from app.core.db import SessionDep
from app.services.transaction_service import TransactionService
from app.core.dependencies.admin_auth import get_current_admin_user
from app.models.administrador import Administrador
from app.utils.admin_log_decorators import log_transaction_approval
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime

router = APIRouter(
    prefix="/admin/transactions",
    tags=["ADMIN - Transaction Management"]
)


class TransactionApprovalRequest(BaseModel):
    transaction_id: UUID = Field(...,
                                 description="ID de la transacción a aprobar")


class TransactionApprovalResponse(BaseModel):
    message: str = Field(..., description="Mensaje de confirmación")
    transaction_id: UUID = Field(...,
                                 description="ID de la transacción aprobada")
    user_id: UUID = Field(..., description="ID del usuario")
    amount: int = Field(..., description="Monto de la transacción")
    transaction_type: str = Field(..., description="Tipo de transacción")
    approved_at: datetime = Field(..., description="Fecha de aprobación")


@router.post("/approve", response_model=TransactionApprovalResponse, status_code=status.HTTP_200_OK, description="""
Aprueba una transacción pendiente (como recargas).

**SOLO PARA ADMINISTRADORES**

**Parámetros:**
- `transaction_id`: ID de la transacción a aprobar (UUID).

**Respuesta:**
Devuelve los detalles de la transacción aprobada.

**Notas:**
- Solo se pueden aprobar transacciones pendientes (is_confirmed=False)
- Al aprobar una recarga, se actualiza el verify_mount del usuario
- Se registra la acción en los logs de administrador
""")
@log_transaction_approval()
async def approve_transaction(
    approval_data: TransactionApprovalRequest,
    request: Request,
    session: SessionDep,
    current_admin: Administrador = Depends(get_current_admin_user)
):
    """
    Aprueba una transacción pendiente.
    """
    service = TransactionService(session)

    try:
        # Obtener la transacción antes de confirmarla para el logging
        from sqlmodel import select
        from app.models.transaction import Transaction

        transaction = session.exec(
            select(Transaction).where(
                Transaction.id == approval_data.transaction_id)
        ).first()

        if not transaction:
            raise HTTPException(
                status_code=404,
                detail="Transacción no encontrada"
            )

        # Confirmar la transacción
        service.confirm_transaction(approval_data.transaction_id)

        # Pasar datos al decorador para el logging
        request.state.transaction_id = str(transaction.id)
        request.state.amount = transaction.income
        request.state.transaction_type = transaction.type

        return TransactionApprovalResponse(
            message="Transacción aprobada exitosamente",
            transaction_id=transaction.id,
            user_id=transaction.user_id,
            amount=transaction.income,
            transaction_type=transaction.type,
            approved_at=transaction.date
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del servidor: {str(e)}"
        )
