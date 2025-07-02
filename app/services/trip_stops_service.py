from sqlmodel import Session, select
from app.models.trip_stop import TripStop, TripStopCreate, TripStopUpdate, StopType, StopStatus
from app.models.client_request import ClientRequest
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from uuid import UUID
from typing import List, Optional
from fastapi import HTTPException, status
from datetime import datetime
import pytz
from app.utils.geo_utils import wkb_to_coords

COLOMBIA_TZ = pytz.timezone("America/Bogota")


def create_trip_stops_for_request(
    session: Session,
    client_request_id: UUID,
    pickup_lat: float,
    pickup_lng: float,
    destination_lat: float,
    destination_lng: float,
    pickup_description: Optional[str] = None,
    destination_description: Optional[str] = None,
    intermediate_stops: Optional[List[dict]] = None
) -> List[TripStop]:
    """
    Crea las paradas para una solicitud de viaje.
    """
    stops = []
    stop_order = 1

    # 1. Crear parada de recogida (PICKUP)
    pickup_position = from_shape(Point(pickup_lng, pickup_lat), srid=4326)
    pickup_stop = TripStop(
        client_request_id=client_request_id,
        stop_order=stop_order,
        stop_type=StopType.PICKUP,
        status=StopStatus.PENDING,
        latitude=pickup_lat,
        longitude=pickup_lng,
        position=pickup_position,
        description=pickup_description or "Punto de recogida"
    )
    session.add(pickup_stop)
    stops.append(pickup_stop)
    stop_order += 1

    # 2. Crear paradas intermedias (si existen)
    if intermediate_stops:
        for stop_data in intermediate_stops:
            lat = stop_data.get("latitude")
            lng = stop_data.get("longitude")
            description = stop_data.get("description", f"Parada {stop_order}")

            if lat is None or lng is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Parada {stop_order}: latitude y longitude son requeridos"
                )

            position = from_shape(Point(lng, lat), srid=4326)
            intermediate_stop = TripStop(
                client_request_id=client_request_id,
                stop_order=stop_order,
                stop_type=StopType.INTERMEDIATE,
                status=StopStatus.PENDING,
                latitude=lat,
                longitude=lng,
                position=position,
                description=description
            )
            session.add(intermediate_stop)
            stops.append(intermediate_stop)
            stop_order += 1

    # 3. Crear parada de destino (DESTINATION)
    destination_position = from_shape(
        Point(destination_lng, destination_lat), srid=4326)
    destination_stop = TripStop(
        client_request_id=client_request_id,
        stop_order=stop_order,
        stop_type=StopType.DESTINATION,
        status=StopStatus.PENDING,
        latitude=destination_lat,
        longitude=destination_lng,
        position=destination_position,
        description=destination_description or "Destino final"
    )
    session.add(destination_stop)
    stops.append(destination_stop)

    session.commit()

    # Refresh todos los objetos
    for stop in stops:
        session.refresh(stop)

    return stops


def get_trip_stops(session: Session, client_request_id: UUID) -> List[TripStop]:
    """
    Obtiene todas las paradas de un viaje ordenadas por stop_order
    """
    statement = select(TripStop).where(
        TripStop.client_request_id == client_request_id
    ).order_by(TripStop.stop_order.asc())

    stops = session.exec(statement).all()
    return stops


def get_current_stop(session: Session, client_request_id: UUID) -> Optional[TripStop]:
    """
    Obtiene la parada actual (la primera con status PENDING)
    """
    statement = select(TripStop).where(
        TripStop.client_request_id == client_request_id,
        TripStop.status == StopStatus.PENDING
    ).order_by(TripStop.stop_order.asc()).limit(1)

    current_stop = session.exec(statement).first()
    return current_stop


def update_stop_status(
    session: Session,
    stop_id: UUID,
    status: StopStatus,
    user_id: UUID
) -> TripStop:
    """
    Actualiza el estado de una parada específica
    """
    stop = session.get(TripStop, stop_id)
    if not stop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parada no encontrada"
        )

    # Verificar que el usuario es el conductor asignado
    client_request = session.get(ClientRequest, stop.client_request_id)
    if not client_request or client_request.id_driver_assigned != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para actualizar esta parada"
        )

    # Actualizar estado
    stop.status = status
    stop.updated_at = datetime.now(COLOMBIA_TZ)

    session.commit()
    session.refresh(stop)

    return stop


def get_trip_progress(session: Session, client_request_id: UUID) -> dict:
    """
    Obtiene el progreso del viaje (paradas completadas vs total)
    """
    stops = get_trip_stops(session, client_request_id)
    total_stops = len(stops)
    completed_stops = len(
        [s for s in stops if s.status == StopStatus.COMPLETED])
    current_stop = get_current_stop(session, client_request_id)

    return {
        "total_stops": total_stops,
        "completed_stops": completed_stops,
        "pending_stops": total_stops - completed_stops,
        "progress_percentage": (completed_stops / total_stops * 100) if total_stops > 0 else 0,
        "current_stop": current_stop,
        "is_completed": completed_stops == total_stops
    }
