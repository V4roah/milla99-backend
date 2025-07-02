from fastapi import APIRouter, Depends, HTTPException, status
from app.core.db import SessionDep
from app.core.dependencies.auth import get_current_user
from app.services.trip_stops_service import (
    get_trip_stops,
    get_current_stop,
    update_stop_status,
    get_trip_progress
)
from app.models.trip_stop import StopStatus, TripStopRead
from app.models.user import User
from uuid import UUID
from typing import List

router = APIRouter(
    prefix="/trip-stops",
    tags=["Trip Stops"],
    dependencies=[Depends(get_current_user)]
)


@router.get(
    "/{client_request_id}/stops",
    response_model=List[TripStopRead],
    status_code=200,
    description="""
Propósito: Permite al cliente o conductor ver todas las paradas de un viaje, su orden y estado actual.

**Permisos de Acceso:**
- El cliente que creó el viaje o el conductor asignado pueden ver las paradas.

**Parámetros:**
- `client_request_id`: ID del viaje.

**Respuesta:**
Devuelve una lista de paradas ordenadas (origen, intermedias, destino) con su estado actual.
"""
)
async def get_stops(
    client_request_id: UUID,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene todas las paradas de un viaje específico.
    Solo el cliente dueño del viaje o el conductor asignado pueden ver las paradas.
    """
    # Verificar permisos
    from app.models.client_request import ClientRequest
    client_request = session.get(ClientRequest, client_request_id)
    if not client_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud de viaje no encontrada"
        )

    if client_request.id_client != current_user.id and client_request.id_driver_assigned != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver las paradas de este viaje"
        )

    stops = get_trip_stops(session, client_request_id)
    return stops


@router.get(
    "/{client_request_id}/current-stop",
    status_code=200,
    description="""
Propósito: Permite consultar la parada actual pendiente del viaje, útil para saber cuál es la siguiente parada a atender.

**Permisos de Acceso:**
- El cliente que creó el viaje o el conductor asignado pueden consultar la parada actual.

**Parámetros:**
- `client_request_id`: ID del viaje.

**Respuesta:**
Devuelve la información de la parada pendiente más próxima (ordenada por stop_order).
"""
)
async def get_current_stop_info(
    client_request_id: UUID,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene la parada actual del viaje.
    """
    # Verificar permisos
    from app.models.client_request import ClientRequest
    client_request = session.get(ClientRequest, client_request_id)
    if not client_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud de viaje no encontrada"
        )

    if client_request.id_client != current_user.id and client_request.id_driver_assigned != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver las paradas de este viaje"
        )

    current_stop = get_current_stop(session, client_request_id)
    if not current_stop:
        return {"message": "No hay paradas pendientes", "current_stop": None}

    return {
        "current_stop": {
            "id": str(current_stop.id),
            "stop_order": current_stop.stop_order,
            "stop_type": current_stop.stop_type,
            "status": current_stop.status,
            "latitude": current_stop.latitude,
            "longitude": current_stop.longitude,
            "description": current_stop.description
        }
    }


@router.patch(
    "/{stop_id}/status",
    status_code=200,
    description="""
Propósito: Permite al conductor actualizar el estado de una parada (por ejemplo, marcar como ARRIVED o COMPLETED).

**Permisos de Acceso:**
- Solo el conductor asignado puede actualizar el estado de las paradas.

**Parámetros:**
- `stop_id`: ID de la parada a actualizar.
- `status`: Nuevo estado a asignar (PENDING, ARRIVED, COMPLETED).

**Respuesta:**
Devuelve un mensaje de éxito y la información actualizada de la parada.
"""
)
async def update_stop_status_endpoint(
    stop_id: UUID,
    status_update: dict,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """
    Actualiza el estado de una parada específica.
    Solo el conductor asignado puede actualizar el estado de las paradas.
    """
    try:
        new_status = StopStatus(status_update.get("status"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estado inválido. Estados válidos: PENDING, ARRIVED, COMPLETED"
        )

    updated_stop = update_stop_status(
        session, stop_id, new_status, current_user.id)

    return {
        "message": f"Estado de parada actualizado a {new_status}",
        "stop": {
            "id": str(updated_stop.id),
            "stop_order": updated_stop.stop_order,
            "stop_type": updated_stop.stop_type,
            "status": updated_stop.status,
            "description": updated_stop.description
        }
    }


@router.get(
    "/{client_request_id}/progress",
    status_code=200,
    description="""
Propósito: Permite consultar el progreso general del viaje, mostrando cuántas paradas han sido completadas y cuál es la siguiente.

**Permisos de Acceso:**
- El cliente que creó el viaje o el conductor asignado pueden consultar el progreso.

**Parámetros:**
- `client_request_id`: ID del viaje.

**Respuesta:**
Devuelve el total de paradas, cuántas han sido completadas, cuántas faltan y la parada actual.
"""
)
async def get_trip_progress_info(
    client_request_id: UUID,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene el progreso del viaje (paradas completadas vs total).
    """
    # Verificar permisos
    from app.models.client_request import ClientRequest
    client_request = session.get(ClientRequest, client_request_id)
    if not client_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud de viaje no encontrada"
        )

    if client_request.id_client != current_user.id and client_request.id_driver_assigned != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver el progreso de este viaje"
        )

    progress = get_trip_progress(session, client_request_id)

    # Convertir current_stop a dict si existe
    if progress.get("current_stop"):
        current_stop = progress["current_stop"]
        progress["current_stop"] = {
            "id": str(current_stop.id),
            "stop_order": current_stop.stop_order,
            "stop_type": current_stop.stop_type,
            "status": current_stop.status,
            "description": current_stop.description
        }

    return progress
