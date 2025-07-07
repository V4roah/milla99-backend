from sqlmodel import Session, select
from typing import List, Dict, Optional, Tuple
from app.models.driver_info import DriverInfo
from app.models.client_request import ClientRequest, StatusEnum
from app.models.project_settings import ProjectSettings
from app.services.project_settings_service import ProjectSettingsService
from app.utils.geo import calculate_distance, estimate_travel_time
from datetime import datetime, timedelta
import pytz

COLOMBIA_TZ = pytz.timezone("America/Bogota")


class DriverSearchService:
    def __init__(self, session: Session):
        self.session = session
        self.project_settings_service = ProjectSettingsService(session)

    def find_available_drivers(
        self,
        latitude: float,
        longitude: float,
        vehicle_type_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Busca conductores disponibles (sin viajes activos ni solicitudes pendientes).

        Args:
            latitude: Latitud del cliente
            longitude: Longitud del cliente
            vehicle_type_id: Tipo de vehículo requerido (opcional)

        Returns:
            Lista de conductores disponibles ordenados por proximidad
        """
        try:
            # Query base para conductores disponibles
            query = select(DriverInfo).where(
                DriverInfo.is_available == True,
                DriverInfo.pending_request_id.is_(
                    None)  # Sin solicitudes pendientes
            )

            # Filtrar por tipo de vehículo si se especifica
            if vehicle_type_id:
                query = query.join(DriverInfo.vehicle_info).where(
                    DriverInfo.vehicle_info.any(
                        vehicle_type_id=vehicle_type_id)
                )

            drivers = self.session.exec(query).all()

            # Calcular distancias y ordenar por proximidad
            drivers_with_distance = []
            for driver in drivers:
                if driver.latitude and driver.longitude:
                    distance = calculate_distance(
                        latitude, longitude,
                        driver.latitude, driver.longitude
                    )
                    drivers_with_distance.append({
                        "driver": driver,
                        "distance": distance,
                        "estimated_time": estimate_travel_time(distance)
                    })

            # Ordenar por distancia (más cercanos primero)
            drivers_with_distance.sort(key=lambda x: x["distance"])

            return drivers_with_distance

        except Exception as e:
            print(f"Error buscando conductores disponibles: {e}")
            return []

    def find_nearby_busy_drivers(
        self,
        latitude: float,
        longitude: float,
        vehicle_type_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Busca conductores ocupados que están cerca del cliente y cumplen el tiempo máximo.

        Args:
            latitude: Latitud del cliente
            longitude: Longitud del cliente
            vehicle_type_id: Tipo de vehículo requerido (opcional)

        Returns:
            Lista de conductores ocupados cercanos que cumplen el tiempo máximo
        """
        try:
            # Obtener el tiempo máximo configurado
            max_time = self.project_settings_service.get_max_busy_driver_time()

            # Buscar conductores ocupados con solicitudes pendientes
            query = select(DriverInfo).where(
                DriverInfo.pending_request_id.is_not(
                    None)  # Con solicitudes pendientes
            )

            # Filtrar por tipo de vehículo si se especifica
            if vehicle_type_id:
                query = query.join(DriverInfo.vehicle_info).where(
                    DriverInfo.vehicle_info.any(
                        vehicle_type_id=vehicle_type_id)
                )

            busy_drivers = self.session.exec(query).all()

            valid_busy_drivers = []
            for driver in busy_drivers:
                if driver.latitude and driver.longitude:
                    # Calcular tiempo total estimado
                    total_time = self.calculate_total_time(
                        driver, latitude, longitude
                    )

                    # Validar que no exceda el tiempo máximo
                    if self.validate_max_time(total_time, max_time):
                        distance = calculate_distance(
                            latitude, longitude,
                            driver.latitude, driver.longitude
                        )
                        valid_busy_drivers.append({
                            "driver": driver,
                            "distance": distance,
                            "estimated_time": estimate_travel_time(distance),
                            "total_time": total_time
                        })

            # Ordenar por tiempo total (menor tiempo primero)
            valid_busy_drivers.sort(key=lambda x: x["total_time"])

            return valid_busy_drivers

        except Exception as e:
            print(f"Error buscando conductores ocupados cercanos: {e}")
            return []

    def find_far_busy_drivers(
        self,
        latitude: float,
        longitude: float,
        vehicle_type_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Busca conductores ocupados que están lejos del cliente (para análisis).

        Args:
            latitude: Latitud del cliente
            longitude: Longitud del cliente
            vehicle_type_id: Tipo de vehículo requerido (opcional)

        Returns:
            Lista de conductores ocupados lejanos
        """
        try:
            # Obtener el tiempo máximo configurado
            max_time = self.project_settings_service.get_max_busy_driver_time()

            # Buscar conductores ocupados con solicitudes pendientes
            query = select(DriverInfo).where(
                DriverInfo.pending_request_id.is_not(None)
            )

            # Filtrar por tipo de vehículo si se especifica
            if vehicle_type_id:
                query = query.join(DriverInfo.vehicle_info).where(
                    DriverInfo.vehicle_info.any(
                        vehicle_type_id=vehicle_type_id)
                )

            busy_drivers = self.session.exec(query).all()

            invalid_busy_drivers = []
            for driver in busy_drivers:
                if driver.latitude and driver.longitude:
                    # Calcular tiempo total estimado
                    total_time = self.calculate_total_time(
                        driver, latitude, longitude
                    )

                    # Incluir solo los que exceden el tiempo máximo
                    if not self.validate_max_time(total_time, max_time):
                        distance = calculate_distance(
                            latitude, longitude,
                            driver.latitude, driver.longitude
                        )
                        invalid_busy_drivers.append({
                            "driver": driver,
                            "distance": distance,
                            "estimated_time": estimate_travel_time(distance),
                            "total_time": total_time,
                            "exceeds_max_time": True
                        })

            return invalid_busy_drivers

        except Exception as e:
            print(f"Error buscando conductores ocupados lejanos: {e}")
            return []

    def calculate_priorities(
        self,
        drivers: List[Dict],
        client_latitude: float,
        client_longitude: float
    ) -> List[Dict]:
        """
        Calcula prioridades para los conductores encontrados.

        Args:
            drivers: Lista de conductores con información de distancia
            client_latitude: Latitud del cliente
            client_longitude: Longitud del cliente

        Returns:
            Lista de conductores ordenados por prioridad
        """
        try:
            for driver_info in drivers:
                driver = driver_info["driver"]

                # Calcular puntuación base por proximidad (0-100)
                max_distance = 50.0  # 50 km como distancia máxima
                distance_score = max(
                    0, 100 - (driver_info["distance"] / max_distance) * 100)

                # Calcular puntuación por calificación del conductor (0-100)
                rating_score = 0
                if hasattr(driver, 'rating') and driver.rating:
                    rating_score = driver.rating * 20  # Convertir rating 0-5 a 0-100

                # Calcular puntuación por tiempo de respuesta (0-100)
                response_time_score = 100  # Valor por defecto
                if hasattr(driver, 'avg_response_time') and driver.avg_response_time:
                    # Menor tiempo = mayor puntuación
                    max_response_time = 300  # 5 minutos
                    response_time_score = max(
                        0, 100 - (driver.avg_response_time / max_response_time) * 100)

                # Calcular puntuación por tipo de vehículo (0-100)
                vehicle_score = 100  # Valor por defecto
                if hasattr(driver, 'vehicle_info') and driver.vehicle_info:
                    # Priorizar ciertos tipos de vehículo si es necesario
                    vehicle_type = driver.vehicle_info.vehicle_type_id
                    if vehicle_type == 1:  # Carro
                        vehicle_score = 100
                    elif vehicle_type == 2:  # Moto
                        vehicle_score = 80
                    else:
                        vehicle_score = 70

                # Calcular puntuación total (promedio ponderado)
                total_score = (
                    distance_score * 0.4 +      # 40% proximidad
                    rating_score * 0.3 +        # 30% calificación
                    response_time_score * 0.2 +  # 20% tiempo de respuesta
                    vehicle_score * 0.1         # 10% tipo de vehículo
                )

                driver_info["priority_score"] = total_score
                driver_info["distance_score"] = distance_score
                driver_info["rating_score"] = rating_score
                driver_info["response_time_score"] = response_time_score
                driver_info["vehicle_score"] = vehicle_score

            # Ordenar por puntuación total (mayor puntuación = mayor prioridad)
            drivers.sort(key=lambda x: x["priority_score"], reverse=True)

            return drivers

        except Exception as e:
            print(f"Error calculando prioridades: {e}")
            return drivers

    def validate_max_time(self, total_time: float, max_time: int) -> bool:
        """
        Valida si el tiempo total estimado no supera el límite configurado.

        Args:
            total_time: Tiempo total estimado en minutos
            max_time: Tiempo máximo permitido en minutos

        Returns:
            True si cumple el límite, False si lo excede
        """
        return total_time <= max_time

    def calculate_total_time(
        self,
        driver: DriverInfo,
        client_latitude: float,
        client_longitude: float
    ) -> float:
        """
        Calcula el tiempo total estimado para un conductor ocupado.

        Args:
            driver: Información del conductor
            client_latitude: Latitud del cliente
            client_longitude: Longitud del cliente

        Returns:
            Tiempo total estimado en minutos
        """
        try:
            # Obtener la solicitud pendiente del conductor
            if not driver.pending_request_id:
                return 0.0

            pending_request = self.session.exec(
                select(ClientRequest).where(
                    ClientRequest.id == driver.pending_request_id
                )
            ).first()

            if not pending_request:
                return 0.0

            # Calcular tiempo restante del viaje actual
            current_trip_remaining = self._calculate_remaining_trip_time(
                driver)

            # Calcular tiempo de tránsito al nuevo cliente
            transit_time = self._calculate_transit_time(
                driver, client_latitude, client_longitude
            )

            # Margen de seguridad (5 minutos)
            safety_margin = 5.0

            # Tiempo total = tiempo restante + tránsito + margen
            total_time = current_trip_remaining + transit_time + safety_margin

            return total_time

        except Exception as e:
            print(f"Error calculando tiempo total: {e}")
            return 0.0

    def _calculate_remaining_trip_time(self, driver: DriverInfo) -> float:
        """
        Calcula el tiempo restante del viaje actual del conductor.

        Args:
            driver: Información del conductor

        Returns:
            Tiempo restante en minutos
        """
        try:
            # Buscar el viaje activo del conductor
            active_trip = self.session.exec(
                select(ClientRequest).where(
                    ClientRequest.driver_id == driver.id,
                    ClientRequest.status.in_([
                        StatusEnum.ACCEPTED,
                        StatusEnum.ON_THE_WAY,
                        StatusEnum.ARRIVED,
                        StatusEnum.TRAVELING
                    ])
                )
            ).first()

            if not active_trip:
                return 0.0

            # Calcular tiempo estimado restante basado en el estado
            if active_trip.status == StatusEnum.ACCEPTED:
                # Conductor aún no ha llegado al cliente
                return 15.0  # Estimación conservadora
            elif active_trip.status == StatusEnum.ON_THE_WAY:
                # Conductor en camino al cliente
                return 10.0
            elif active_trip.status == StatusEnum.ARRIVED:
                # Conductor llegó, esperando al cliente
                return 5.0
            elif active_trip.status == StatusEnum.TRAVELING:
                # Conductor transportando al cliente
                # Calcular tiempo restante basado en distancia al destino
                if active_trip.destination_latitude and active_trip.destination_longitude:
                    distance_to_destination = calculate_distance(
                        driver.latitude, driver.longitude,
                        active_trip.destination_latitude, active_trip.destination_longitude
                    )
                    return estimate_travel_time(distance_to_destination)
                else:
                    return 10.0  # Estimación por defecto

            return 0.0

        except Exception as e:
            print(f"Error calculando tiempo restante del viaje actual: {e}")
            return 0.0

    def _calculate_transit_time(
        self,
        driver: DriverInfo,
        client_latitude: float,
        client_longitude: float
    ) -> float:
        """
        Calcula el tiempo de tránsito desde la posición actual del conductor al nuevo cliente.

        Args:
            driver: Información del conductor
            client_latitude: Latitud del cliente
            client_longitude: Longitud del cliente

        Returns:
            Tiempo de tránsito en minutos
        """
        try:
            if not driver.latitude or not driver.longitude:
                return 0.0

            # Calcular distancia al nuevo cliente
            distance = calculate_distance(
                driver.latitude, driver.longitude,
                client_latitude, client_longitude
            )

            # Estimar tiempo de tránsito
            transit_time = estimate_travel_time(distance)

            return transit_time

        except Exception as e:
            print(f"Error calculando tiempo de tránsito: {e}")
            return 0.0
