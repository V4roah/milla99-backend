from sqlmodel import Session, select
from typing import List, Dict, Optional, Tuple
from app.models.driver_info import DriverInfo
from app.models.client_request import ClientRequest, StatusEnum
from app.models.project_settings import ProjectSettings
from app.models.driver_position import DriverPosition
from app.services.config_service_value_service import ConfigServiceValueService
from app.utils.geo_utils import get_time_and_distance_from_google, wkb_to_coords
from datetime import datetime, timedelta
import pytz

COLOMBIA_TZ = pytz.timezone("America/Bogota")


class DriverSearchService:
    def __init__(self, session: Session):
        self.session = session
        self.config_service_value_service = ConfigServiceValueService(session)

    def _get_driver_position(self, driver_id: str) -> Optional[Dict]:
        """
        Obtiene la posición actual de un conductor desde DriverPosition

        Args:
            driver_id: ID del conductor

        Returns:
            Diccionario con lat y lng, o None si no tiene posición
        """
        try:
            driver_position = self.session.exec(
                select(DriverPosition).where(
                    DriverPosition.id_driver == driver_id)
            ).first()

            if driver_position and driver_position.position:
                coords = wkb_to_coords(driver_position.position)
                return {
                    "lat": coords["lat"],
                    "lng": coords["lng"]
                }
            return None
        except Exception as e:
            print(f"Error obteniendo posición del conductor {driver_id}: {e}")
            return None

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
            # Un conductor está disponible si:
            # 1. No tiene solicitudes pendientes
            # 2. No tiene viajes activos (ACCEPTED, ON_THE_WAY, ARRIVED, TRAVELLING)
            query = select(DriverInfo).where(
                DriverInfo.pending_request_id.is_(
                    None)  # Sin solicitudes pendientes
            )

            # Filtrar por tipo de vehículo si se especifica
            if vehicle_type_id:
                query = query.join(DriverInfo.vehicle_info).where(
                    DriverInfo.vehicle_info.has(
                        vehicle_type_id=vehicle_type_id)
                )

            drivers = self.session.exec(query).all()

            # Filtrar conductores que no tengan viajes activos
            available_drivers = []
            for driver in drivers:
                # Verificar si el conductor tiene viajes activos
                active_trip = self.session.exec(
                    select(ClientRequest).where(
                        ClientRequest.id_driver_assigned == driver.user_id,
                        ClientRequest.status.in_([
                            StatusEnum.ACCEPTED,
                            StatusEnum.ON_THE_WAY,
                            StatusEnum.ARRIVED,
                            StatusEnum.TRAVELLING
                        ])
                    )
                ).first()

                # Si no tiene viajes activos, está disponible
                if not active_trip:
                    available_drivers.append(driver)

            # Calcular distancias y ordenar por proximidad
            drivers_with_distance = []
            for driver in available_drivers:
                # Obtener posición del conductor desde DriverPosition
                driver_pos = self._get_driver_position(driver.user_id)
                if driver_pos:
                    distance_data = get_time_and_distance_from_google(
                        latitude, longitude,
                        driver_pos["lat"], driver_pos["lng"]
                    )
                    if distance_data[0] is not None and distance_data[1] is not None:
                        # Convertir metros a km
                        distance_km = distance_data[0] / 1000
                        # Convertir segundos a minutos
                        duration_min = distance_data[1] / 60
                        drivers_with_distance.append({
                            "driver": driver,
                            "distance": distance_km,
                            "estimated_time": duration_min
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
        Busca conductores ocupados (ON_THE_WAY, ARRIVED, TRAVELLING) que están cerca del cliente y cumplen TODAS las validaciones.
        Solo considera conductores que NO tienen solicitudes pendientes.

        Args:
            latitude: Latitud del cliente
            longitude: Longitud del cliente
            vehicle_type_id: Tipo de vehículo requerido (opcional)

        Returns:
            Lista de conductores ocupados cercanos que cumplen todas las validaciones
        """
        try:
            # Obtener configuraciones desde ProjectSettings
            settings = self.session.exec(select(ProjectSettings)).first()
            if not settings:
                print(
                    "⚠️ No se encontraron configuraciones de ProjectSettings, usando valores por defecto")
                max_wait_time = 15.0
                max_distance = 2.0
                max_transit_time = 5.0
            else:
                max_wait_time = settings.max_wait_time_for_busy_driver or 15.0
                max_distance = settings.max_distance_for_busy_driver or 2.0
                max_transit_time = settings.max_transit_time_for_busy_driver or 5.0

            print(f"🔧 Configuraciones de validación:")
            print(f"   - Tiempo máximo de espera: {max_wait_time} minutos")
            print(f"   - Distancia máxima: {max_distance} km")
            print(
                f"   - Tiempo máximo de tránsito: {max_transit_time} minutos")

            # Buscar conductores que estén ocupados (ON_THE_WAY, ARRIVED, TRAVELLING) pero NO tengan solicitudes pendientes
            query = select(DriverInfo).join(ClientRequest).where(
                ClientRequest.id_driver_assigned == DriverInfo.user_id,
                ClientRequest.status.in_([
                    StatusEnum.ON_THE_WAY,
                    StatusEnum.ARRIVED,
                    StatusEnum.TRAVELLING
                ]),
                # ✅ NO tienen solicitudes pendientes
                DriverInfo.pending_request_id.is_(None)
            )

            # Filtrar por tipo de vehículo si se especifica
            if vehicle_type_id:
                query = query.join(DriverInfo.vehicle_info).where(
                    DriverInfo.vehicle_info.has(
                        vehicle_type_id=vehicle_type_id)
                )

            busy_drivers = self.session.exec(query).all()
            print(
                f"🔍 Encontrados {len(busy_drivers)} conductores ocupados (ON_THE_WAY/ARRIVED/TRAVELLING) SIN solicitudes pendientes")

            valid_busy_drivers = []
            for driver in busy_drivers:
                # Obtener posición del conductor desde DriverPosition
                driver_pos = self._get_driver_position(driver.user_id)
                if not driver_pos:
                    print(f"❌ Conductor {driver.id}: Sin posición registrada")
                    continue

                # Calcular distancia al cliente
                distance_data = get_time_and_distance_from_google(
                    latitude, longitude,
                    driver_pos["lat"], driver_pos["lng"]
                )
                if distance_data[0] is None or distance_data[1] is None:
                    print(
                        f"❌ Conductor {driver.id}: No se pudo obtener distancia/tiempo de Google")
                    continue

                distance = distance_data[0] / 1000  # Convertir metros a km
                # Convertir segundos a minutos
                transit_time = distance_data[1] / 60

                # Validación 1: Distancia máxima
                if distance > max_distance:
                    print(
                        f"❌ Conductor {driver.id}: Distancia {distance:.2f}km > {max_distance}km")
                    continue

                # Validación 2: Tiempo de tránsito máximo
                if transit_time > max_transit_time:
                    print(
                        f"❌ Conductor {driver.id}: Tiempo de tránsito {transit_time:.2f}min > {max_transit_time}min")
                    continue

                # Validación 3: Tiempo total máximo
                total_time = self.calculate_total_time(
                    driver, latitude, longitude
                )
                if total_time > max_wait_time:
                    print(
                        f"❌ Conductor {driver.id}: Tiempo total {total_time:.2f}min > {max_wait_time}min")
                    continue

                print(
                    f"✅ Conductor {driver.id} cumple todas las validaciones:")
                print(f"   - Distancia: {distance:.2f}km")
                print(f"   - Tiempo de tránsito: {transit_time:.2f}min")
                print(f"   - Tiempo total: {total_time:.2f}min")

                valid_busy_drivers.append({
                    "driver": driver,
                    "distance": distance,
                    "estimated_time": transit_time,
                    "total_time": total_time
                })

            # Ordenar por tiempo total (menor tiempo primero)
            valid_busy_drivers.sort(key=lambda x: x["total_time"])
            print(
                f"✅ {len(valid_busy_drivers)} conductores ocupados válidos encontrados")

            return valid_busy_drivers

        except Exception as e:
            print(f"❌ Error buscando conductores ocupados cercanos: {e}")
            import traceback
            traceback.print_exc()
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
            # Calcular tiempo restante del viaje actual
            current_trip_remaining = self._calculate_remaining_trip_time(
                driver)

            # Calcular tiempo de tránsito al nuevo cliente
            transit_time = self._calculate_transit_time(
                driver, client_latitude, client_longitude
            )

            # Margen de seguridad (reducido de 5 a 2 minutos)
            safety_margin = 2.0

            # Tiempo total = tiempo restante + tránsito + margen
            total_time = current_trip_remaining + transit_time + safety_margin

            return total_time

        except Exception as e:
            print(f"Error calculando tiempo total: {e}")
            return 0.0

    def _calculate_remaining_trip_time(self, driver: DriverInfo) -> float:
        """
        Calcula el tiempo restante del viaje actual del conductor.
        Considera conductores en estados ON_THE_WAY, ARRIVED y TRAVELLING como ocupados.

        Args:
            driver: Información del conductor

        Returns:
            Tiempo restante en minutos
        """
        try:
            # Buscar el viaje activo del conductor (ocupados: ON_THE_WAY, ARRIVED, TRAVELLING)
            active_trip = self.session.exec(
                select(ClientRequest).where(
                    ClientRequest.id_driver_assigned == driver.user_id,
                    ClientRequest.status.in_([
                        StatusEnum.ON_THE_WAY,
                        StatusEnum.ARRIVED,
                        StatusEnum.TRAVELLING
                    ])
                )
            ).first()

            if not active_trip:
                return 0.0

            # Obtener posición actual del conductor
            driver_pos = self._get_driver_position(driver.user_id)
            if not driver_pos:
                return 10.0  # Estimación por defecto si no hay posición

            # Calcular tiempo estimado restante basado en el estado
            if active_trip.status == StatusEnum.ON_THE_WAY:
                # Conductor en camino al cliente
                return 15.0  # Estimación conservadora
            elif active_trip.status == StatusEnum.ARRIVED:
                # Conductor llegó, esperando al cliente
                return 5.0
            elif active_trip.status == StatusEnum.TRAVELLING:
                # Conductor transportando al cliente
                # Calcular tiempo restante basado en distancia al destino
                if active_trip.destination_position:
                    destination_coords = wkb_to_coords(
                        active_trip.destination_position)
                    time_to_destination = get_time_and_distance_from_google(
                        driver_pos["lat"], driver_pos["lng"],
                        destination_coords["lat"], destination_coords["lng"]
                    )["estimated_time"]
                    return time_to_destination
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
        Calcula el tiempo de tránsito desde el destino del viaje actual al nuevo cliente.

        Args:
            driver: Información del conductor
            client_latitude: Latitud del cliente
            client_longitude: Longitud del cliente

        Returns:
            Tiempo de tránsito en minutos
        """
        try:
            # Buscar el viaje activo del conductor para obtener el destino
            active_trip = self.session.exec(
                select(ClientRequest).where(
                    ClientRequest.id_driver_assigned == driver.user_id,
                    ClientRequest.status.in_([
                        StatusEnum.ON_THE_WAY,
                        StatusEnum.ARRIVED,
                        StatusEnum.TRAVELLING
                    ])
                )
            ).first()

            if not active_trip or not active_trip.destination_position:
                # Si no hay viaje activo o destino, usar posición actual del conductor
                driver_pos = self._get_driver_position(driver.user_id)
                if not driver_pos:
                    return 0.0

                # Calcular tiempo desde posición actual al nuevo cliente
                transit_time = get_time_and_distance_from_google(
                    driver_pos["lat"], driver_pos["lng"],
                    client_latitude, client_longitude
                )["estimated_time"]
                return transit_time

            # Calcular tiempo desde el destino del viaje actual al nuevo cliente
            destination_coords = wkb_to_coords(
                active_trip.destination_position)
            transit_time = get_time_and_distance_from_google(
                destination_coords["lat"], destination_coords["lng"],
                client_latitude, client_longitude
            )["estimated_time"]

            return transit_time

        except Exception as e:
            print(f"Error calculando tiempo de tránsito: {e}")
            return 0.0
