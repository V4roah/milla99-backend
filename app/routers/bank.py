from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session
from typing import List
from app.core.db import get_session
from app.models.bank import Bank
from app.services.bank_service import BankService
from pydantic import BaseModel, Field

router = APIRouter(prefix="/banks", tags=["banks"])


# Modelos para request/response
class BankCreate(BaseModel):
    bank_code: str = Field(..., max_length=10,
                           description="Código único del banco (ej: '001', '007')")
    bank_name: str = Field(..., max_length=100,
                           description="Nombre del banco (ej: 'Bancolombia', 'Banco de Bogotá')")


class BankUpdate(BaseModel):
    bank_code: str = Field(None, max_length=10,
                           description="Código único del banco")
    bank_name: str = Field(None, max_length=100,
                           description="Nombre del banco")


@router.get("/",
            response_model=List[Bank],
            description="""
    Obtiene la lista completa de todos los bancos disponibles en el sistema.
    
    **Propósito:**
    Este endpoint permite a los usuarios (clientes y conductores) obtener la lista de bancos
    disponibles para crear cuentas bancarias. Es un endpoint público que no requiere autenticación.
    
    **Respuesta:**
    - Lista de todos los bancos con sus códigos y nombres
    - Ordenados por ID (orden de creación)
    
    **Casos de uso:**
    - Mostrar lista de bancos en formularios de registro de cuentas
    - Permitir a usuarios seleccionar su banco al crear cuentas bancarias
    - Consulta de referencia para operaciones bancarias
    """,
            responses={
                200: {
                    "description": "Lista de bancos obtenida exitosamente",
                    "content": {
                        "application/json": {
                            "example": [
                                {
                                    "id": 1,
                                    "bank_code": "001",
                                    "bank_name": "Banco de Bogotá",
                                    "created_at": "2025-01-01T00:00:00",
                                    "updated_at": "2025-01-01T00:00:00"
                                },
                                {
                                    "id": 2,
                                    "bank_code": "007",
                                    "bank_name": "Bancolombia",
                                    "created_at": "2025-01-01T00:00:00",
                                    "updated_at": "2025-01-01T00:00:00"
                                }
                            ]
                        }
                    }
                }
            }
            )
def list_banks(session: Session = Depends(get_session)):
    """
    Lista todos los bancos disponibles en el sistema.
    """
    service = BankService(session)
    return service.list_banks()


@router.get("/{bank_id}",
            response_model=Bank,
            description="""
    Obtiene la información detallada de un banco específico por su ID.
    
    **Propósito:**
    Permite obtener los datos completos de un banco específico, incluyendo su código,
    nombre y fechas de creación/actualización. Útil para validaciones o mostrar
    información detallada de un banco seleccionado.
    
    **Parámetros:**
    - `bank_id`: ID numérico del banco a consultar
    
    **Respuesta:**
    - Datos completos del banco solicitado
    - Incluye fechas de creación y actualización
    
    **Casos de uso:**
    - Validar existencia de un banco específico
    - Mostrar información detallada de un banco
    - Verificar datos antes de crear cuentas bancarias
    """,
            responses={
                200: {
                    "description": "Banco encontrado exitosamente",
                    "content": {
                        "application/json": {
                            "example": {
                                "id": 7,
                                "bank_code": "007",
                                "bank_name": "Bancolombia",
                                "created_at": "2025-01-01T00:00:00",
                                "updated_at": "2025-01-01T00:00:00"
                            }
                        }
                    }
                },
                404: {
                    "description": "Banco no encontrado",
                    "content": {
                        "application/json": {
                            "example": {
                                "detail": "Bank not found"
                            }
                        }
                    }
                }
            }
            )
def get_bank(bank_id: int, session: Session = Depends(get_session)):
    """
    Obtiene un banco específico por su ID.
    """
    service = BankService(session)
    return service.get_bank(bank_id)


@router.post("/",
             response_model=Bank,
             status_code=status.HTTP_201_CREATED,
             description="""
    Crea un nuevo banco en el sistema.
    
    **Propósito:**
    Permite a los administradores agregar nuevos bancos al sistema. Los bancos
    son entidades fundamentales para el sistema de pagos y retiros, ya que
    los usuarios necesitan asociar sus cuentas bancarias a bancos existentes.
    
    **Request:**
    - `bank_code`: Código único del banco (máximo 10 caracteres)
    - `bank_name`: Nombre del banco (máximo 100 caracteres)
    
    **Validaciones:**
    - El `bank_code` debe ser único en el sistema
    - Ambos campos son obligatorios
    - Longitudes máximas según especificación
    
    **Respuesta:**
    - Datos del banco creado incluyendo ID asignado
    - Fechas de creación y actualización automáticas
    
    **Casos de uso:**
    - Agregar nuevos bancos al sistema
    - Actualizar catálogo de bancos disponibles
    - Mantener lista actualizada de entidades financieras
    """,
             responses={
                 201: {
                     "description": "Banco creado exitosamente",
                     "content": {
                         "application/json": {
                             "example": {
                                 "id": 15,
                                 "bank_code": "999",
                                 "bank_name": "Nuevo Banco Digital",
                                 "created_at": "2025-01-15T10:30:00",
                                 "updated_at": "2025-01-15T10:30:00"
                             }
                         }
                     }
                 },
                 422: {
                     "description": "Datos de entrada inválidos",
                     "content": {
                         "application/json": {
                             "example": {
                                 "detail": [
                                     {
                                         "loc": ["body", "bank_code"],
                                         "msg": "field required",
                                         "type": "value_error.missing"
                                     }
                                 ]
                             }
                         }
                     }
                 },
                 409: {
                     "description": "Código de banco ya existe",
                     "content": {
                         "application/json": {
                             "example": {
                                 "detail": "Bank code already exists"
                             }
                         }
                     }
                 }
             }
             )
def create_bank(bank: BankCreate, session: Session = Depends(get_session)):
    """
    Crea un nuevo banco en el sistema.
    """
    service = BankService(session)
    return service.create_bank(bank.dict())


@router.put("/{bank_id}",
            response_model=Bank,
            description="""
    Actualiza la información de un banco existente.
    
    **Propósito:**
    Permite a los administradores modificar los datos de un banco existente,
    como su código o nombre. Útil para corregir errores o actualizar
    información de bancos que han cambiado sus datos.
    
    **Parámetros:**
    - `bank_id`: ID del banco a actualizar
    
    **Request:**
    - `bank_code`: Nuevo código del banco (opcional)
    - `bank_name`: Nuevo nombre del banco (opcional)
    
    **Validaciones:**
    - El banco debe existir
    - Si se actualiza `bank_code`, debe ser único
    - Al menos un campo debe ser proporcionado
    
    **Respuesta:**
    - Datos actualizados del banco
    - `updated_at` se actualiza automáticamente
    
    **Casos de uso:**
    - Corregir errores en datos de bancos
    - Actualizar nombres de bancos que han cambiado
    - Modificar códigos de bancos por cambios regulatorios
    """,
            responses={
                200: {
                    "description": "Banco actualizado exitosamente",
                    "content": {
                        "application/json": {
                            "example": {
                                "id": 7,
                                "bank_code": "007",
                                "bank_name": "Bancolombia S.A.",
                                "created_at": "2025-01-01T00:00:00",
                                "updated_at": "2025-01-15T14:30:00"
                            }
                        }
                    }
                },
                404: {
                    "description": "Banco no encontrado",
                    "content": {
                        "application/json": {
                            "example": {
                                "detail": "Bank not found"
                            }
                        }
                    }
                },
                422: {
                    "description": "Datos de entrada inválidos",
                    "content": {
                        "application/json": {
                            "example": {
                                "detail": [
                                    {
                                        "loc": ["body", "bank_code"],
                                        "msg": "ensure this value has at most 10 characters",
                                        "type": "value_error.any_str.max_length"
                                    }
                                ]
                            }
                        }
                    }
                },
                409: {
                    "description": "Código de banco ya existe",
                    "content": {
                        "application/json": {
                            "example": {
                                "detail": "Bank code already exists"
                            }
                        }
                    }
                }
            }
            )
def update_bank(bank_id: int, bank: BankUpdate, session: Session = Depends(get_session)):
    """
    Actualiza un banco existente.
    """
    service = BankService(session)
    return service.update_bank(bank_id, bank.dict(exclude_unset=True))


@router.delete("/{bank_id}",
               description="""
    Elimina un banco del sistema.
    
    **Propósito:**
    Permite a los administradores eliminar bancos que ya no están activos
    o que han sido absorbidos por otras entidades. Esta operación es
    irreversible y debe usarse con precaución.
    
    **Parámetros:**
    - `bank_id`: ID del banco a eliminar
    
    **Validaciones:**
    - El banco debe existir
    - No debe tener cuentas bancarias asociadas (restricción de integridad)
    - No debe tener retiros pendientes asociados
    
    **Respuesta:**
    - Mensaje de confirmación de eliminación
    - No devuelve datos del banco eliminado
    
    **Casos de uso:**
    - Eliminar bancos que han cerrado operaciones
    - Limpiar catálogo de bancos obsoletos
    - Mantener integridad de datos del sistema
    
    **⚠️ Advertencia:**
    Esta operación es irreversible. Asegúrese de que el banco no tenga
    cuentas bancarias asociadas antes de eliminarlo.
    """,
               responses={
                   200: {
                       "description": "Banco eliminado exitosamente",
                       "content": {
                           "application/json": {
                               "example": {
                                   "message": "Bank deleted successfully"
                               }
                           }
                       }
                   },
                   404: {
                       "description": "Banco no encontrado",
                       "content": {
                           "application/json": {
                               "example": {
                                   "detail": "Bank not found"
                               }
                           }
                       }
                   },
                   409: {
                       "description": "No se puede eliminar el banco",
                       "content": {
                           "application/json": {
                               "example": {
                                   "detail": "Cannot delete bank: has associated bank accounts"
                               }
                           }
                       }
                   }
               }
               )
def delete_bank(bank_id: int, session: Session = Depends(get_session)):
    """
    Elimina un banco del sistema.
    """
    service = BankService(session)
    return service.delete_bank(bank_id)
