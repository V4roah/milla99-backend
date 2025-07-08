from decimal import Decimal
from sqlalchemy.orm import Session
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from app.models.client_request import ClientRequest, ClientRequestCreate, StatusEnum
from app.models.driver_cancellation import DriverCancellation
from app.models.penality_user import PenalityUser, statusEnum
from app.models.project_settings import ProjectSettings
from app.models.user import User
from sqlalchemy import func, text
from geoalchemy2.functions import ST_Distance_Sphere
from datetime import datetime, timedelta, timezone
import requests
from fastapi import HTTPException, status
from app.core.config import settings
from app.models.user_has_roles import UserHasRole, RoleStatus
from app.models.driver_info import DriverInfo
from app.models.vehicle_info import VehicleInfo
from app.models.driver_position import DriverPosition
from app.services.driver_trip_offer_service import get_average_rating
from sqlalchemy.orm import selectinload
import traceback
from app.utils.geo_utils import wkb_to_coords, get_address_from_coords, get_time_and_distance_from_google
from app.models.type_service import TypeService
from uuid import UUID
from typing import Dict, Set, Optional, List
from app.models.payment_method import PaymentMethod
from app.services.transaction_service import TransactionService
from app.models.transaction import TransactionType
from app.services.notification_service import NotificationService
from app.services.driver_search_service import DriverSearchService
import logging
import pytz
from app.services.config_service_value_service import ConfigServiceValueService

logger = logging.getLogger(__name__)

COLOMBIA_TZ = pytz.timezone("America/Bogota")


def create_client_request(db: Session, data: ClientRequestCreate, id_client: UUID):
    pickup_point = from_shape(
        Point(data.pickup_lng, data.pickup_lat), srid=4326)
    destination_point = from_shape(
        Point(data.destination_lng, data.destination_lat), srid=4326)
    db_obj = ClientRequest(
        id_client=id_client,
        fare_offered=data.fare_offered,
        fare_assigned=data.fare_assigned,
        pickup_description=data.pickup_description,
        destination_description=data.destination_description,
        client_rating=data.client_rating,
        driver_rating=data.driver_rating,
        pickup_position=pickup_point,
        destination_position=destination_point,
        type_service_id=data.type_service_id,
        payment_method_id=data.payment_method_id
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    # Crear las paradas del viaje
    from app.services.trip_stops_service import create_trip_stops_for_request
    create_trip_stops_for_request(
        session=db,
        client_request_id=db_obj.id,
        pickup_lat=data.pickup_lat,
        pickup_lng=data.pickup_lng,
        destination_lat=data.destination_lat,
        destination_lng=data.destination_lng,
        pickup_description=data.pickup_description,
        destination_description=data.destination_description,
        intermediate_stops=data.intermediate_stops
    )

    return db_obj


def get_time_and_distance_service(origin_lat, origin_lng, destination_lat, destination_lng):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": f"{origin_lat},{origin_lng}",
        "destinations": f"{destination_lat},{destination_lng}",
        "units": "metric",
        "key": settings.GOOGLE_API_KEY
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"Error en el API de Google Distance Matrix: {response.status_code}")
    data = response.json()
    if data.get("status") != "OK":
        raise HTTPException(status_code=status.HTTP_200_OK,
                            detail=f"Error en la respuesta del API de Google Distance Matrix: {data.get('status')}")
    return data


async def get_nearby_client_requests_service(driver_lat, driver_lng, session: Session, wkb_to_coords, type_service_ids=None):
    print(
        f"\n[DEBUG] Calculando distancias para conductor en lat={driver_lat}, lng={driver_lng}")
    driver_point = func.ST_GeomFromText(
        f'POINT({driver_lng} {driver_lat})', 4326)

    # Obtener el timeout de project_settings
    project_settings = session.query(ProjectSettings).first()
    timeout_minutes = project_settings.request_timeout_minutes if project_settings else 5

    time_limit = datetime.now(COLOMBIA_TZ) - timedelta(minutes=timeout_minutes)
    distance_limit = 4000
    print(
        f"[DEBUG] Límite de distancia configurado: {distance_limit} metros (1.35km)")

    base_query = (
        session.query(
            ClientRequest,
            User.full_name,
            User.country_code,
            User.phone_number,
            TypeService.name.label("type_service_name"),
            ST_Distance_Sphere(ClientRequest.pickup_position,
                               driver_point).label("distance"),
            func.timestampdiff(
                text('MINUTE'),
                ClientRequest.created_at,
                func.now()  # Hora local del servidor MySQL
            ).label("time_difference")
        )
        .join(User, User.id == ClientRequest.id_client)
        .join(TypeService, TypeService.id == ClientRequest.type_service_id)
        .filter(
            ClientRequest.status == "CREATED",
            ClientRequest.created_at > time_limit
        )
    )
    if type_service_ids:
        base_query = base_query.filter(
            ClientRequest.type_service_id.in_(type_service_ids))

    print(f"[DEBUG] Query SQL: {str(base_query)}")

    base_query = base_query.having(text(f"distance < {distance_limit}"))
    results = []
    query_results = base_query.all()

    print(f"\n[DEBUG] Resultados encontrados: {len(query_results)}")
    for row in query_results:
        cr, full_name, country_code, phone_number, type_service_name, distance, time_difference = row
        pickup_coords = wkb_to_coords(cr.pickup_position)
        destination_coords = wkb_to_coords(cr.destination_position)

        # Obtener direcciones desde coordenadas
        pickup_address = get_address_from_coords(
            pickup_coords['lat'], pickup_coords['lng']) if pickup_coords else "No disponible"
        destination_address = get_address_from_coords(
            destination_coords['lat'], destination_coords['lng']) if destination_coords else "No disponible"

        # Obtener método de pago
        payment_method_obj = None
        if cr.payment_method_id:
            payment_method_obj = session.query(PaymentMethod).filter(
                PaymentMethod.id == cr.payment_method_id).first()
        payment_method = None
        if payment_method_obj:
            payment_method = {
                "id": payment_method_obj.id,
                "name": payment_method_obj.name
            }

        # Calcular distancia y tiempo del trayecto del cliente (origen -> destino)
        distance_trip = None
        duration_trip = None
        distance_trip_text = None
        duration_trip_text = None
        fair_price = None  # Precio justo a calcular
        if pickup_coords and destination_coords:
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            params = {
                "origins": f"{pickup_coords['lat']},{pickup_coords['lng']}",
                "destinations": f"{destination_coords['lat']},{destination_coords['lng']}",
                "units": "metric",
                "key": settings.GOOGLE_API_KEY,
                "mode": "driving"
            }
            try:
                response = requests.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "OK" and data["rows"][0]["elements"][0]["status"] == "OK":
                        element = data["rows"][0]["elements"][0]
                        distance_trip = element["distance"]["value"]
                        duration_trip = element["duration"]["value"]
                        distance_trip_text = element["distance"]["text"]
                        duration_trip_text = element["duration"]["text"]
                        # Calcular el precio justo usando la configuración y Google Distance Matrix
                        try:
                            config_service = ConfigServiceValueService(session)
                            # Comentario: Calcula el precio justo para el tipo de servicio de la solicitud
                            fair_price_response = await config_service.calculate_total_value(
                                cr.type_service_id, {"rows": [{"elements": [element]}],
                                                     "destination_addresses": [destination_address],
                                                     "origin_addresses": [pickup_address]}
                            )
                            if fair_price_response:
                                fair_price = fair_price_response.recommended_value
                        except Exception as e:
                            print(
                                f"[ERROR] No se pudo calcular el precio justo: {e}")
            except Exception as e:
                print(
                    f"[ERROR] Google Distance Matrix (trayecto cliente): {e}")

        average_rating = get_average_rating(
            session, "passenger", cr.id_client) if cr.id_client else 0.0
        result = {
            "id": str(cr.id),
            "id_client": str(cr.id_client),
            "fare_offered": cr.fare_offered,
            "fair_price": int(fair_price) if fair_price is not None else None,
            "pickup_description": cr.pickup_description,
            "destination_description": cr.destination_description,
            "status": cr.status,
            "updated_at": cr.updated_at.isoformat(),
            "pickup_position": pickup_coords,
            "destination_position": destination_coords,
            "pickup_address": pickup_address,
            "destination_address": destination_address,
            "distance": float(distance) if distance is not None else None,
            "time_difference": int(time_difference) if time_difference is not None else None,
            "type_service": {
                "id": cr.type_service_id,
                "name": type_service_name
            },
            "client": {
                "full_name": full_name,
                "country_code": country_code,
                "phone_number": phone_number,
                "average_rating": average_rating
            },
            "payment_method": payment_method,
            "distance_trip": distance_trip,
            "duration_trip": duration_trip,
            "distance_trip_text": distance_trip_text,
            "duration_trip_text": duration_trip_text
        }
        results.append(result)
    return results


def assign_driver_service(session: Session, id: UUID, id_driver_assigned: UUID, fare_assigned: float = None):
    # Validación: El conductor debe tener el rol DRIVER y status APPROVED
    try:
        user_role = session.query(UserHasRole).filter(
            UserHasRole.id_user == id_driver_assigned,
            UserHasRole.id_rol == "DRIVER"
        ).first()

        print("DEBUG user_role:", user_role)
        if user_role:
            print("DEBUG user_role.status:", user_role.status)

        if not user_role or user_role.status != RoleStatus.APPROVED:
            print("DEBUG: No tiene rol DRIVER aprobado")
            raise HTTPException(
                status_code=400,
                detail="El usuario no tiene el rol de conductor aprobado. No se puede asignar como conductor."
            )
        client_request = session.query(ClientRequest).filter(
            ClientRequest.id == id).first()
        if not client_request:
            raise HTTPException(
                status_code=404, detail="Solicitud no encontrada")
        client_request.id_driver_assigned = id_driver_assigned
        client_request.status = "ACCEPTED"
        client_request.updated_at = datetime.utcnow()
        if fare_assigned is not None:
            client_request.fare_assigned = fare_assigned
        session.commit()

        # Enviar notificaciones después de asignar el conductor
        try:
            notification_service = NotificationService(session)

            # Notificar al cliente que se asignó un conductor
            client_notification = notification_service.notify_driver_assigned(
                request_id=id,
                driver_id=id_driver_assigned
            )
            logger.info(
                f"Notificación de conductor asignado enviada al cliente: {client_notification}")

            # Notificar al conductor que se le asignó un viaje
            driver_notification = notification_service.notify_trip_assigned(
                request_id=id,
                driver_id=id_driver_assigned
            )
            logger.info(
                f"Notificación de viaje asignado enviada al conductor: {driver_notification}")

        except Exception as e:
            logger.error(f"Error enviando notificaciones de asignación: {e}")
            # No fallar la asignación si fallan las notificaciones

        return {"success": True, "message": "Conductor asignado correctamente"}
    except Exception as e:
        print("TRACEBACK:")
        print(traceback.format_exc())
        raise


def update_status_service(session: Session, id_client_request: UUID, status: str):
    client_request = session.query(ClientRequest).filter(
        ClientRequest.id == id_client_request).first()
    if not client_request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    client_request.status = status
    client_request.updated_at = datetime.utcnow()
    session.commit()
    return {"success": True, "message": "Status actualizado correctamente"}


def get_client_request_detail_service(session: Session, client_request_id: UUID, user_id: UUID = None):
    """
    Devuelve el detalle de una Client Request, incluyendo info de usuario, driver y vehículo si aplica.
    Solo permite acceso al cliente dueño de la solicitud o al conductor asignado.
    """
    from app.models.user import User
    from app.models.client_request import ClientRequest

    # Buscar la solicitud
    cr = session.query(ClientRequest).filter(
        ClientRequest.id == client_request_id).first()
    if not cr:
        raise HTTPException(
            status_code=404, detail="Client Request no encontrada")

    # Validar que el usuario tenga permiso para ver esta solicitud
    if cr.id_client != user_id and cr.id_driver_assigned != user_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para ver esta solicitud. Solo el cliente o el conductor asignado pueden verla."
        )

    try:
        # Buscar el usuario que la creó
        user = session.query(User).filter(User.id == cr.id_client).first()
        average_rating = get_average_rating(
            session, "passenger", user.id) if user else 0.0
        client_data = {
            "id": user.id,
            "full_name": user.full_name,
            "phone_number": user.phone_number,
            "country_code": user.country_code,
            "average_rating": average_rating
        } if user else None

        # Buscar info del conductor asignado (si existe)
        driver_info = None
        vehicle_info = None
        if cr.id_driver_assigned:
            driver = session.query(User).filter(
                User.id == cr.id_driver_assigned).first()
            if driver and driver.driver_info:
                average_rating = get_average_rating(
                    session, "driver", cr.id_driver_assigned) if cr.id_driver_assigned else 0.0
                di = driver.driver_info
                driver_info = {
                    "id": di.id,
                    "first_name": di.first_name,
                    "last_name": di.last_name,
                    "email": di.email,
                    "phone_number": driver.phone_number,
                    "country_code": driver.country_code,
                    "selfie_url": driver.selfie_url,
                    "average_rating": average_rating
                }
                if di.vehicle_info:
                    vi = di.vehicle_info
                    vehicle_info = {
                        "brand": vi.brand,
                        "model": vi.model,
                        "model_year": vi.model_year,
                        "color": vi.color,
                        "plate": vi.plate,
                        "vehicle_type_id": vi.vehicle_type_id
                    }

        # Buscar información del método de pago si existe
        payment_method = None
        if cr.payment_method_id:
            pm = session.query(PaymentMethod).filter(
                PaymentMethod.id == cr.payment_method_id).first()
            if pm:
                payment_method = {
                    "id": pm.id,
                    "name": pm.name
                }

        # Construir la respuesta completa
        response = {
            "id": cr.id,
            "status": str(cr.status),
            "fare_offered": cr.fare_offered,
            "fare_assigned": cr.fare_assigned,  # Aseguramos que fare_assigned esté incluido
            "pickup_description": cr.pickup_description,
            "destination_description": cr.destination_description,
            "created_at": cr.created_at.isoformat(),
            "updated_at": cr.updated_at.isoformat(),
            "client": client_data,
            "id_driver_assigned": cr.id_driver_assigned,
            "pickup_position": wkb_to_coords(cr.pickup_position),
            "destination_position": wkb_to_coords(cr.destination_position),
            "driver_info": driver_info,
            "vehicle_info": vehicle_info,
            "review": cr.review,
            "payment_method": payment_method,
            "type_service_id": cr.type_service_id,
            "client_rating": cr.client_rating,
            "driver_rating": cr.driver_rating
        }

        # Obtener el nombre del tipo de servicio
        type_service = session.query(TypeService).filter(
            TypeService.id == cr.type_service_id).first()
        if type_service:
            response["type_service_name"] = type_service.name

        # Obtener las paradas del viaje
        from app.services.trip_stops_service import get_trip_stops, get_trip_progress
        trip_stops = get_trip_stops(session, cr.id)
        trip_progress = get_trip_progress(session, cr.id)

        # Convertir paradas a formato JSON
        stops_data = []
        for stop in trip_stops:
            stops_data.append({
                "id": str(stop.id),
                "stop_order": stop.stop_order,
                "stop_type": stop.stop_type,
                "status": stop.status,
                "latitude": stop.latitude,
                "longitude": stop.longitude,
                "description": stop.description,
                "position": wkb_to_coords(stop.position) if stop.position else None
            })

        response["trip_stops"] = stops_data
        response["trip_progress"] = trip_progress

        # Serializar current_stop en trip_progress
        if trip_progress.get("current_stop"):
            stop = trip_progress["current_stop"]
            trip_progress["current_stop"] = {
                "id": str(stop.id),
                "stop_order": stop.stop_order,
                "stop_type": stop.stop_type,
                "status": stop.status,
                "latitude": stop.latitude,
                "longitude": stop.longitude,
                "description": stop.description,
                "position": wkb_to_coords(stop.position) if stop.position else None
            }

        return response
    except Exception as e:
        print("ERROR EN SERIALIZACION DE CLIENT REQUEST")
        traceback.print_exc()
        raise


def get_client_requests_by_status_service(session: Session, status: str, user_id: UUID):
    """
    Devuelve una lista de client_request filtrados por el estatus enviado en el parámetro y el user_id.
    Solo devuelve las solicitudes del usuario autenticado.
    Incluye información del conductor asignado para el historial.
    """
    from app.models.client_request import ClientRequest
    from app.models.payment_method import PaymentMethod
    from app.models.user import User

    # Obtener las solicitudes con sus métodos de pago
    results = session.query(ClientRequest).filter(
        ClientRequest.status == status,
        ClientRequest.id_client == user_id  # Filtrar por el usuario autenticado
    ).all()

    # Crear un diccionario de métodos de pago para evitar múltiples consultas
    payment_methods = {}
    for cr in results:
        if cr.payment_method_id and cr.payment_method_id not in payment_methods:
            pm = session.query(PaymentMethod).filter(
                PaymentMethod.id == cr.payment_method_id).first()
            if pm:
                payment_methods[cr.payment_method_id] = {
                    "id": pm.id,
                    "name": pm.name
                }

    # Crear un diccionario de conductores para evitar múltiples consultas
    drivers = {}
    for cr in results:
        if cr.id_driver_assigned and cr.id_driver_assigned not in drivers:
            driver = session.query(User).filter(
                User.id == cr.id_driver_assigned).first()
            if driver:
                drivers[cr.id_driver_assigned] = {
                    "id": str(driver.id),
                    "full_name": driver.full_name,
                    "phone_number": driver.phone_number,
                    "country_code": driver.country_code,
                    "selfie_url": driver.selfie_url
                }

    # Construir la respuesta
    response_list = []
    for cr in results:
        pickup_coords = wkb_to_coords(cr.pickup_position)
        destination_coords = wkb_to_coords(cr.destination_position)

        # Obtener direcciones desde coordenadas
        pickup_address = get_address_from_coords(
            pickup_coords['lat'], pickup_coords['lng']) if pickup_coords else "No disponible"
        destination_address = get_address_from_coords(
            destination_coords['lat'], destination_coords['lng']) if destination_coords else "No disponible"

        response_list.append({
            "id": cr.id,
            "id_client": cr.id_client,
            "id_driver_assigned": cr.id_driver_assigned,
            "fare_offered": cr.fare_offered,
            "fare_assigned": cr.fare_assigned,
            "pickup_description": cr.pickup_description,
            "destination_description": cr.destination_description,
            "client_rating": cr.client_rating,
            "driver_rating": cr.driver_rating,
            "status": str(cr.status),
            "pickup_position": pickup_coords,
            "destination_position": destination_coords,
            "pickup_address": pickup_address,
            "destination_address": destination_address,
            "created_at": cr.created_at.isoformat(),
            "updated_at": cr.updated_at.isoformat(),
            "review": cr.review,
            "payment_method": payment_methods.get(cr.payment_method_id) if cr.payment_method_id else None,
            "driver": drivers.get(cr.id_driver_assigned) if cr.id_driver_assigned else None
        })
    return response_list


def get_driver_requests_by_status_service(session: Session, id_driver_assigned: str, status: str):
    """
    Devuelve una lista de solicitudes de viaje asociadas a un conductor filtradas por el estado.
    Incluye información del cliente para el historial del conductor.
    """
    from app.models.client_request import ClientRequest
    from app.models.user import User

    # Consulta las solicitudes
    results = session.query(ClientRequest).filter(
        ClientRequest.id_driver_assigned == id_driver_assigned,
        ClientRequest.status == status
    ).all()

    # Crear un diccionario de clientes para evitar múltiples consultas
    clients = {}
    for cr in results:
        if cr.id_client and cr.id_client not in clients:
            client = session.query(User).filter(
                User.id == cr.id_client).first()
            if client:
                clients[cr.id_client] = {
                    "id": str(client.id),
                    "full_name": client.full_name,
                    "selfie_url": client.selfie_url
                }

    # Construir la respuesta con conversión de campos geoespaciales
    response_list = []
    for cr in results:
        pickup_coords = wkb_to_coords(cr.pickup_position)
        destination_coords = wkb_to_coords(cr.destination_position)

        # Obtener direcciones desde coordenadas
        pickup_address = get_address_from_coords(
            pickup_coords['lat'], pickup_coords['lng']) if pickup_coords else "No disponible"
        destination_address = get_address_from_coords(
            destination_coords['lat'], destination_coords['lng']) if destination_coords else "No disponible"

        response_list.append({
            "id": cr.id,
            "id_client": cr.id_client,
            "id_driver_assigned": cr.id_driver_assigned,
            "fare_offered": cr.fare_offered,
            "fare_assigned": cr.fare_assigned,
            "pickup_description": cr.pickup_description,
            "destination_description": cr.destination_description,
            "client_rating": cr.client_rating,
            "driver_rating": cr.driver_rating,
            "status": str(cr.status),
            "pickup_position": pickup_coords,
            "destination_position": destination_coords,
            "pickup_address": pickup_address,
            "destination_address": destination_address,
            "created_at": cr.created_at.isoformat(),
            "updated_at": cr.updated_at.isoformat(),
            "review": cr.review,
            "client": clients.get(cr.id_client) if cr.id_client else None
        })
    return response_list


def update_client_rating_service(session: Session, id_client_request: UUID, client_rating: float, user_id: UUID):
    """
    Permite al conductor asignado calificar al cliente de una solicitud específica.

    Validaciones:
    1. La solicitud debe existir
    2. La solicitud debe estar en estado PAID
    3. El usuario debe ser el conductor asignado a esta solicitud específica
    4. La calificación debe estar entre 1 y 5
    5. No debe existir una calificación previa

    Args:
        session: Sesión de base de datos
        id_client_request: ID de la solicitud a calificar
        client_rating: Calificación a asignar (1-5)
        user_id: ID del usuario que intenta calificar (debe ser el conductor asignado)

    Returns:
        Mensaje de éxito si la calificación se actualiza correctamente

    Raises:
        HTTPException(404): Si la solicitud no existe
        HTTPException(400): Si la solicitud no está en estado PAID, la calificación está fuera de rango, o ya existe una calificación
        HTTPException(403): Si el usuario no es el conductor asignado a esta solicitud
    """
    # Validar rango de calificación
    if not (1 <= client_rating <= 5):
        raise HTTPException(
            status_code=400,
            detail="La calificación debe estar entre 1 y 5"
        )

    client_request = session.query(ClientRequest).filter(
        ClientRequest.id == id_client_request).first()
    if not client_request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    # Primero validar el estado
    if client_request.status != StatusEnum.PAID:
        raise HTTPException(
            status_code=400, detail="Solo se puede calificar cuando el viaje está PAID")

    # Luego validar que el usuario es el conductor asignado a esta solicitud específica
    if client_request.id_driver_assigned != user_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para calificar esta solicitud. Solo el conductor asignado a esta solicitud puede calificar al cliente."
        )

    # Validar que no exista una calificación previa
    if client_request.client_rating is not None:
        raise HTTPException(
            status_code=400,
            detail="Ya existe una calificación para este viaje"
        )

    client_request.client_rating = client_rating
    client_request.updated_at = datetime.utcnow()
    session.commit()
    return {"success": True, "message": "Calificación del cliente actualizada correctamente"}


def update_driver_rating_service(session: Session, id_client_request: UUID, driver_rating: float, user_id: UUID):
    """
    Permite al cliente calificar al conductor de una solicitud específica.

    Validaciones:
    1. La solicitud debe existir
    2. La solicitud debe estar en estado PAID
    3. El usuario debe ser el cliente que creó esta solicitud específica
    4. La calificación debe estar entre 1 y 5
    5. No debe existir una calificación previa

    Args:
        session: Sesión de base de datos
        id_client_request: ID de la solicitud a calificar
        driver_rating: Calificación a asignar (1-5)
        user_id: ID del usuario que intenta calificar (debe ser el cliente que creó la solicitud)

    Returns:
        Mensaje de éxito si la calificación se actualiza correctamente

    Raises:
        HTTPException(404): Si la solicitud no existe
        HTTPException(400): Si la solicitud no está en estado PAID, la calificación está fuera de rango, o ya existe una calificación
        HTTPException(403): Si el usuario no es el cliente que creó esta solicitud
    """
    # Validar rango de calificación
    if not (1 <= driver_rating <= 5):
        raise HTTPException(
            status_code=400,
            detail="La calificación debe estar entre 1 y 5"
        )

    client_request = session.query(ClientRequest).filter(
        ClientRequest.id == id_client_request).first()
    if not client_request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    # Primero validar el estado
    if client_request.status != StatusEnum.PAID:
        raise HTTPException(
            status_code=400, detail="Solo se puede calificar cuando el viaje está PAID")

    # Luego validar que el usuario es el cliente que creó esta solicitud específica
    if client_request.id_client != user_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para calificar esta solicitud. Solo el cliente que creó esta solicitud puede calificar al conductor."
        )

    # Validar que no exista una calificación previa
    if client_request.driver_rating is not None:
        raise HTTPException(
            status_code=400,
            detail="Ya existe una calificación para este viaje"
        )

    client_request.driver_rating = driver_rating
    client_request.updated_at = datetime.utcnow()
    session.commit()
    return {"success": True, "message": "Calificación del conductor actualizada correctamente"}


def assign_driver(self, client_request_id: UUID, driver_id: UUID):
    """Asigna un conductor a una solicitud de cliente"""
    client_request = self.session.query(ClientRequest).filter(
        ClientRequest.id == client_request_id
    ).first()

    if not client_request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    if client_request.id_driver_assigned:
        raise HTTPException(
            status_code=400, detail="La solicitud ya tiene un conductor asignado")

    # Verificar que el usuario es un conductor
    driver = self.session.query(User).filter(
        User.id == driver_id,
        User.role == "DRIVER"
    ).first()

    if not driver:
        raise HTTPException(
            status_code=400, detail="El usuario no es un conductor")

    # Verificar que el conductor tiene un vehículo del tipo correcto
    driver_vehicle = self.session.query(VehicleInfo).filter(
        VehicleInfo.user_id == driver_id,
        VehicleInfo.vehicle_type_id == client_request.type_service.vehicle_type_id
    ).first()

    if not driver_vehicle:
        raise HTTPException(
            status_code=400,
            detail="El conductor no tiene un vehículo del tipo requerido para este servicio"
        )

    client_request.id_driver_assigned = driver_id
    client_request.status = StatusEnum.ACCEPTED
    self.session.add(client_request)
    self.session.commit()
    self.session.refresh(client_request)
    return client_request


def get_nearby_requests(self, driver_id: UUID, lat: float, lng: float, max_distance: float = 5.0):
    """Obtiene las solicitudes cercanas al conductor, filtrando por tipo de servicio"""
    # Obtener el vehículo del conductor
    driver_vehicle = self.session.query(VehicleInfo).filter(
        VehicleInfo.user_id == driver_id
    ).first()

    if not driver_vehicle:
        raise HTTPException(
            status_code=400,
            detail="El conductor no tiene un vehículo registrado"
        )

    # Obtener el tipo de servicio que puede manejar el conductor
    type_services = self.session.query(TypeService).filter(
        TypeService.vehicle_type_id == driver_vehicle.vehicle_type_id
    ).all()

    if not type_services:
        raise HTTPException(
            status_code=400,
            detail="No hay servicios disponibles para el tipo de vehículo del conductor"
        )

    type_service_ids = [ts.id for ts in type_services]

    # Obtener las solicitudes cercanas del tipo de servicio correspondiente
    nearby_requests = self.session.query(ClientRequest).filter(
        ClientRequest.status == StatusEnum.CREATED,
        ClientRequest.type_service_id.in_(type_service_ids),
        func.ST_Distance(
            func.ST_SetSRID(func.ST_MakePoint(
                ClientRequest.pickup_lng, ClientRequest.pickup_lat), 4326),
            func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)
        ) <= max_distance
    ).all()

    return nearby_requests


def get_nearby_drivers_service(
    client_lat: float,
    client_lng: float,
    type_service_id: int,
    session: Session,
    wkb_to_coords
) -> list:
    """
    Obtiene los conductores cercanos a un cliente en un radio de 5km.

    Args:
        client_lat: Latitud del cliente
        client_lng: Longitud del cliente
        type_service_id: ID del tipo de servicio solicitado
        session: Sesión de base de datos
        wkb_to_coords: Función para convertir WKB a coordenadas

    Returns:
        Lista de conductores cercanos con su información
    """
    try:
        # 1. Obtener el tipo de servicio para validar el tipo de vehículo
        type_service = session.query(TypeService).filter(
            TypeService.id == type_service_id
        ).first()

        if not type_service:
            raise HTTPException(
                status_code=404,
                detail="Tipo de servicio no encontrado"
            )

        # 2. Crear punto del cliente
        client_point = func.ST_GeomFromText(
            f'POINT({client_lng} {client_lat})', 4326)

        # 3. Consulta base para obtener conductores cercanos
        base_query = (
            session.query(
                User,
                DriverInfo,
                VehicleInfo,
                DriverPosition,
                ST_Distance_Sphere(DriverPosition.position,
                                   client_point).label("distance")
            )
            .join(UserHasRole, UserHasRole.id_user == User.id)
            .join(DriverInfo, DriverInfo.user_id == User.id)
            .join(VehicleInfo, VehicleInfo.driver_info_id == DriverInfo.id)
            .join(DriverPosition, DriverPosition.id_driver == User.id)
            .filter(
                UserHasRole.id_rol == "DRIVER",
                UserHasRole.status == RoleStatus.APPROVED,
                User.is_active == True,
                DriverPosition.position.isnot(None),
                VehicleInfo.vehicle_type_id == type_service.vehicle_type_id
            )
        )

        # 4. Filtrar por distancia (5km)
        distance_limit = 5000  # 5km en metros
        base_query = base_query.having(text(f"distance < {distance_limit}"))

        # 5. Ejecutar consulta
        results = []
        query_results = base_query.all()

        for row in query_results:
            user, driver_info, vehicle_info, driver_position, distance = row

            # Calcular calificación promedio del conductor
            avg_rating = session.query(
                func.avg(ClientRequest.driver_rating)
            ).filter(
                ClientRequest.id_driver_assigned == user.id,
                ClientRequest.driver_rating.isnot(None)
            ).scalar() or 0.0

            result = {
                "id": str(user.id),
                "driver_info": {
                    "id": str(driver_info.id),
                    "first_name": driver_info.first_name,
                    "last_name": driver_info.last_name,
                    "email": driver_info.email,
                    "selfie_url": user.selfie_url,
                    "current_position": wkb_to_coords(driver_position.position)
                },
                "vehicle_info": {
                    "id": str(vehicle_info.id),
                    "brand": vehicle_info.brand,
                    "model": vehicle_info.model,
                    "model_year": vehicle_info.model_year,
                    "color": vehicle_info.color,
                    "plate": vehicle_info.plate,
                    "vehicle_type_id": vehicle_info.vehicle_type_id
                },
                "distance": float(distance) if distance is not None else None,
                "rating": float(avg_rating),
                "phone_number": user.phone_number,
                "country_code": user.country_code
            }
            results.append(result)

        # 6. Obtener tiempos estimados de Google Distance Matrix
        if results:
            driver_positions = [
                f"{r['driver_info']['current_position']['lat']},{r['driver_info']['current_position']['lng']}"
                for r in results
            ]
            origins = '|'.join(driver_positions)
            destination = f"{client_lat},{client_lng}"

            url = 'https://maps.googleapis.com/maps/api/distancematrix/json'
            params = {
                'origins': origins,
                'destinations': destination,
                'units': 'metric',
                'key': settings.GOOGLE_API_KEY,
                'mode': 'driving'
            }

            response = requests.get(url, params=params)
            if response.status_code == 200:
                google_data = response.json()
                if google_data.get('status') == 'OK':
                    elements = google_data['rows']
                    for i, element in enumerate(elements):
                        if i < len(results):
                            results[i]['google_distance_matrix'] = element['elements'][0]

        return results

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"[ERROR] Exception en get_nearby_drivers_service: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al buscar conductores cercanos: {str(e)}"
        )


class ClientRequestStateMachine:
    """
    Máquina de estados para controlar las transiciones válidas en una solicitud de viaje.
    """
    # Estados que permiten cancelación
    CANCELLABLE_STATES = {StatusEnum.CREATED,
                          StatusEnum.ACCEPTED, StatusEnum.ON_THE_WAY,
                          StatusEnum.ARRIVED}

    # Transiciones permitidas por rol
    DRIVER_TRANSITIONS: Dict[StatusEnum, Set[StatusEnum]] = {
        StatusEnum.ACCEPTED: {StatusEnum.ON_THE_WAY},
        StatusEnum.ON_THE_WAY: {StatusEnum.ARRIVED},
        StatusEnum.ARRIVED: {StatusEnum.TRAVELLING},
        StatusEnum.TRAVELLING: {StatusEnum.FINISHED},
        StatusEnum.FINISHED: {StatusEnum.PAID}
    }

    CLIENT_TRANSITIONS: Dict[StatusEnum, Set[StatusEnum]] = {
        StatusEnum.CREATED: {StatusEnum.CANCELLED},
        StatusEnum.ACCEPTED: {StatusEnum.CANCELLED},
        StatusEnum.ON_THE_WAY: {StatusEnum.CANCELLED},
        # PAID solo se puede establecer después de un pago exitoso, no por cambio directo de estado
    }

    @classmethod
    def can_transition(cls, current_state: StatusEnum, new_state: StatusEnum, role: str) -> bool:
        """
        Verifica si la transición de estado es válida para el rol especificado.
        """
        # PAID ahora se permite desde FINISHED (para el rol DRIVER) (se quita la restricción anterior)

        # Si el nuevo estado es CANCELLED, verificar que el estado actual lo permita
        if new_state == StatusEnum.CANCELLED:
            return current_state in cls.CANCELLABLE_STATES

        # Obtener las transiciones permitidas según el rol
        allowed_transitions = cls.DRIVER_TRANSITIONS if role == "DRIVER" else cls.CLIENT_TRANSITIONS

        # Verificar si la transición está permitida
        return new_state in allowed_transitions.get(current_state, set())

    @classmethod
    def get_allowed_transitions(cls, current_state: StatusEnum, role: str) -> Set[StatusEnum]:
        """
        Retorna el conjunto de estados a los que se puede transicionar desde el estado actual.
        """
        transitions = cls.DRIVER_TRANSITIONS if role == "DRIVER" else cls.CLIENT_TRANSITIONS
        allowed = transitions.get(current_state, set())

        # Si el estado actual permite cancelación, agregar CANCELLED a las transiciones permitidas
        if current_state in cls.CANCELLABLE_STATES:
            allowed.add(StatusEnum.CANCELLED)

        return allowed


def update_status_by_driver_service(session: Session, id_client_request: int, status: str, user_id: int):
    """
    Permite al conductor cambiar el estado de la solicitud solo a los estados permitidos.
    """
    try:
        new_status = StatusEnum(status)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Estado inválido. Estados válidos: {[s.value for s in StatusEnum]}")

    # Validar rol del conductor
    user_role = session.query(UserHasRole).filter(
        UserHasRole.id_user == user_id,
        UserHasRole.id_rol == "DRIVER",
        UserHasRole.status == RoleStatus.APPROVED
    ).first()
    if not user_role:
        raise HTTPException(
            status_code=403, detail="Solo conductores aprobados pueden cambiar este estado")

    # Obtener la solicitud actual
    client_request = session.query(ClientRequest).filter(
        ClientRequest.id == id_client_request).first()
    if not client_request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    # Validar que el conductor asignado sea el que hace la petición
    if client_request.id_driver_assigned != user_id:
        raise HTTPException(
            status_code=403, detail="Solo el conductor asignado puede cambiar el estado de esta solicitud")

    # Validar la transición de estado
    if not ClientRequestStateMachine.can_transition(client_request.status, new_status, "DRIVER"):
        allowed = ClientRequestStateMachine.get_allowed_transitions(
            client_request.status, "DRIVER")
        raise HTTPException(
            status_code=400,
            detail=f"Transición de estado no permitida. Desde {client_request.status.value} solo se puede cambiar a: {', '.join(s.value for s in allowed)}"
        )

    # Validar que solo se pueda pasar a PAID si el estado actual es FINISHED
    if new_status == StatusEnum.PAID and client_request.status != StatusEnum.FINISHED:
        raise HTTPException(
            status_code=400,
            detail="Solo se puede pasar a PAID desde FINISHED"
        )

    try:
        client_request.status = new_status
        client_request.updated_at = datetime.utcnow()
        session.commit()

        # Enviar notificación al cliente sobre el cambio de estado
        try:
            notification_service = NotificationService(session)

            # Obtener tiempo estimado si es ON_THE_WAY (usar el tiempo de la oferta si existe)
            estimated_time = None
            if new_status == StatusEnum.ON_THE_WAY:
                # Buscar la oferta del conductor para obtener el tiempo estimado
                from app.models.driver_trip_offer import DriverTripOffer
                offer = session.query(DriverTripOffer).filter(
                    DriverTripOffer.id_client_request == id_client_request,
                    DriverTripOffer.id_driver == user_id
                ).first()
                if offer:
                    estimated_time = int(offer.time)

            notification_result = notification_service.notify_driver_status_change(
                request_id=id_client_request,
                status=new_status.value,
                estimated_time=estimated_time
            )
            logger.info(
                f"Notificación de cambio de estado enviada: {notification_result}")

        except Exception as e:
            logger.error(
                f"Error enviando notificación de cambio de estado: {e}")
            # No fallar el cambio de estado si falla la notificación

        return {"success": True, "message": "Status actualizado correctamente"}
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Error al actualizar el estado: {str(e)}")


def client_canceled_service(session: Session, id_client_request: UUID, user_id: UUID):
    """
    Permite al cliente (dueño de la solicitud) cancelar su solicitud (cambiando su estado a CANCELLED) 
    únicamente si la solicitud está en CREATED, ACCEPTED, ON_THE_WAY o ARRIVED.

    - En ON_THE_WAY: Aplica penalización monetaria (fine_one)
    - En ARRIVED: Aplica penalización monetaria (fine_two)
    - En CREATED/ACCEPTED: Sin penalización
    """
    # Validar rol del cliente (que sea CLIENT y esté aprobado)
    user_role = session.query(UserHasRole).filter(
        UserHasRole.id_user == user_id,
        UserHasRole.id_rol == "CLIENT",
        UserHasRole.status == RoleStatus.APPROVED
    ).first()
    if not user_role:
        raise HTTPException(
            status_code=403, detail="Solo clientes aprobados pueden cancelar su solicitud.")

    # Obtener la solicitud actual
    client_request = session.query(ClientRequest).filter(
        ClientRequest.id == id_client_request).first()
    if not client_request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    # Validar que el cliente sea el dueño de la solicitud
    if client_request.id_client != user_id:
        raise HTTPException(
            status_code=403, detail="Solo el cliente dueño de la solicitud puede cancelarla.")

    # Validar que la solicitud esté en un estado que permita cancelación
    if client_request.status not in ClientRequestStateMachine.CANCELLABLE_STATES:
        raise HTTPException(
            status_code=400,
            detail="La solicitud no se puede cancelar (solo se permite cancelar si está en CREATED, ACCEPTED, ON_THE_WAY o ARRIVED)."
        )

    # Obtener configuración del proyecto para las penalizaciones
    config = session.query(ProjectSettings).get(1)
    if not config:
        raise ValueError(
            "No se encontró la configuración del proyecto con ID 1")

    # Guardar el estado original para el mensaje
    original_status = client_request.status

    # Aplicar penalización según el estado
    if original_status == StatusEnum.ON_THE_WAY:
        # Crear registro de penalización
        penality = PenalityUser(
            id_user=client_request.id_client,
            id_client_request=client_request.id,
            id_driver_assigned=client_request.id_driver_assigned,
            amount=float(config.fine_one),
            status=statusEnum.PENDING,
        )
        session.add(penality)

        # Crear transacción de penalización
        transaction_service = TransactionService(session)
        transaction_service.create_transaction(
            user_id=client_request.id_client,
            expense=int(config.fine_one),
            type=TransactionType.PENALITY_DEDUCTION,
            client_request_id=client_request.id,
            description=f"Penalización por cancelación en ON_THE_WAY"
        )

    elif original_status == StatusEnum.ARRIVED:
        # Crear registro de penalización
        penality = PenalityUser(
            id_user=client_request.id_client,
            id_client_request=client_request.id,
            id_driver_assigned=client_request.id_driver_assigned,
            amount=float(config.fine_two),
            status=statusEnum.PENDING,
        )
        session.add(penality)

        # Crear transacción de penalización
        transaction_service = TransactionService(session)
        transaction_service.create_transaction(
            user_id=client_request.id_client,
            expense=int(config.fine_two),
            type=TransactionType.PENALITY_DEDUCTION,
            client_request_id=client_request.id,
            description=f"Penalización por cancelación en ARRIVED"
        )

    # Actualizar estado a CANCELLED
    client_request.status = StatusEnum.CANCELLED
    client_request.updated_at = datetime.utcnow()
    session.commit()

    # Enviar notificación al conductor si hay uno asignado
    if client_request.id_driver_assigned:
        try:
            notification_service = NotificationService(session)
            notification_result = notification_service.notify_trip_cancelled_by_client(
                request_id=id_client_request,
                driver_id=client_request.id_driver_assigned
            )
            logger.info(
                f"Notificación de cancelación por cliente enviada al conductor: {notification_result}")
        except Exception as e:
            logger.error(
                f"Error enviando notificación de cancelación por cliente: {e}")
            # No fallar la cancelación si falla la notificación

    # Mensaje según si hubo penalización (usando el estado original)
    if original_status in [StatusEnum.ON_THE_WAY, StatusEnum.ARRIVED]:
        amount = float(config.fine_one) if original_status == StatusEnum.ON_THE_WAY else float(
            config.fine_two)
        return {
            "success": True,
            "message": f"Solicitud cancelada. Se aplicará una penalización de {amount} pesos en su próximo servicio."
        }
    return {
        "success": True,
        "message": "Solicitud cancelada correctamente."
    }


def update_status_to_paid_service(session: Session, id_client_request: int, user_id: int):
    """
    Actualiza el estado de la solicitud a PAID después de un pago exitoso.
    Solo se puede cambiar a PAID desde FINISHED y solo por el cliente dueño de la solicitud.
    """
    # Validar rol del cliente
    user_role = session.query(UserHasRole).filter(
        UserHasRole.id_user == user_id,
        UserHasRole.id_rol == "CLIENT",
        UserHasRole.status == RoleStatus.APPROVED
    ).first()
    if not user_role:
        raise HTTPException(
            status_code=403, detail="Solo clientes aprobados pueden realizar pagos")

    # Obtener la solicitud actual
    client_request = session.query(ClientRequest).filter(
        ClientRequest.id == id_client_request).first()
    if not client_request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    # Validar que el cliente sea el dueño de la solicitud
    if client_request.id_client != user_id:
        raise HTTPException(
            status_code=403, detail="Solo el cliente dueño de la solicitud puede realizar el pago")

    # Validar que el estado actual sea FINISHED
    if client_request.status != StatusEnum.FINISHED:
        raise HTTPException(
            status_code=400,
            detail="Solo se puede realizar el pago cuando el viaje está FINISHED"
        )

    # Actualizar el estado a PAID
    client_request.status = StatusEnum.PAID
    client_request.updated_at = datetime.utcnow()
    session.commit()
    return {"success": True, "message": "Pago registrado correctamente"}


def update_review_service(session: Session, id_client_request: UUID, review: str, user_id: UUID):
    """
    Permite al cliente actualizar el review de una solicitud específica.

    Validaciones:
    1. La solicitud debe existir
    2. La solicitud debe estar en estado PAID
    3. El usuario debe ser el cliente que creó esta solicitud específica
    4. El review no debe exceder 255 caracteres

    Args:
        session: Sesión de base de datos
        id_client_request: ID de la solicitud a actualizar
        review: Review a asignar (máximo 255 caracteres)
        user_id: ID del usuario que intenta actualizar (debe ser el cliente que creó la solicitud)

    Returns:
        Mensaje de éxito si el review se actualiza correctamente

    Raises:
        HTTPException(404): Si la solicitud no existe
        HTTPException(400): Si la solicitud no está en estado PAID o el review excede el límite
        HTTPException(403): Si el usuario no es el cliente que creó esta solicitud
    """
    # Validar longitud del review
    if review and len(review) > 255:
        raise HTTPException(
            status_code=400,
            detail="El review no puede exceder los 255 caracteres"
        )

    client_request = session.query(ClientRequest).filter(
        ClientRequest.id == id_client_request).first()
    if not client_request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    # Validar que el estado sea PAID
    if client_request.status != StatusEnum.PAID:
        raise HTTPException(
            status_code=400, detail="Solo se puede agregar un review cuando el viaje está PAID")

    # Validar que el usuario es el cliente que creó esta solicitud
    if client_request.id_client != user_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para actualizar esta solicitud. Solo el cliente que creó esta solicitud puede agregar un review."
        )

    client_request.review = review
    client_request.updated_at = datetime.utcnow()
    session.commit()
    return {"success": True, "message": "Review actualizado correctamente"}


def driver_canceled_service(session: Session, id_client_request: UUID, user_id: UUID, reason: str | None = None):
    """
    Permite al conductor cancelar una solicitud de viaje. El conductor solo puede cancelar solicitudes que estén en estado 
    ACCEPTED, ON_THE_WAY o ARRIVED. 

    - En estados ACCEPTED y ON_THE_WAY:
        - Registra la cancelación
        - Verifica límites diarios (cancel_max_days) y semanales (cancel_max_weeks)
        - Aplica suspensión si excede límites
    - En estado ARRIVED:
        - Solo registra la cancelación
        - No aplica suspensión ni verifica límites

    Args:
        session: Sesión de base de datos
        id_client_request: ID de la solicitud de viaje a cancelar
        user_id: ID del conductor que intenta cancelar (obtenido del token)
        reason: Razón opcional de la cancelación

    Returns:
        Mensaje de éxito si la cancelación fue exitosa

    Raises:
        HTTPException(404): Si la solicitud no se encuentra
        HTTPException(403): Si el usuario no es el conductor asignado
        HTTPException(400): Si la solicitud no está en estado permitido
    """
    # Obtener la solicitud y validar que existe
    client_request = session.query(ClientRequest).filter(
        ClientRequest.id == id_client_request
    ).first()

    if not client_request:
        raise HTTPException(
            status_code=404,
            detail="Solicitud de viaje no encontrada o no tienes permiso para cancelarla."
        )

    # Validación explícita del conductor asignado
    if client_request.id_driver_assigned != user_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para cancelar esta solicitud."
        )

    # Validar que la solicitud está en estado permitido
    if client_request.status not in [StatusEnum.ARRIVED, StatusEnum.ACCEPTED, StatusEnum.ON_THE_WAY]:
        raise HTTPException(
            status_code=400,
            detail="Esta solicitud de viaje solo puede ser cancelada por el conductor cuando está en estado ARRIVED, ACCEPTED u ON_THE_WAY."
        )

    # Obtener configuración del proyecto
    config = session.query(ProjectSettings).get(1)
    if not config:
        raise ValueError(
            "No se encontró la configuración del proyecto con ID 1")

    # Registrar la cancelación
    record_driver_cancellation(session, user_id, id_client_request)
    session.commit()  # Hacer commit para que esté disponible para el conteo

    # Solo verificar límites y aplicar suspensión si está en ACCEPTED u ON_THE_WAY
    if client_request.status in [StatusEnum.ACCEPTED, StatusEnum.ON_THE_WAY]:
        # Eliminar cancelaciones antiguas y obtener conteos actuales
        delete_old_cancellations(session, user_id)
        cancel_day_count = get_daily_cancellation_count(session, user_id)
        cancel_week_count = get_weekly_cancellation_count(session, user_id)

        # Verificar si se debe aplicar suspensión
        if cancel_day_count >= config.cancel_max_days or cancel_week_count >= config.cancel_max_weeks:
            driver = session.query(UserHasRole).filter(
                UserHasRole.id_user == user_id,
                UserHasRole.id_rol == "DRIVER"
            ).first()
            if driver:
                driver.suspension = True
                driver.status = RoleStatus.PENDING
                session.commit()

            # Enviar notificación al cliente sobre la cancelación
            try:
                notification_service = NotificationService(session)
                notification_result = notification_service.notify_trip_cancelled_by_driver(
                    request_id=id_client_request,
                    reason=reason
                )
                logger.info(
                    f"Notificación de cancelación por conductor enviada al cliente: {notification_result}")
            except Exception as e:
                logger.error(
                    f"Error enviando notificación de cancelación por conductor: {e}")

            return {
                "success": True,
                "message": f"Solicitud de viaje cancelada exitosamente por el conductor. El conductor ha sido suspendido por {config.day_suspension} días al exceder el límite de cancelaciones.",
                "daily_cancellation_count": cancel_day_count,
                "weekly_cancellation_count": cancel_week_count
            }
        else:
            # Enviar notificación al cliente sobre la cancelación
            try:
                notification_service = NotificationService(session)
                notification_result = notification_service.notify_trip_cancelled_by_driver(
                    request_id=id_client_request,
                    reason=reason
                )
                logger.info(
                    f"Notificación de cancelación por conductor enviada al cliente: {notification_result}")
            except Exception as e:
                logger.error(
                    f"Error enviando notificación de cancelación por conductor: {e}")

            return {
                "success": True,
                "message": "Solicitud de viaje cancelada exitosamente por el conductor. Se ha registrado la cancelación.",
                "daily_cancellation_count": cancel_day_count,
                "weekly_cancellation_count": cancel_week_count
            }
    else:  # Estado ARRIVED
        # Actualizar estado a CANCELLED
        client_request.status = StatusEnum.CANCELLED
        client_request.updated_at = datetime.utcnow()
        session.commit()

        # Enviar notificación al cliente sobre la cancelación
        try:
            notification_service = NotificationService(session)
            notification_result = notification_service.notify_trip_cancelled_by_driver(
                request_id=id_client_request,
                reason=reason
            )
            logger.info(
                f"Notificación de cancelación por conductor enviada al cliente: {notification_result}")
        except Exception as e:
            logger.error(
                f"Error enviando notificación de cancelación por conductor: {e}")

        return {
            "success": True,
            "message": "Solicitud de viaje cancelada exitosamente por el conductor."
        }


def record_driver_cancellation(session: Session, driver_id: UUID, client_request_id: UUID):
    """
    Registra la cancelación del conductor en la tabla de registros.
    """
    print(
        f"DEBUG: record_driver_cancellation - driver_id: {driver_id}, client_request_id: {client_request_id}")

    cancellation_record = DriverCancellation(
        id_driver=driver_id,
        id_client_request=client_request_id
    )
    session.add(cancellation_record)
    print(
        f"DEBUG: record_driver_cancellation - cancellation_record created with cancelled_at: {cancellation_record.cancelled_at}")
    # No hacer flush aquí, el commit se hará después de registrar


def get_daily_cancellation_count(session: Session, driver_id: UUID) -> int:
    """
    Obtiene el número de cancelaciones hechas por un conductor en el día actual.
    """
    # Usar zona horaria de Colombia para la comparación
    today_start = datetime.now(COLOMBIA_TZ).replace(
        hour=0, minute=0, second=0, microsecond=0)

    # Debug: Imprimir información de la consulta
    print(f"DEBUG: get_daily_cancellation_count - driver_id: {driver_id}")
    print(f"DEBUG: get_daily_cancellation_count - today_start: {today_start}")

    # Obtener todos los registros para debug
    all_cancellations = session.query(DriverCancellation).filter(
        DriverCancellation.id_driver == driver_id
    ).all()
    print(
        f"DEBUG: get_daily_cancellation_count - total cancellations for driver: {len(all_cancellations)}")

    for cancellation in all_cancellations:
        print(
            f"DEBUG: Cancellation - id: {cancellation.id}, cancelled_at: {cancellation.cancelled_at}, tzinfo: {cancellation.cancelled_at.tzinfo}")

    # Consulta filtrada por fecha - manejar zona horaria
    daily_cancellations = []
    for cancellation in all_cancellations:
        # Si cancelled_at no tiene zona horaria, asumir que es hora local de Colombia
        cancelled_at = cancellation.cancelled_at
        if cancelled_at.tzinfo is None:
            cancelled_at = COLOMBIA_TZ.localize(cancelled_at)

        if cancelled_at >= today_start:
            daily_cancellations.append(cancellation)

    print(
        f"DEBUG: get_daily_cancellation_count - daily cancellations: {len(daily_cancellations)}")

    return len(daily_cancellations)


def get_weekly_cancellation_count(session: Session, driver_id: UUID) -> int:
    """
    Obtiene el número de cancelaciones hechas por un conductor en los últimos 7 días.
    """
    seven_days_ago = datetime.now(COLOMBIA_TZ) - timedelta(days=7)

    # Obtener todas las cancelaciones del conductor
    all_cancellations = session.query(DriverCancellation).filter(
        DriverCancellation.id_driver == driver_id
    ).all()

    # Filtrar por fecha - manejar zona horaria
    weekly_cancellations = []
    for cancellation in all_cancellations:
        # Si cancelled_at no tiene zona horaria, asumir que es hora local de Colombia
        cancelled_at = cancellation.cancelled_at
        if cancelled_at.tzinfo is None:
            cancelled_at = COLOMBIA_TZ.localize(cancelled_at)

        if cancelled_at >= seven_days_ago:
            weekly_cancellations.append(cancellation)

    return len(weekly_cancellations)


def delete_old_cancellations(session: Session, driver_id: UUID):
    """
    Elimina los registros de cancelación de un conductor que tienen más de 7 días.
    """
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    session.query(DriverCancellation).filter(
        DriverCancellation.id_driver == driver_id,
        DriverCancellation.cancelled_at < seven_days_ago
    ).delete(synchronize_session=False)
    session.commit()


def delete_all_cancellations(session: Session, driver_id: UUID):
    """
    Elimina todos los registros de cancelación de un conductor.
    """
    session.query(DriverCancellation).filter(
        DriverCancellation.id_driver == driver_id
    ).delete(synchronize_session=False)
    session.commit()


def check_and_lift_driver_suspension(session: Session, driver_id: UUID):
    """
    Verifica si ha transcurrido el tiempo de suspensión de un conductor y levanta la suspensión automáticamente.
    También elimina todos los registros de cancelación del conductor si se levanta la suspensión.

    Args:
        session: Sesión de base de datos
        driver_id: ID del conductor a verificar

    Returns:
        dict: Información sobre el estado de la suspensión
    """
    # Obtener la configuración del proyecto para los días de suspensión
    config = session.query(ProjectSettings).get(1)
    if not config:
        raise ValueError(
            "No se encontró la configuración del proyecto con ID 1")

    suspension_days = int(config.day_suspension)

    # Obtener el registro del conductor en user_has_role
    driver_role = session.query(UserHasRole).filter(
        UserHasRole.id_user == driver_id,
        UserHasRole.id_rol == "DRIVER"
    ).first()

    if not driver_role:
        return {
            "success": False,
            "message": "Conductor no encontrado"
        }

    # Si el conductor no está suspendido, no hay nada que hacer
    if not driver_role.suspension:
        return {
            "success": True,
            "message": "El conductor no está suspendido",
            "is_suspended": False
        }

    # Obtener la última cancelación del conductor (la más reciente)
    last_cancellation = session.query(DriverCancellation).filter(
        DriverCancellation.id_driver == driver_id
    ).order_by(DriverCancellation.cancelled_at.desc()).first()

    if not last_cancellation:
        # Si no hay cancelaciones pero está suspendido, levantar la suspensión
        driver_role.suspension = False
        driver_role.status = RoleStatus.APPROVED
        session.commit()
        return {
            "success": True,
            "message": "Suspensión levantada - no se encontraron cancelaciones",
            "is_suspended": False
        }

    # Calcular si han pasado los días de suspensión desde la última cancelación
    # Asegurar que cancelled_at tenga zona horaria UTC si no la tiene
    cancelled_at = last_cancellation.cancelled_at
    if cancelled_at.tzinfo is None:
        cancelled_at = cancelled_at.replace(tzinfo=timezone.utc)

    suspension_end_date = cancelled_at + timedelta(days=suspension_days)
    current_time = datetime.now(timezone.utc)

    if current_time >= suspension_end_date:
        # Ha transcurrido el tiempo de suspensión, levantar la suspensión
        driver_role.suspension = False
        driver_role.status = RoleStatus.APPROVED
        # Eliminar todos los registros de cancelación del conductor
        delete_all_cancellations(session, driver_id)

        session.commit()

        return {
            "success": True,
            "message": f"Suspensión levantada automáticamente. Han transcurrido {suspension_days} días desde la última cancelación",
            "is_suspended": False,
            "suspension_lifted_at": current_time.isoformat(),
            "last_cancellation_date": cancelled_at.isoformat()
        }
    else:
        # Aún no ha transcurrido el tiempo de suspensión
        remaining_time = suspension_end_date - current_time
        remaining_days = remaining_time.days
        remaining_hours = remaining_time.seconds // 3600

        return {
            "success": True,
            "message": f"El conductor aún está suspendido. Tiempo restante: {remaining_days} días y {remaining_hours} horas",
            "is_suspended": True,
            "suspension_end_date": suspension_end_date.isoformat(),
            "remaining_days": remaining_days,
            "remaining_hours": remaining_hours
        }


def get_busy_driver_config(session: Session) -> Dict[str, float]:
    """
    Obtiene la configuración para conductores ocupados desde project_settings
    """
    settings = session.query(ProjectSettings).first()
    if not settings:
        # Valores por defecto si no hay configuración
        return {
            "max_wait_time": 15.0,
            "max_distance": 2.0,
            "max_transit_time": 5.0
        }

    return {
        "max_wait_time": settings.max_wait_time_for_busy_driver or 15.0,
        "max_distance": settings.max_distance_for_busy_driver or 2.0,
        "max_transit_time": settings.max_transit_time_for_busy_driver or 5.0
    }


def find_optimal_drivers(
    session: Session,
    client_lat: float,
    client_lng: float,
    type_service_id: int,
    max_distance: float = 5.0
) -> List[Dict]:
    """
    Busca conductores óptimos incluyendo conductores ocupados
    """
    config = get_busy_driver_config(session)

    # Buscar conductores disponibles (PRIORIDAD 1)
    available_drivers = find_available_drivers(
        session, client_lat, client_lng, type_service_id, max_distance)

    # Buscar conductores ocupados (PRIORIDAD 2)
    busy_drivers = find_busy_drivers(
        session, client_lat, client_lng, type_service_id, config)

    # Combinar y ordenar por prioridad
    all_drivers = []

    # Agregar conductores disponibles con prioridad 1
    for driver in available_drivers:
        driver["priority"] = 1
        driver["type"] = "available"
        all_drivers.append(driver)

    # Agregar conductores ocupados con prioridad 2
    for driver in busy_drivers:
        driver["priority"] = 2
        driver["type"] = "busy"
        all_drivers.append(driver)

    # Ordenar por prioridad y tiempo estimado
    all_drivers.sort(key=lambda x: (
        x["priority"], x.get("estimated_time", float('inf'))))

    return all_drivers


def find_optimal_drivers_with_search_service(
    session: Session,
    client_lat: float,
    client_lng: float,
    type_service_id: int,
    max_distance: float = 5.0
) -> List[Dict]:
    """
    Busca conductores óptimos usando el nuevo DriverSearchService
    """
    try:
        # Inicializar el servicio de búsqueda
        search_service = DriverSearchService(session)

        # Buscar conductores disponibles (PRIORIDAD 1)
        available_drivers = search_service.find_available_drivers(
            client_lat, client_lng, type_service_id
        )

        # Buscar conductores ocupados cercanos (PRIORIDAD 2)
        busy_drivers = search_service.find_nearby_busy_drivers(
            client_lat, client_lng, type_service_id
        )

        # Calcular prioridades para conductores disponibles
        available_drivers_with_priority = search_service.calculate_priorities(
            available_drivers, client_lat, client_lng
        )

        # Calcular prioridades para conductores ocupados
        busy_drivers_with_priority = search_service.calculate_priorities(
            busy_drivers, client_lat, client_lng
        )

        # Combinar y formatear resultados
        all_drivers = []

        # Agregar conductores disponibles con prioridad 1
        for driver_info in available_drivers_with_priority:
            driver = driver_info["driver"]
            all_drivers.append({
                "user_id": driver.user_id,
                "driver_info_id": driver.id,
                "full_name": driver.user.full_name if driver.user else "N/A",
                "phone_number": driver.user.phone_number if driver.user else "N/A",
                "distance": driver_info["distance"],
                "estimated_time": driver_info["estimated_time"],
                "priority_score": driver_info.get("priority_score", 0),
                "type": "available",
                "priority": 1,
                "vehicle_info": {
                    "brand": driver.vehicle_info.brand if driver.vehicle_info else "N/A",
                    "model": driver.vehicle_info.model if driver.vehicle_info else "N/A",
                    "plate": driver.vehicle_info.plate if driver.vehicle_info else "N/A"
                } if driver.vehicle_info else {}
            })

        # Agregar conductores ocupados con prioridad 2
        for driver_info in busy_drivers_with_priority:
            driver = driver_info["driver"]
            all_drivers.append({
                "user_id": driver.user_id,
                "driver_info_id": driver.id,
                "full_name": driver.user.full_name if driver.user else "N/A",
                "phone_number": driver.user.phone_number if driver.user else "N/A",
                "distance": driver_info["distance"],
                "estimated_time": driver_info["total_time"],
                "priority_score": driver_info.get("priority_score", 0),
                "type": "busy",
                "priority": 2,
                "total_time": driver_info["total_time"],
                "vehicle_info": {
                    "brand": driver.vehicle_info.brand if driver.vehicle_info else "N/A",
                    "model": driver.vehicle_info.model if driver.vehicle_info else "N/A",
                    "plate": driver.vehicle_info.plate if driver.vehicle_info else "N/A"
                } if driver.vehicle_info else {}
            })

        # Ordenar por prioridad y puntuación
        all_drivers.sort(key=lambda x: (
            x["priority"],
            -x.get("priority_score", 0),  # Mayor puntuación = mejor
            x.get("estimated_time", float('inf'))
        ))

        return all_drivers

    except Exception as e:
        print(f"Error en find_optimal_drivers_with_search_service: {e}")
        traceback.print_exc()
        # Fallback a la función original si hay error
        return find_optimal_drivers(session, client_lat, client_lng, type_service_id, max_distance)


def find_available_drivers(
    session: Session,
    client_lat: float,
    client_lng: float,
    type_service_id: int,
    max_distance: float
) -> List[Dict]:
    """
    Busca conductores disponibles (sin viaje activo y sin solicitud pendiente)
    """
    client_point = func.ST_GeomFromText(
        f'POINT({client_lng} {client_lat})', 4326)

    # Buscar conductores que:
    # 1. Tienen rol DRIVER aprobado
    # 2. No tienen solicitud pendiente
    # 3. No están en viaje activo
    # 4. Están dentro del rango de distancia
    query = (
        session.query(
            User,
            DriverInfo,
            VehicleInfo,
            ST_Distance_Sphere(VehicleInfo.position,
                               client_point).label("distance")
        )
        .join(UserHasRole, User.id == UserHasRole.id_user)
        .join(DriverInfo, User.id == DriverInfo.user_id)
        .join(VehicleInfo, DriverInfo.id == VehicleInfo.driver_info_id)
        .filter(
            UserHasRole.id_rol == "DRIVER",
            UserHasRole.status == RoleStatus.APPROVED,
            UserHasRole.is_verified == True,
            DriverInfo.pending_request_id.is_(None),  # Sin solicitud pendiente
            VehicleInfo.vehicle_type_id == type_service_id
        )
    )

    results = []
    for user, driver_info, vehicle_info, distance in query.all():
        if distance <= max_distance * 1000:  # Convertir km a metros
            # Calcular tiempo estimado directo
            estimated_time = calculate_direct_time(
                client_lat, client_lng, vehicle_info.lat, vehicle_info.lng)

            results.append({
                "user_id": user.id,
                "driver_info_id": driver_info.id,
                "full_name": user.full_name,
                "phone_number": user.phone_number,
                "distance": distance,
                "estimated_time": estimated_time,
                "vehicle_info": {
                    "brand": vehicle_info.brand,
                    "model": vehicle_info.model,
                    "plate": vehicle_info.plate
                }
            })

    return results


def find_busy_drivers(
    session: Session,
    client_lat: float,
    client_lng: float,
    type_service_id: int,
    config: Dict[str, float]
) -> List[Dict]:
    """
    Busca conductores ocupados que pueden tomar la solicitud
    """
    client_point = func.ST_GeomFromText(
        f'POINT({client_lng} {client_lat})', 4326)

    # Buscar conductores que:
    # 1. Tienen rol DRIVER aprobado
    # 2. Están en viaje activo (tienen client_request asignado)
    # 3. NO tienen solicitud pendiente
    # 4. Están dentro del rango de distancia configurado
    query = (
        session.query(
            User,
            DriverInfo,
            VehicleInfo,
            ClientRequest,
            ST_Distance_Sphere(VehicleInfo.position,
                               client_point).label("distance")
        )
        .join(UserHasRole, User.id == UserHasRole.id_user)
        .join(DriverInfo, User.id == DriverInfo.user_id)
        .join(VehicleInfo, DriverInfo.id == VehicleInfo.driver_info_id)
        .join(ClientRequest, User.id == ClientRequest.id_driver_assigned)
        .filter(
            UserHasRole.id_rol == "DRIVER",
            UserHasRole.status == RoleStatus.APPROVED,
            UserHasRole.is_verified == True,
            DriverInfo.pending_request_id.is_(None),  # Sin solicitud pendiente
            VehicleInfo.vehicle_type_id == type_service_id,
            ClientRequest.status.in_(
                ["ON_THE_WAY", "ARRIVED", "TRAVELLING"])  # En viaje activo
        )
    )

    results = []
    for user, driver_info, vehicle_info, current_request, distance in query.all():
        if distance <= config["max_distance"] * 1000:  # Convertir km a metros
            # Calcular tiempo total para conductor ocupado
            total_time = calculate_busy_driver_total_time(
                session, driver_info, current_request, client_lat, client_lng, config
            )

            # Convertir minutos a segundos
            if total_time <= config["max_wait_time"] * 60:
                results.append({
                    "user_id": user.id,
                    "driver_info_id": driver_info.id,
                    "full_name": user.full_name,
                    "phone_number": user.phone_number,
                    "distance": distance,
                    "estimated_time": total_time,
                    "current_trip_remaining_time": calculate_remaining_trip_time(current_request),
                    "transit_time": calculate_transit_time(current_request, client_lat, client_lng),
                    "vehicle_info": {
                        "brand": vehicle_info.brand,
                        "model": vehicle_info.model,
                        "plate": vehicle_info.plate
                    },
                    "current_request_id": current_request.id
                })

    return results


def calculate_busy_driver_total_time(
    session: Session,
    driver_info: DriverInfo,
    current_request: ClientRequest,
    client_lat: float,
    client_lng: float,
    config: Dict[str, float]
) -> float:
    """
    Calcula el tiempo total para un conductor ocupado
    """
    # Tiempo restante del viaje actual
    remaining_time = calculate_remaining_trip_time(current_request)

    # Tiempo de tránsito desde destino actual hasta nuevo cliente
    transit_time = calculate_transit_time(
        current_request, client_lat, client_lng)

    # Tiempo estimado del nuevo viaje
    new_trip_time = calculate_direct_time(client_lat, client_lng,
                                          current_request.destination_lat,
                                          current_request.destination_lng)

    total_time = remaining_time + transit_time + new_trip_time

    return total_time


def calculate_remaining_trip_time(current_request: ClientRequest) -> float:
    """
    Calcula el tiempo restante del viaje actual
    """
    # Obtener coordenadas del viaje actual
    pickup_coords = wkb_to_coords(current_request.pickup_position)
    destination_coords = wkb_to_coords(current_request.destination_position)

    if not pickup_coords or not destination_coords:
        return 0.0

    # Calcular tiempo total del viaje actual
    total_trip_time = calculate_direct_time(
        pickup_coords['lat'], pickup_coords['lng'],
        destination_coords['lat'], destination_coords['lng']
    )

    # Estimar tiempo transcurrido basado en el status
    elapsed_time = estimate_elapsed_time(
        current_request.status, total_trip_time)

    remaining_time = max(0, total_trip_time - elapsed_time)

    return remaining_time


def calculate_transit_time(current_request: ClientRequest, client_lat: float, client_lng: float) -> float:
    """
    Calcula el tiempo de tránsito desde el destino actual hasta el nuevo cliente
    """
    destination_coords = wkb_to_coords(current_request.destination_position)

    if not destination_coords:
        return 0.0

    transit_time = calculate_direct_time(
        destination_coords['lat'], destination_coords['lng'],
        client_lat, client_lng
    )

    return transit_time


def calculate_direct_time(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calcula el tiempo directo entre dos puntos usando Google Distance Matrix
    """
    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": f"{lat1},{lng1}",
            "destinations": f"{lat2},{lng2}",
            "units": "metric",
            "key": settings.GOOGLE_API_KEY,
            "mode": "driving"
        }

        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "OK" and data["rows"][0]["elements"][0]["status"] == "OK":
                # En segundos
                return data["rows"][0]["elements"][0]["duration"]["value"]

        # Fallback: cálculo aproximado
        return calculate_approximate_time(lat1, lng1, lat2, lng2)

    except Exception as e:
        logger.error(f"Error calculating direct time: {e}")
        return calculate_approximate_time(lat1, lng1, lat2, lng2)


def calculate_approximate_time(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calcula tiempo aproximado basado en distancia
    """
    # Distancia en km
    distance = ((lat2 - lat1) ** 2 + (lng2 - lng1) ** 2) ** 0.5 * 111

    # Velocidad promedio 30 km/h en ciudad
    speed_kmh = 30
    time_hours = distance / speed_kmh
    time_seconds = time_hours * 3600

    return time_seconds


def estimate_elapsed_time(status: StatusEnum, total_trip_time: float) -> float:
    """
    Estima el tiempo transcurrido basado en el status del viaje
    """
    if status == StatusEnum.ON_THE_WAY:
        return total_trip_time * 0.2  # 20% del viaje
    elif status == StatusEnum.ARRIVED:
        return total_trip_time * 0.5  # 50% del viaje
    elif status == StatusEnum.TRAVELLING:
        return total_trip_time * 0.8  # 80% del viaje
    else:
        return 0.0


def validate_busy_driver(driver_info: DriverInfo, config: Dict[str, float]) -> bool:
    """
    Valida si un conductor ocupado puede tomar una nueva solicitud
    """
    # Verificar que no tenga solicitud pendiente
    if driver_info.pending_request_id is not None:
        return False

    # Verificar que no haya aceptado una solicitud recientemente
    if driver_info.pending_request_accepted_at:
        time_since_accepted = datetime.now(
            COLOMBIA_TZ) - driver_info.pending_request_accepted_at
        if time_since_accepted.total_seconds() < 60:  # Mínimo 1 minuto entre solicitudes
            return False

    return True


def assign_busy_driver(session, client_request_id, driver_id, estimated_pickup_time, remaining_time, transit_time):
    print(
        f"DEBUG: assign_busy_driver called with client_request_id={client_request_id}, driver_id={driver_id}")

    from app.models.client_request import ClientRequest
    from app.models.driver_info import DriverInfo
    from app.utils.geo_utils import wkb_to_coords

    # 1. Obtener configuraciones dinámicas
    config = get_busy_driver_config(session)
    print(f"🔧 Configuraciones de validación:")
    print(f"   - Tiempo máximo de espera: {config['max_wait_time']} minutos")
    print(f"   - Distancia máxima: {config['max_distance']} km")
    print(
        f"   - Tiempo máximo de tránsito: {config['max_transit_time']} minutos")

    # 2. Obtener datos necesarios
    client_request = session.query(ClientRequest).filter(
        ClientRequest.id == client_request_id).first()
    driver_info = session.query(DriverInfo).filter(
        DriverInfo.user_id == driver_id).first()

    if not client_request or not driver_info:
        print(f"DEBUG: assign_busy_driver - client_request or driver_info not found")
        return False

    # 3. Obtener viaje activo del conductor
    active_request = session.query(ClientRequest).filter(
        ClientRequest.id_driver_assigned == driver_id,
        ClientRequest.status.in_(["ON_THE_WAY", "ARRIVED", "TRAVELLING"])
    ).first()

    if not active_request:
        print(f"DEBUG: assign_busy_driver - No active request found for driver")
        return False

    # 4. Calcular distancia entre cliente y conductor
    try:
        # Obtener posición del conductor (desde DriverPosition)
        from app.models.driver_position import DriverPosition
        driver_position = session.query(DriverPosition).filter(
            DriverPosition.id_driver == driver_id
        ).first()

        if not driver_position or not driver_position.position:
            print(f"DEBUG: assign_busy_driver - No driver position found")
            return False

        # Obtener coordenadas del conductor
        driver_coords = wkb_to_coords(driver_position.position)
        driver_lat, driver_lng = driver_coords["lat"], driver_coords["lng"]

        # Obtener coordenadas del cliente
        client_coords = wkb_to_coords(client_request.pickup_position)
        client_lat, client_lng = client_coords["lat"], client_coords["lng"]

        # Calcular distancia en metros
        from sqlalchemy import func
        client_point = func.ST_GeomFromText(
            f'POINT({client_lng} {client_lat})', 4326)
        vehicle_point = func.ST_GeomFromText(
            f'POINT({driver_lng} {driver_lat})', 4326)

        distance_result = session.query(
            func.ST_Distance_Sphere(vehicle_point, client_point)
        ).scalar()

        distance_km = distance_result / 1000  # Convertir a km
        print(f"🔍 Distancia calculada: {distance_km:.2f} km")

        # 5. VALIDAR DISTANCIA
        if distance_km > config["max_distance"]:
            print(
                f"❌ Distancia excede el límite: {distance_km:.2f} km > {config['max_distance']} km")
            return False

        # 6. VALIDAR TIEMPO TOTAL
        # Convertir a minutos
        total_time_minutes = (remaining_time + transit_time) / 60
        print(f"🔍 Tiempo total calculado: {total_time_minutes:.2f} minutos")

        if total_time_minutes > config["max_wait_time"]:
            print(
                f"❌ Tiempo total excede el límite: {total_time_minutes:.2f} min > {config['max_wait_time']} min")
            return False

        # 7. VALIDAR TIEMPO DE TRÁNSITO
        transit_time_minutes = transit_time / 60  # Convertir a minutos
        print(f"🔍 Tiempo de tránsito: {transit_time_minutes:.2f} minutos")

        if transit_time_minutes > config["max_transit_time"]:
            print(
                f"❌ Tiempo de tránsito excede el límite: {transit_time_minutes:.2f} min > {config['max_transit_time']} min")
            return False

        print(f"✅ Todas las validaciones pasaron - Procediendo con asignación")

    except Exception as e:
        print(f"❌ Error calculando validaciones: {e}")
        return False

    # 8. Si pasa todas las validaciones, proceder con la asignación
    print(
        f"DEBUG: Before assignment - driver_info.id={driver_info.id}, driver_info.user_id={driver_info.user_id}, driver_info.pending_request_id={driver_info.pending_request_id}")
    print(
        f"DEBUG: Before assignment - client_request.id={client_request.id}, client_request.assigned_busy_driver_id={client_request.assigned_busy_driver_id}")

    client_request.assigned_busy_driver_id = driver_id
    client_request.estimated_pickup_time = estimated_pickup_time
    client_request.driver_current_trip_remaining_time = remaining_time
    client_request.driver_transit_time = transit_time
    driver_info.pending_request_id = client_request_id

    session.add(client_request)
    session.add(driver_info)
    session.commit()
    session.refresh(driver_info)
    session.refresh(client_request)

    print(
        f"DEBUG: After assignment - driver_info.id={driver_info.id}, driver_info.user_id={driver_info.user_id}, driver_info.pending_request_id={driver_info.pending_request_id}")
    print(
        f"DEBUG: After assignment - client_request.id={client_request.id}, client_request.assigned_busy_driver_id={client_request.assigned_busy_driver_id}")

    return True


def get_eta_service(session, client_request_id):
    """
    Calcula el ETA (tiempo estimado de llegada) del conductor al punto de recogida usando Google Distance Matrix.
    """
    import traceback
    try:
        from app.models.client_request import ClientRequest
        from app.models.driver_info import DriverInfo
        from app.utils.geo_utils import wkb_to_coords, get_time_and_distance_from_google

        # Buscar la solicitud
        client_request = session.query(ClientRequest).filter(
            ClientRequest.id == client_request_id).first()
        if not client_request:
            raise Exception("Solicitud no encontrada")
        if not client_request.id_driver_assigned:
            raise Exception("No hay conductor asignado a esta solicitud")

        # Buscar la ubicación actual del conductor
        driver_info = session.query(DriverInfo).filter(
            DriverInfo.user_id == client_request.id_driver_assigned).first()
        if not driver_info:
            raise Exception("No se encontró información del conductor")

        # Verificar si tiene campos de ubicación
        if hasattr(driver_info, 'current_lat') and hasattr(driver_info, 'current_lng'):
            if not getattr(driver_info, 'current_lat', None) or not getattr(driver_info, 'current_lng', None):
                raise Exception(
                    "No se encontró la ubicación actual del conductor")
            else:
                driver_lat = driver_info.current_lat
                driver_lng = driver_info.current_lng
        else:
            # Buscar en DriverPosition
            from app.models.driver_position import DriverPosition
            from geoalchemy2.shape import to_shape
            driver_position = session.query(DriverPosition).filter(
                DriverPosition.id_driver == client_request.id_driver_assigned).first()
            if not driver_position:
                raise Exception(
                    "No se encontró la ubicación actual del conductor en DriverPosition")
            point = to_shape(driver_position.position)
            driver_lat = point.y
            driver_lng = point.x

        # Obtener coordenadas de recogida
        pickup_coords = None
        if client_request.pickup_position:
            pickup_coords = wkb_to_coords(client_request.pickup_position)
        if not pickup_coords:
            raise Exception("No se encontró la ubicación de recogida")

        # Llamar a la utilidad de Google
        distance, duration = get_time_and_distance_from_google(
            driver_lat, driver_lng,
            pickup_coords["lat"], pickup_coords["lng"]
        )
        if distance is None or duration is None:
            raise Exception(
                "No se pudo obtener el tiempo y distancia desde Google API")

        result = {"distance": distance, "duration": duration}
        # Emitir actualización por WebSocket si está disponible
        try:
            from app.core.sio_events import sio
            import asyncio

            async def emit_eta_update():
                await sio.emit(
                    f'eta_update/{client_request_id}',
                    {
                        'distance': distance,
                        'duration': duration,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                )
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(emit_eta_update())
                else:
                    loop.run_until_complete(emit_eta_update())
            except RuntimeError:
                asyncio.run(emit_eta_update())
        except Exception:
            pass
        return result
    except Exception as e:
        traceback.print_exc()
        raise
