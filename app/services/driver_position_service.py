from sqlmodel import Session
from app.models.driver_position import DriverPosition, DriverPositionCreate, DriverPositionRead
from app.models.user import User
from fastapi import HTTPException, status
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select, text, func
from app.models.user_has_roles import UserHasRole, RoleStatus
from app.models.role import Role
from app.utils.geo import wkb_to_coords
from uuid import UUID


class DriverPositionService:
    def __init__(self, session: Session):
        self.session = session

    def create_driver_position(self, data: DriverPositionCreate) -> DriverPosition:
        user = self.session.get(User, data.id_driver)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

        # Validar que el usuario tenga el rol DRIVER aprobado
        driver_role = self.session.exec(
            select(UserHasRole).where(
                UserHasRole.id_user == data.id_driver,
                UserHasRole.id_rol == "DRIVER",
            )
        ).first()
        if not driver_role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="El usuario no tiene el rol de conductor aprobado")

        # Verifica si ya existe una posición para este driver
        existing = self.session.get(DriverPosition, data.id_driver)
        point = from_shape(Point(data.lng, data.lat), srid=4326)
        if existing:
            existing.position = point
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing

        driver_position = DriverPosition(
            id_driver=data.id_driver,
            position=point
        )
        self.session.add(driver_position)
        self.session.commit()
        self.session.refresh(driver_position)
        return driver_position

    def get_nearby_drivers(self, lat: float, lng: float, max_distance_km: float):
        max_distance_m = max_distance_km * 1000  # Convertir a metros
        driver_point = func.ST_GeomFromText(f'POINT({lng} {lat})', 4326)
        query = (
            self.session.query(
                DriverPosition.id_driver,
                func.ST_X(DriverPosition.position).label("lng"),
                func.ST_Y(DriverPosition.position).label("lat"),
                (func.ST_Distance_Sphere(DriverPosition.position,
                 driver_point) / 1000).label("distance_km")
            )
            .filter(
                func.ST_Distance_Sphere(
                    DriverPosition.position, driver_point) <= max_distance_m
            )
            .order_by("distance_km")
        )
        results = query.all()
        drivers = []
        for row in results:
            drivers.append(DriverPositionRead(
                id_driver=row[0],
                lat=row[2],
                lng=row[1],
                distance_km=round(row[3], 3)
            ))
        return drivers

    def get_driver_position(self, id_driver: UUID):
        return self.session.get(DriverPosition, id_driver)

    def delete_driver_position(self, id_driver: UUID):
        obj = self.session.get(DriverPosition, id_driver)
        if not obj:
            return False
        self.session.delete(obj)
        self.session.commit()
        return True

    def get_nearby_drivers_by_client_request(self, id_client_request: UUID):
        from app.models.client_request import ClientRequest
        from app.models.type_service import TypeService
        from app.models.vehicle_info import VehicleInfo
        from app.models.driver_info import DriverInfo
        from app.models.user import User
        from app.models.driver_position import DriverPosition
        from sqlalchemy import select

        # 1. Obtener la solicitud de viaje
        client_request = self.session.query(ClientRequest).filter(
            ClientRequest.id == id_client_request).first()
        if not client_request:
            raise HTTPException(
                status_code=404, detail="Client request no encontrada")

        # 2. Obtener el tipo de servicio
        type_service = self.session.query(TypeService).filter(
            TypeService.id == client_request.type_service_id).first()
        if not type_service:
            raise HTTPException(
                status_code=404, detail="Tipo de servicio no encontrado")

        # 3. Obtener el tipo de vehículo requerido
        vehicle_type_id = type_service.vehicle_type_id

        # 4. Buscar todos los conductores con vehículo compatible y posición actual
        # Usar DriverPosition para obtener la posición
        allowed_role = type_service.allowed_role
        results = (
            self.session.query(User, DriverInfo, VehicleInfo, DriverPosition)
            .join(DriverInfo, DriverInfo.user_id == User.id)
            .join(VehicleInfo, VehicleInfo.driver_info_id == DriverInfo.id)
            .join(DriverPosition, DriverPosition.id_driver == User.id)
            .join(UserHasRole, UserHasRole.id_user == User.id)
            .filter(
                VehicleInfo.vehicle_type_id == vehicle_type_id,
                UserHasRole.id_rol == allowed_role,
                UserHasRole.status == RoleStatus.APPROVED
            )
            .all()
        )

        drivers = []
        for user, driver_info, vehicle_info, driver_position in results:
            coords = None
            if driver_position and driver_position.position:
                coords = wkb_to_coords(driver_position.position)
            drivers.append({
                "user_id": user.id,
                "full_name": user.full_name,
                "phone_number": user.phone_number,
                "driver_info": {
                    "id": driver_info.id,
                    "first_name": driver_info.first_name,
                    "last_name": driver_info.last_name,
                    "email": driver_info.email,
                    "selfie_url": user.selfie_url
                },
                "vehicle_info": {
                    "id": vehicle_info.id,
                    "brand": vehicle_info.brand,
                    "model": vehicle_info.model,
                    "model_year": vehicle_info.model_year,
                    "color": vehicle_info.color,
                    "plate": vehicle_info.plate,
                    "vehicle_type_id": vehicle_info.vehicle_type_id
                },
                "current_position": coords
            })

        return {
            "client_request_id": client_request.id,
            "type_service": {
                "id": type_service.id,
                "name": type_service.name,
                "vehicle_type_id": type_service.vehicle_type_id
            },
            "drivers": drivers
        }

    def get_driver_position_by_client_request(self, id_client_request: UUID):
        from app.models.client_request import ClientRequest
        from app.models.driver_info import DriverInfo
        from app.models.vehicle_info import VehicleInfo
        from app.models.user import User
        from app.services.client_requests_service import wkb_to_coords

        # 1. Obtener la solicitud de viaje
        client_request = self.session.query(ClientRequest).filter(
            ClientRequest.id == id_client_request).first()
        if not client_request:
            raise HTTPException(
                status_code=404, detail="Client request no encontrada")

        # 2. Verificar que tenga conductor asignado
        driver_id = client_request.id_driver_assigned
        if not driver_id:
            raise HTTPException(
                status_code=404, detail="La solicitud no tiene conductor asignado")

        # 3. Obtener info del conductor
        user = self.session.query(User).filter(User.id == driver_id).first()
        driver_info = self.session.query(DriverInfo).filter(
            DriverInfo.user_id == driver_id).first()
        vehicle_info = self.session.query(VehicleInfo).filter(
            VehicleInfo.driver_info_id == driver_info.id).first() if driver_info else None

        if not driver_info or not driver_info.current_position:
            raise HTTPException(
                status_code=404, detail="El conductor no tiene posición registrada")

        driver_position = wkb_to_coords(driver_info.current_position)

        return {
            "driver_id": user.id,
            "full_name": user.full_name,
            "current_position": driver_position,
            "vehicle": {
                "brand": vehicle_info.brand if vehicle_info else None,
                "model": vehicle_info.model if vehicle_info else None,
                "plate": vehicle_info.plate if vehicle_info else None
            } if vehicle_info else None
        }
