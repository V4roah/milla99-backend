from fastapi import APIRouter, Depends, status, HTTPException, Request, Query, Body
from uuid import UUID
import logging
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from app.core.dependencies.admin_auth import get_current_admin
from app.core.db import SessionDep
from app.services.withdrawal_service import WithdrawalService
from app.models.withdrawal import Withdrawal, WithdrawalStatus, WithdrawalRead
from app.utils.admin_log_decorators import log_withdrawal_approval, log_withdrawal_rejection

router = APIRouter(
    prefix="/withdrawals",
    tags=["ADMIN"]
)


class UpdateWithdrawalStatusRequest(BaseModel):
    new_status: str


class ListWithdrawalsRequest(BaseModel):
    """Modelo para filtrar retiros"""
    status: Optional[str] = None  # "pending", "approved", "rejected"
    skip: int = 0
    limit: int = 100


@router.patch("/{withdrawal_id}/update-status", status_code=status.HTTP_200_OK, description="""
Actualiza el estado de un retiro (withdrawal) por su ID. Este endpoint está separado y se agrupa en la sección de administración en Swagger.

**Parámetros:**
- `withdrawal_id`: UUID del retiro a actualizar.
- `new_status`: Nuevo estado (por ejemplo, "approved", "rejected").

**Respuesta:**
Devuelve el objeto de retiro actualizado.
""")
# Decorador específico para logging crítico de retiros
@log_withdrawal_approval()
async def update_withdrawal_status(
    withdrawal_id: UUID,
    data: UpdateWithdrawalStatusRequest,
    request: Request,
    session: SessionDep,
    current_admin=Depends(get_current_admin)
):
    service = WithdrawalService(session)
    try:
        if data.new_status == "approved":
            return service.approve_withdrawal(withdrawal_id)
        elif data.new_status == "rejected":
            return service.reject_withdrawal(withdrawal_id)
        else:
            raise HTTPException(
                status_code=400, detail="Invalid or unsupported status")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.exception("Unexpected error updating withdrawal status")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/list", response_model=List[WithdrawalRead], description="""
Lista los retiros filtrados por status.

**Body:**
```json
{
    "status": "pending",  // Opcional: pending, approved, rejected
    "skip": 0,           // Opcional: número de registros a saltar
    "limit": 100         // Opcional: número máximo de registros (máx 100)
}
```

**Respuesta:**
Devuelve una lista de retiros con información detallada del usuario y la cuenta bancaria.
""")
async def list_withdrawals(
    filters: ListWithdrawalsRequest,
    session: SessionDep,
    current_admin=Depends(get_current_admin)
):
    service = WithdrawalService(session)
    try:
        # Convertir el status string a WithdrawalStatus si está presente
        status_enum = None
        if filters.status:
            try:
                status_enum = WithdrawalStatus(filters.status)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {filters.status}. Must be one of: {[s.value for s in WithdrawalStatus]}"
                )

        return service.list_withdrawals(
            status=status_enum,
            skip=filters.skip,
            limit=filters.limit
        )
    except Exception as e:
        logging.exception("Error listing withdrawals")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
