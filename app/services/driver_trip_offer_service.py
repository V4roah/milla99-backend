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
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from datetime import datetime
from uuid import UUID
import requests
from app.core.config import settings
from app.utils.geo_utils import wkb_to_coords


def get_time_and_distance_from_google(origin_lat, origin_lng, destination_lat, destination_lng):
    """Llama a la API de Google Distance Matrix para obtener tiempo y distancia."""
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": f"{origin_lat},{origin_lng}",
        "destinations": f"{destination_lat},{destination_lng}",
        "units": "metric",
        "key": settings.GOOGLE_API_KEY
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "OK" and data["rows"][0]["elements"][0]["status"] == "OK":
            distance = data["rows"][0]["elements"][0]["distance"]["value"]
            duration = data["rows"][0]["elements"][0]["duration"]["value"]
            return distance, duration
        else:
            return None, None
    except requests.exceptions.RequestException as e:
        print(f"Error al llamar a Google Maps API: {e}")
        return None, None


class DriverTripOfferService:
    def __init__(self, session: Session):
        self.session = session

    def create_offer(self, data: dict) -> DriverTripOffer:
        # Validar que el driver exista y tenga el rol DRIVER
        user = self.session.get(User, data["id_driver"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conductor no encontrado")
        driver_role = self.session.exec(
            select(UserHasRole).where(
                UserHasRole.id_user == data["id_driver"],
                UserHasRole.id_rol == "DRIVER"
            )
        ).first()
        if not driver_role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="El usuario no tiene el rol de conductor")

        # Validar que la solicitud exista y esté en estado CREATED
        client_request = self.session.get(
            ClientRequest, data["id_client_request"])
        if not client_request:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Solicitud de cliente no encontrada")
        if client_request.status != StatusEnum.CREATED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="La solicitud no está en estado CREATED")

        # Validar que el precio ofrecido no sea menor al precio base
        if client_request.fare_offered is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La solicitud de cliente no tiene un precio base definido"
            )

        if float(data["fare_offer"]) < float(client_request.fare_offered):
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
        if existing_offer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe una oferta para esta solicitud"
            )

        offer = DriverTripOffer(**data)
        self.session.add(offer)
        self.session.commit()
        self.session.refresh(offer)
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

        pickup_coords = wkb_to_coords(client_request.pickup_position)
        destination_coords = wkb_to_coords(client_request.destination_position)

        distance_fallback, time_fallback = get_time_and_distance_from_google(
            pickup_coords['lat'], pickup_coords['lng'],
            destination_coords['lat'], destination_coords['lng']
        )
        time_fallback_minutes = (
            time_fallback / 60) if time_fallback is not None else 0

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

            time_to_return = offer.time if offer.time else time_fallback_minutes
            distance_to_return = offer.distance if offer.distance else distance_fallback

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
