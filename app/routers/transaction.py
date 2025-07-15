from fastapi import APIRouter, Depends, Request, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.db import SessionDep
from app.services.transaction_service import TransactionService
from app.models.transaction import TransactionType, TransactionCreate
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime

bearer_scheme = HTTPBearer()

router = APIRouter(prefix="/transactions", tags=["transactions"])


# Modelos para response
class BalanceResponse(BaseModel):
    available: float = Field(
        ..., description="Saldo total disponible (total_income - total_expense)", example=150000
    )
    withdrawable: float = Field(
        ..., description="Saldo retirable (excluye bonificaciones)", example=145000
    )
    mount: float = Field(
        ..., description="Saldo actual en cuenta (VerifyMount)", example=150000
    )


class TransactionResponse(BaseModel):
    id: UUID = Field(..., description="ID único de la transacción")
    user_id: UUID = Field(..., description="ID del usuario propietario")
    income: int = Field(..., description="Monto de ingreso (0 si es egreso)")
    expense: int = Field(..., description="Monto de egreso (0 si es ingreso)")
    type: str = Field(..., description="Tipo de transacción")
    client_request_id: Optional[UUID] = Field(
        None, description="ID de la solicitud asociada")
    is_confirmed: bool = Field(..., description="Estado de confirmación")
    date: datetime = Field(..., description="Fecha de la transacción")
    description: Optional[str] = Field(
        None, description="Descripción de la transacción")


# Modelos para recarga
class RechargeRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Monto a recargar (en pesos)")
    description: Optional[str] = Field(
        "Recarga de saldo", description="Descripción opcional")


class RechargeResponse(BaseModel):
    message: str = Field(..., description="Mensaje de confirmación")
    transaction_id: UUID = Field(...,
                                 description="ID de la transacción creada")
    user_id: UUID = Field(...,
                          description="ID del usuario que solicitó la recarga")
    amount_recharged: int = Field(..., description="Monto recargado")
    transaction_type: str = Field(..., description="Tipo de transacción")
    created_at: datetime = Field(..., description="Fecha y hora de creación")


@router.get(
    "/balance/me",
    response_model=BalanceResponse,
    description="""
    Obtiene el saldo completo del usuario autenticado.
    
    Permite a los usuarios consultar su saldo actual, incluyendo el saldo disponible, retirable y el saldo real en cuenta.
    """,
    responses={
        200: {
            "description": "Saldo obtenido exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "available": 150000,
                        "withdrawable": 145000,
                        "mount": 150000
                    }
                }
            }
        },
        401: {
            "description": "No autorizado - Token inválido o expirado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Could not validate credentials"
                    }
                }
            }
        },
        403: {
            "description": "Prohibido - Token no proporcionado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Not authenticated"
                    }
                }
            }
        },
        404: {
            "description": "Usuario no encontrado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "User not found"
                    }
                }
            }
        }
    }
)
def get_my_balance(
    request: Request,
    session: SessionDep,
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
):
    """
    Obtiene el saldo completo del usuario autenticado.
    """
    user_id = request.state.user_id
    service = TransactionService(session)
    return service.get_user_balance(user_id)


@router.get(
    "/list/me",
    response_model=List[TransactionResponse],
    description="""
    Lista todas las transacciones del usuario autenticado.
    
    Permite a los usuarios consultar su historial completo de transacciones, incluyendo ingresos, egresos, comisiones, bonificaciones y todas las operaciones financieras realizadas en la plataforma.
    """,
    responses={
        200: {
            "description": "Lista de transacciones obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "user_id": "550e8400-e29b-41d4-a716-446655440001",
                            "income": 21250,
                            "expense": 0,
                            "type": "SERVICE",
                            "client_request_id": "550e8400-e29b-41d4-a716-446655440002",
                            "is_confirmed": True,
                            "date": "2025-01-15T14:30:00",
                            "description": "Ingreso por servicio del viaje 550e8400-e29b-41d4-a716-446655440002"
                        },
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440003",
                            "user_id": "550e8400-e29b-41d4-a716-446655440001",
                            "income": 0,
                            "expense": 2500,
                            "type": "COMMISSION",
                            "client_request_id": "550e8400-e29b-41d4-a716-446655440002",
                            "is_confirmed": True,
                            "date": "2025-01-15T14:30:00",
                            "description": "Comisión por uso de la plataforma para el viaje 550e8400-e29b-41d4-a716-446655440002"
                        },
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440004",
                            "user_id": "550e8400-e29b-41d4-a716-446655440001",
                            "income": 50000,
                            "expense": 0,
                            "type": "RECHARGE",
                            "client_request_id": None,
                            "is_confirmed": True,
                            "date": "2025-01-14T10:15:00",
                            "description": "Recarga de saldo"
                        }
                    ]
                }
            }
        },
        401: {
            "description": "No autorizado - Token inválido o expirado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Could not validate credentials"
                    }
                }
            }
        },
        403: {
            "description": "Prohibido - Token no proporcionado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Not authenticated"
                    }
                }
            }
        },
        404: {
            "description": "Usuario no encontrado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "User not found"
                    }
                }
            }
        }
    }
)
def list_my_transactions(
    request: Request,
    session: SessionDep,
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
):
    """
    Lista todas las transacciones del usuario autenticado.
    """
    user_id = request.state.user_id
    service = TransactionService(session)
    return service.list_transactions(user_id)


@router.post(
    "/recharge",
    response_model=RechargeResponse,
    status_code=status.HTTP_201_CREATED,
    description="""
    Crea una recarga de saldo para el usuario autenticado.
    
    Permite a usuarios (clientes y conductores) recargar su saldo en la plataforma.
    La recarga se crea como pendiente de aprobación por un administrador.
    
    **Parámetros:**
    - `amount`: Monto a recargar (debe ser mayor al mínimo configurado)
    - `description`: Descripción opcional de la recarga
    
    **Respuesta:**
    Devuelve información de la recarga creada, incluyendo ID de transacción y monto.
    """,
    responses={
        201: {
            "description": "Recarga creada exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Recarga creada exitosamente. Pendiente de aprobación por administrador.",
                        "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
                        "user_id": "550e8400-e29b-41d4-a716-446655440001",
                        "amount_recharged": 50000,
                        "transaction_type": "RECHARGE",
                        "created_at": "2025-01-15T14:30:00"
                    }
                }
            }
        },
        400: {
            "description": "Monto inválido o insuficiente",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "El monto mínimo para recargas es 10,000 pesos"
                    }
                }
            }
        },
        401: {
            "description": "No autorizado - Token inválido o expirado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Could not validate credentials"
                    }
                }
            }
        },
        403: {
            "description": "Prohibido - Token no proporcionado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Not authenticated"
                    }
                }
            }
        }
    }
)
def create_recharge(
    request: Request,
    recharge_data: RechargeRequest,
    session: SessionDep,
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
):
    """
    Crea una recarga de saldo para el usuario autenticado.
    """
    user_id = request.state.user_id
    service = TransactionService(session)

    result = service.create_recharge(
        user_id=user_id,
        amount=recharge_data.amount,
        description=recharge_data.description
    )

    return RechargeResponse(**result)
