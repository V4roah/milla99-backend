from sqlmodel import Session, select
from fastapi import HTTPException, status
from app.models.driver_trip_offer import DriverTripOffer, DriverTripOfferCreate
from app.models.client_request import ClientRequest, StatusEnum
from app.models.user import User
from app.models.user_has_roles import UserHasRole
from app.models.driver_info import DriverInfo
from app.models.vehicle_info import VehicleInfo
from app.models.driver_trip_offer import DriverTripOfferResponse
from app.models.driver_response import UserResponse, DriverInfoResponse, VehicleInfoResponse
from app.models.driver_position import DriverPosition
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from datetime import datetime
from uuid import UUID
import requests
from app.core.config import settings
from app.utils.geo_utils import wkb_to_coords, get_time_and_distance_from_google
from app.services.notification_service import NotificationService
import logging

logger = logging.getLogger(__name__)


class DriverTripOfferService:
    def __init__(self, session: Session):
        self.session = session

    def create_offer(self, data: dict) -> DriverTripOffer:
        print(f"\n=== DEBUG CREATE_OFFER ===")
        print(f"Datos recibidos: {data}")

        # Validar que el driver exista y tenga el rol DRIVER
        user = self.session.get(User, data["id_driver"])
        print(f"Usuario encontrado: {user is not None}")
        if not user:
            print(
                f"ERROR: Conductor no encontrado con ID: {data['id_driver']}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conductor no encontrado")

        driver_role = self.session.exec(
            select(UserHasRole).where(
                UserHasRole.id_user == data["id_driver"],
                UserHasRole.id_rol == "DRIVER"
            )
        ).first()
        print(f"Rol de conductor encontrado: {driver_role is not None}")
        if not driver_role:
            print(f"ERROR: Usuario {data['id_driver']} no tiene rol DRIVER")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="El usuario no tiene el rol de conductor")

        # Validar que la solicitud exista y esté en estado CREATED
        client_request = self.session.get(
            ClientRequest, data["id_client_request"])
        print(f"Client request encontrada: {client_request is not None}")
        if not client_request:
            print(
                f"ERROR: Client request no encontrada con ID: {data['id_client_request']}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Solicitud de cliente no encontrada")

        print(f"Estado de client request: {client_request.status}")
        if client_request.status != StatusEnum.CREATED:
            print(
                f"ERROR: Client request no está en estado CREATED, está en: {client_request.status}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="La solicitud no está en estado CREATED")

        # Validar que el precio ofrecido no sea menor al precio base
        print(f"Fare offered en client request: {client_request.fare_offered}")
        print(f"Fare offer en data: {data.get('fare_offer')}")

        if client_request.fare_offered is None:
            print(f"ERROR: Client request no tiene fare_offered definido")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La solicitud de cliente no tiene un precio base definido"
            )

        if float(data["fare_offer"]) < float(client_request.fare_offered):
            print(
                f"ERROR: Oferta {data['fare_offer']} es menor que precio base {client_request.fare_offered}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La oferta debe ser mayor o igual al precio base"
            )

        # Validar que no exista una oferta previa del mismo conductor para esta solicitud
        existing_offer = self.session.exec(
            select(DriverTripOffer).where(
                DriverTripOffer.id_client_request == data["id_client_request"],
                DriverTripOffer.id_driver == data["id_driver"]
            )
        ).first()
        print(f"Oferta existente encontrada: {existing_offer is not None}")
        if existing_offer:
            print(
                f"ERROR: Ya existe una oferta del conductor {data['id_driver']} para la solicitud {data['id_client_request']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe una oferta para esta solicitud"
            )

        print(f"Todas las validaciones pasaron, creando oferta...")

        # Obtener la posición actual del conductor
        driver_position = self.session.query(DriverPosition).filter(
            DriverPosition.id_driver == data["id_driver"]
        ).first()

        # Obtener coordenadas del punto de recogida
        pickup_coords = wkb_to_coords(client_request.pickup_position)

        # Calcular distancia y tiempo desde el conductor hasta el punto de recogida
        if driver_position and driver_position.position:
            driver_coords = wkb_to_coords(driver_position.position)

            # Calcular usando Google Maps API
            distance_to_pickup, time_to_pickup = get_time_and_distance_from_google(
                # Posición del conductor
                driver_coords['lat'], driver_coords['lng'],
                # Punto de recogida
                pickup_coords['lat'], pickup_coords['lng']
            )

            # Convertir tiempo de segundos a minutos
            time_to_pickup_minutes = (
                time_to_pickup / 60) if time_to_pickup is not None else 0

            # Usar los valores calculados o los valores guardados en la oferta como fallback
            time_to_return = time_to_pickup_minutes if time_to_pickup_minutes > 0 else data.get(
                "time", 0)
            distance_to_return = distance_to_pickup if distance_to_pickup is not None else data.get(
                "distance", 0)

            print(
                f"DEBUG: Conductor {data['id_driver']} - Distancia calculada: {distance_to_return}m, Tiempo: {time_to_return}min")
        else:
            # Si no hay posición del conductor, usar los valores guardados en la oferta
            time_to_return = data.get("time", 0)
            distance_to_return = data.get("distance", 0)
            print(
                f"WARNING: Conductor {data['id_driver']} no tiene posición definida, usando valores guardados: {distance_to_return}m, {time_to_return}min")

        data["time"] = time_to_return
        data["distance"] = distance_to_return

        offer = DriverTripOffer(**data)
        self.session.add(offer)
        self.session.commit()
        self.session.refresh(offer)
        print(f"Oferta creada exitosamente con ID: {offer.id}")

        # Enviar notificación al cliente sobre la nueva oferta
        try:
            notification_service = NotificationService(self.session)
            notification_result = notification_service.notify_driver_offer(
                request_id=data["id_client_request"],
                driver_id=data["id_driver"],
                fare=data["fare_offer"]
            )
            logger.info(
                f"Notificación de oferta enviada: {notification_result}")
        except Exception as e:
            logger.error(f"Error enviando notificación de oferta: {e}")
            # No fallar la creación de la oferta si falla la notificación

        return offer

    def get_offers_by_client_request(self, id_client_request: UUID, user_id: UUID, user_role: str):
        client_request = self.session.query(ClientRequest).filter(
            ClientRequest.id == id_client_request).first()
        if not client_request:
            raise HTTPException(
                status_code=404, detail="Solicitud de cliente no encontrada")

        offers = self.session.query(DriverTripOffer).filter(
            DriverTripOffer.id_client_request == id_client_request
        ).all()
        result = []

        # Obtener coordenadas del punto de recogida del cliente
        pickup_coords = wkb_to_coords(client_request.pickup_position)

        for offer in offers:
            user = self.session.query(User).options(
                selectinload(User.driver_info).selectinload(
                    DriverInfo.vehicle_info),
                selectinload(User.roles)
            ).filter(User.id == offer.id_driver).first()

            driver_info_obj = user.driver_info if user else None
            vehicle_info_obj = driver_info_obj.vehicle_info if driver_info_obj and hasattr(
                driver_info_obj, 'vehicle_info') else None

            vehicle_info_response = VehicleInfoResponse(
                brand=vehicle_info_obj.brand,
                model=vehicle_info_obj.model,
                model_year=vehicle_info_obj.model_year,
                color=vehicle_info_obj.color,
                plate=vehicle_info_obj.plate,
                vehicle_type_id=vehicle_info_obj.vehicle_type_id
            ) if vehicle_info_obj else None

            driver_info_response = DriverInfoResponse(
                first_name=driver_info_obj.first_name,
                last_name=driver_info_obj.last_name,
                birth_date=str(driver_info_obj.birth_date),
                email=driver_info_obj.email
            ) if driver_info_obj else None

            user_response = UserResponse(
                id=user.id,
                full_name=user.full_name,
                country_code=user.country_code,
                phone_number=user.phone_number,
                selfie_url=user.selfie_url
            ) if user else None

            average_rating = get_average_rating(
                self.session, "driver", user.id) if user else 0.0

            # Obtener la posición actual del conductor
            driver_position = self.session.query(DriverPosition).filter(
                DriverPosition.id_driver == offer.id_driver
            ).first()

            # Calcular distancia y tiempo desde el conductor hasta el punto de recogida
            if driver_position and driver_position.position:
                driver_coords = wkb_to_coords(driver_position.position)

                # Calcular usando Google Maps API
                distance_to_pickup, time_to_pickup = get_time_and_distance_from_google(
                    # Posición del conductor
                    driver_coords['lat'], driver_coords['lng'],
                    # Punto de recogida
                    pickup_coords['lat'], pickup_coords['lng']
                )

                # Convertir tiempo de segundos a minutos
                time_to_pickup_minutes = (
                    time_to_pickup / 60) if time_to_pickup is not None else 0

                # Usar los valores calculados o los valores guardados en la oferta como fallback
                time_to_return = time_to_pickup_minutes if time_to_pickup_minutes > 0 else offer.time
                distance_to_return = distance_to_pickup if distance_to_pickup is not None else offer.distance

                print(
                    f"DEBUG: Conductor {offer.id_driver} - Distancia calculada: {distance_to_return}m, Tiempo: {time_to_return}min")
            else:
                # Si no hay posición del conductor, usar los valores guardados en la oferta
                time_to_return = offer.time
                distance_to_return = offer.distance
                print(
                    f"WARNING: Conductor {offer.id_driver} no tiene posición definida, usando valores guardados: {distance_to_return}m, {time_to_return}min")

            result.append(DriverTripOfferResponse(
                id=offer.id,
                fare_offer=offer.fare_offer,
                time=time_to_return,
                distance=distance_to_return,
                created_at=str(offer.created_at),
                updated_at=str(offer.updated_at),
                user=user_response,
                driver_info=driver_info_response,
                vehicle_info=vehicle_info_response,
                average_rating=average_rating
            ))

        if user_role == "DRIVER":
            # Solo ve su propia oferta
            result = [r for r in result if r.user.id == user_id]
        elif user_role == "CLIENT":
            # Solo el cliente dueño puede ver todas
            if client_request.id_client != user_id:
                raise HTTPException(
                    status_code=403, detail="No autorizado para ver las ofertas de esta solicitud")
            # El cliente dueño ve todas
        else:
            raise HTTPException(status_code=403, detail="No autorizado")

        return result


def get_average_rating(session, role: str, id_user: UUID) -> float:
    if role not in ["driver", "passenger"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El parámetro 'role' debe ser 'driver' o 'passenger'"
        )

    if role == "passenger":
        # Buscar por id_client y calcular promedio de client_rating
        avg_rating = session.query(func.avg(ClientRequest.client_rating))\
            .filter(
                ClientRequest.id_client == id_user,
                ClientRequest.status == StatusEnum.PAID
        ).scalar()
    else:  # role == "driver"
        # Buscar por id_driver_assigned y calcular promedio de driver_rating
        avg_rating = session.query(func.avg(ClientRequest.driver_rating))\
            .filter(
                ClientRequest.id_driver_assigned == id_user,
                ClientRequest.status == StatusEnum.PAID
        ).scalar()

    # Si no hay calificaciones, devolver 0 o None según prefieras
    return avg_rating if avg_rating is not None else 0.0
