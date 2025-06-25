from fastapi import APIRouter, Depends, Request, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.db import SessionDep
from app.services.transaction_service import TransactionService
from app.models.transaction import TransactionType, TransactionCreate
from pydantic import BaseModel, Field
from typing import List, Dict, Any

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
    id: str = Field(..., description="ID único de la transacción",
                    example="550e8400-e29b-41d4-a716-446655440000")
    user_id: str = Field(..., description="ID del usuario propietario",
                         example="550e8400-e29b-41d4-a716-446655440001")
    income: int = Field(...,
                        description="Monto de ingreso (0 si es egreso)", example=21250)
    expense: int = Field(...,
                         description="Monto de egreso (0 si es ingreso)", example=0)
    type: str = Field(..., description="Tipo de transacción",
                      example="SERVICE")
    client_request_id: str = Field(
        None, description="ID de la solicitud asociada", example="550e8400-e29b-41d4-a716-446655440002"
    )
    is_confirmed: bool = Field(...,
                               description="Estado de confirmación", example=True)
    date: str = Field(..., description="Fecha de la transacción",
                      example="2025-01-15T14:30:00")
    description: str = Field(None, description="Descripción de la transacción",
                             example="Ingreso por servicio del viaje 550e8400-e29b-41d4-a716-446655440002")


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
