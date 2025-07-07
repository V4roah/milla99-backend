from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlmodel import Session, select
from app.models.config_service_value import ConfigServiceValue, FareCalculationResponse
import requests
from app.utils.geo_utils import get_time_and_distance_from_google


class ConfigServiceValueService:
    def __init__(self, session: Session):
        self.session = session

    def create_config_service_value(
        self,
        km_value: float,
        min_value: float,
        tarifa_value: Optional[float] = None,
        weight_value: Optional[float] = None
    ) -> ConfigServiceValue:
        """
        Crea un nuevo registro de ConfigServiceValue
        """
        config_service_value = ConfigServiceValue(
            km_value=km_value,
            min_value=min_value,
            tarifa_value=tarifa_value,
            weight_value=weight_value
        )
        self.session.add(config_service_value)
        self.session.commit()
        self.session.refresh(config_service_value)
        return config_service_value

    def get_config_service_value_by_id(self, id: int) -> Optional[ConfigServiceValue]:
        """
        Busca un registro por ID
        """
        statement = select(ConfigServiceValue).where(
            ConfigServiceValue.service_type_id == id)
        result = self.session.exec(statement).first()
        return result

    def get_config_service_values(self) -> List[ConfigServiceValue]:
        """
        Obtiene todos los registros de ConfigServiceValue
        """
        statement = select(ConfigServiceValue)
        result = self.session.exec(statement).all()
        return result

    def update_config_service_value(
        self,
        id_type_vehicle: int,
        update_data: Dict[str, Any]
    ) -> Optional[ConfigServiceValue]:
        """
        Actualiza un registro según los campos proporcionados
        """
        config_service_value = self.get_config_service_value_by_id(
            id_type_vehicle)
        if not config_service_value:
            return None

        # Actualiza solo los campos proporcionados
        valid_fields = {'km_value', 'min_value',
                        'tarifa_value', 'weight_value'}
        for field, value in update_data.items():
            if field in valid_fields and value is not None:
                setattr(config_service_value, field, value)

        config_service_value.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(config_service_value)
        return config_service_value

    def update_by_vehicle_type_id(self, vehicle_type_id: int, update_data: dict):
        from app.models.config_service_value import ConfigServiceValue
        config = self.session.exec(
            select(ConfigServiceValue).where(
                ConfigServiceValue.service_type_id == vehicle_type_id)
        ).first()
        if not config:
            return None

        valid_fields = {'km_value', 'min_value',
                        'tarifa_value', 'weight_value'}
        for field, value in update_data.items():
            if field in valid_fields and value is not None:
                setattr(config, field, value)

        config.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(config)
        return config

    def get_google_distance_data(self, origin_lat, origin_lng, destination_lat, destination_lng, api_key):
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": f"{origin_lat},{origin_lng}",
            "destinations": f"{destination_lat},{destination_lng}",
            "units": "metric",
            "key": api_key
        }
        response = requests.get(url, params=params)
        if response.status_code != 200:
            raise Exception(
                f"Error en el API de Google Distance Matrix: {response.status_code}")
        data = response.json()
        if data.get("status") != "OK":
            raise Exception(
                f"Error en la respuesta del API de Google Distance Matrix: {data.get('status')}")
        return data

    async def calculate_total_value(self, id: int, google_data: Dict) -> FareCalculationResponse:
        """
        Calcula el valor total basado en los datos de Google y retorna la información necesaria
        """

        try:
            # Obtener el registro de tarifas
            config_service_value = self.get_config_service_value_by_id(id)
            if not config_service_value:
                return None

            # Extraer los datos usando el modelo Pydantic
            element = google_data["rows"][0]["elements"][0]

            # Cálculos
            distance_km = element["distance"]["value"] / 1000.0
            time_minutes = element["duration"]["value"] / 60.00

            # Calcular el costo
            distance_cost = distance_km * config_service_value.km_value
            time_cost = time_minutes * config_service_value.min_value

            total_cost = distance_cost + time_cost

            # Aplicar tarifa mínima si existe
            if config_service_value.tarifa_value is not None:
                total_cost = max(total_cost, config_service_value.tarifa_value)

            return FareCalculationResponse(
                recommended_value=round(total_cost, 2),
                destination_addresses=google_data["destination_addresses"][0],
                origin_addresses=google_data["origin_addresses"][0],
                distance=element["distance"]["text"],
                duration=element["duration"]["text"]
            )

        except Exception as e:
            print(f"Error al calcular el valor total: {str(e)}")
            return None
