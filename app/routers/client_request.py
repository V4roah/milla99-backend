from fastapi import APIRouter, HTTPException, status, Depends, Request, Query, Body, Path
from fastapi.responses import JSONResponse
from app.core.db import get_session
from app.core.dependencies.admin_auth import get_current_admin
from app.models.client_request import ClientRequest, ClientRequestCreate, StatusEnum
from app.models.type_service import TypeService
from app.core.db import SessionDep
from app.services.client_requests_service import (
    check_and_lift_driver_suspension,
    create_client_request,
    driver_canceled_service,
    get_time_and_distance_service,
    get_nearby_client_requests_service,
    assign_driver_service,
    update_status_service,
    get_client_request_detail_service,
    get_client_requests_by_status_service,
    update_client_rating_service,
    update_driver_rating_service,
    get_nearby_drivers_service,
    update_status_by_driver_service,
    client_canceled_service,
    update_review_service,
    get_driver_requests_by_status_service,
    find_optimal_drivers,
    find_optimal_drivers_with_search_service,
    assign_busy_driver,
    get_eta_service
)
from sqlalchemy.orm import Session
import traceback
from pydantic import BaseModel, Field
from app.models.user_has_roles import UserHasRole, RoleStatus
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Security
from app.utils.geo_utils import wkb_to_coords, get_time_and_distance_from_google
from datetime import datetime, timedelta
from app.utils.geo import wkb_to_coords
from uuid import UUID
from app.core.dependencies.auth import get_current_user
import pytz
COLOMBIA_TZ = pytz.timezone("America/Bogota")

bearer_scheme = HTTPBearer()

router = APIRouter(
    prefix="/client-request",
    dependencies=[Depends(get_current_user)]
)


class Position(BaseModel):
    lat: float
    lng: float


class ClientRequestResponse(BaseModel):
    id: UUID
    id_client: UUID
    fare_offered: float | None = None
    fare_assigned: float | None = None
    pickup_description: str | None = None
    destination_description: str | None = None
    client_rating: float | None = None
    driver_rating: float | None = None
    status: str
    pickup_position: Position | None = None
    destination_position: Position | None = None
    type_service_id: int
    type_service_name: str | None = None
    created_at: str
    updated_at: str


class AssignDriverRequest(BaseModel):
    id_client_request: UUID = Field(...,
                                    description="ID de la solicitud de viaje")
    id_driver: UUID = Field(...,
                            description="user_id que tiene como rol Driver")
    fare_assigned: float | None = Field(
        None, description="Tarifa asignada (opcional)")


class CancelClientRequestRequest(BaseModel):
    id_client_request: UUID = Field(...,
                                    description="ID de la solicitud de viaje a cancelar")
    reason: str | None = Field(
        None, description="Razón de la cancelación (opcional)")


class DriverCancelRequest(BaseModel):
    id_client_request: UUID = Field(...,
                                    description="ID de la solicitud de viaje a cancelar")
    reason: str | None = Field(
        None, description="Razón de la cancelación (opcional)")


class ETAResponse(BaseModel):
    distance: float
    duration: float


@router.post("/eta/start-tracking", tags=["Passengers", "Drivers"], description="""
Inicia el seguimiento en tiempo real del ETA (tiempo estimado de llegada) del conductor.
Este endpoint configura las actualizaciones automáticas por WebSocket.

**Parámetros:**
- `client_request_id`: ID de la solicitud de viaje.

**Respuesta:**
- `success`: True si el seguimiento se inició correctamente.
- `message`: Mensaje descriptivo.
- `socket_event`: Nombre del evento WebSocket a escuchar.

**Nota:** El cliente debe conectarse al WebSocket y escuchar el evento `eta_update/{client_request_id}`.
""")
def start_eta_tracking(
    client_request_id: UUID = Body(...,
                                   description="ID de la solicitud de viaje"),
    session: Session = Depends(get_session)
):
    """
    Inicia el seguimiento en tiempo real del ETA del conductor.
    """
    import traceback

    try:
        print(
            f"🔍 DEBUG ETA TRACKING: Iniciando seguimiento para client_request_id: {client_request_id}")

        # Verificar que la solicitud existe y tiene conductor asignado
        from app.models.client_request import ClientRequest

        client_request = session.query(ClientRequest).filter(
            ClientRequest.id == client_request_id).first()

        if not client_request:
            raise HTTPException(
                status_code=404, detail="Solicitud no encontrada")

        if not client_request.id_driver_assigned:
            raise HTTPException(
                status_code=400, detail="No hay conductor asignado a esta solicitud")

        print(
            f"✅ DEBUG ETA TRACKING: Seguimiento iniciado para solicitud {client_request_id}")

        return {
            "success": True,
            "message": "Seguimiento de ETA iniciado correctamente",
            "socket_event": f"eta_update/{client_request_id}",
            "instructions": {
                "connect_websocket": "Conectarse a ws://localhost:8000/ws",
                "listen_event": f"Escuchar evento: eta_update/{client_request_id}",
                "data_format": {
                    "distance": "Distancia en metros",
                    "duration": "Tiempo en segundos",
                    "timestamp": "Timestamp de la actualización"
                }
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ ERROR en start_eta_tracking:")
        print(f"Tipo de error: {type(e).__name__}")
        print(f"Mensaje: {str(e)}")
        print("=== TRACEBACK COMPLETO ===")
        traceback.print_exc()
        print("=== FIN TRACEBACK ===")
        raise HTTPException(
            status_code=500, detail=f"Error iniciando seguimiento: {str(e)}")


@router.get("/eta", response_model=ETAResponse, tags=["Passengers", "Drivers"], description="""
Devuelve el tiempo y la distancia estimados para que el conductor asignado llegue al punto de recogida del pasajero usando Google Distance Matrix.

**Parámetros:**
- `client_request_id`: ID de la solicitud de viaje.

**Respuesta:**
- `distance`: Distancia estimada en metros.
- `duration`: Tiempo estimado en segundos.
""")
def get_eta(
    client_request_id: UUID = Query(...,
                                    description="ID de la solicitud de viaje"),
    session: Session = Depends(get_session)
):
    """
    Calcula el ETA (tiempo estimado de llegada) del conductor al punto de recogida usando Google Distance Matrix.
    """
    import traceback

    try:
        print(
            f"🔍 DEBUG ETA: Iniciando cálculo ETA para client_request_id: {client_request_id}")
        print(f"🔍 DEBUG ETA: Tipo de session: {type(session)}")

        result = get_eta_service(session, client_request_id)
        print(f"✅ DEBUG ETA: Resultado del servicio: {result}")

        response = ETAResponse(**result)
        print(f"✅ DEBUG ETA: Respuesta final: {response}")
        return response

    except Exception as e:
        print(f"❌ ERROR en get_eta:")
        print(f"Tipo de error: {type(e).__name__}")
        print(f"Mensaje: {str(e)}")
        print("=== TRACEBACK COMPLETO ===")
        traceback.print_exc()
        print("=== FIN TRACEBACK ===")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/nearby", tags=["Drivers"], description="""
Obtiene las solicitudes de viaje cercanas a un conductor en un radio de 5 km, filtrando por el tipo de servicio del vehículo del conductor.
""")
async def get_nearby_client_requests(
    request: Request,
    driver_lat: float = Query(..., example=4.708822,
                              description="Latitud del conductor"),
    driver_lng: float = Query(..., example=-74.076542,
                              description="Longitud del conductor"),
    session=Depends(get_session)
):
    try:
        user_id = getattr(request.state, 'user_id', None)
        if user_id is None:
            raise Exception("user_id no está presente en request.state")
        # 1. Verificar que el usuario es DRIVER
        from app.models.user_has_roles import UserHasRole, RoleStatus
        user_role = session.query(UserHasRole).filter(
            UserHasRole.id_user == user_id,
            UserHasRole.id_rol == "DRIVER"
        ).first()
        if not user_role or user_role.status != RoleStatus.APPROVED:
            raise HTTPException(
                status_code=400, detail="El usuario no tiene el rol de conductor aprobado.")
        # 2. Obtener el DriverInfo del conductor
        from app.models.driver_info import DriverInfo
        driver_info = session.query(DriverInfo).filter(
            DriverInfo.user_id == user_id).first()
        if not driver_info:
            raise HTTPException(
                status_code=400, detail="El conductor no tiene información de conductor registrada")
        # 2b. Obtener el vehículo del conductor
        from app.models.vehicle_info import VehicleInfo
        driver_vehicle = session.query(VehicleInfo).filter(
            VehicleInfo.driver_info_id == driver_info.id).first()
        if not driver_vehicle:
            raise HTTPException(
                status_code=400, detail="El conductor no tiene un vehículo registrado")
        # 3. Obtener los tipos de servicio para ese tipo de vehículo
        from app.models.type_service import TypeService
        type_services = session.query(TypeService).filter(
            TypeService.vehicle_type_id == driver_vehicle.vehicle_type_id).all()
        if not type_services:
            raise HTTPException(
                status_code=400, detail="No hay servicios disponibles para el tipo de vehículo del conductor")
        type_service_ids = [ts.id for ts in type_services]
        # 4. Buscar las solicitudes cercanas filtrando por esos type_service_ids
        results = await get_nearby_client_requests_service(
            driver_lat, driver_lng, session, wkb_to_coords, type_service_ids=type_service_ids
        )
        if not results:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": f"No hay solicitudes de viaje activas en un radio de 5000 metros",
                    "data": []
                }
            )
        # Google Distance Matrix
        pickup_positions = [
            f"{r['pickup_position']['lat']},{r['pickup_position']['lng']}" for r in results]
        origins = f"{driver_lat},{driver_lng}"
        destinations = '|'.join(pickup_positions)
        import requests
        from app.core.config import settings
        url = 'https://maps.googleapis.com/maps/api/distancematrix/json'
        params = {
            'destinations': destinations,
            'origins': origins,
            'units': 'metric',
            'key': settings.GOOGLE_API_KEY,
            'mode': 'driving'
        }
        response = requests.get(url, params=params)
        if response.status_code != 200:
            return JSONResponse(
                status_code=status.HTTP_502_BAD_GATEWAY,
                content={
                    "message": f"Error en el API de Google Distance Matrix: {response.status_code}"}
            )
        google_data = response.json()
        if google_data.get('status') != 'OK':
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": f"Error en la respuesta del API de Google Distance Matrix: {google_data.get('status')}"}
            )
        elements = google_data['rows'][0]['elements']
        for index, element in enumerate(elements):
            results[index]['google_distance_matrix'] = element
        return JSONResponse(content=results, status_code=200)
    except Exception as e:
        print("[ERROR] Exception en /nearby:")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail=f"Error al buscar solicitudes cercanas: {str(e)}")


@router.get("/nearby-drivers", description="""
Obtiene los conductores cercanos a un cliente en un radio de 5km, filtrados por el tipo de servicio solicitado.

**Parámetros:**
- `client_lat`: Latitud del cliente.
- `client_lng`: Longitud del cliente.
- `type_service_id`: ID del tipo de servicio solicitado.

**Respuesta:**
Devuelve una lista de conductores cercanos con su información, incluyendo:
- Información del conductor
- Información del vehículo
- Distancia al cliente
- Calificación promedio
- Tiempo estimado de llegada (usando Google Distance Matrix)
""")
def get_nearby_drivers(
    request: Request,
    client_lat: float = Query(..., example=4.708822,
                              description="Latitud del cliente"),
    client_lng: float = Query(..., example=-74.076542,
                              description="Longitud del cliente"),
    type_service_id: int = Query(..., example=1,
                                 description="ID del tipo de servicio solicitado"),
    session: Session = Depends(get_session)
):
    """
    Endpoint para obtener conductores cercanos a un cliente.
    """
    import traceback as tb
    try:
        # Verificar que el usuario es CLIENT
        user_id = request.state.user_id
        user_role = session.query(UserHasRole).filter(
            UserHasRole.id_user == user_id,
            UserHasRole.id_rol == "CLIENT"
        ).first()

        if not user_role or user_role.status != RoleStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail="El usuario no tiene el rol de cliente aprobado"
            )

        results = get_nearby_drivers_service(
            client_lat=client_lat,
            client_lng=client_lng,
            type_service_id=type_service_id,
            session=session,
            wkb_to_coords=wkb_to_coords
        )

        if not results:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "No hay conductores disponibles en un radio de 5km",
                    "data": []
                }
            )

        return JSONResponse(content=results, status_code=200)

    except HTTPException as e:
        print(f"[HTTPException] {e.detail}")
        print(tb.format_exc())
        raise e
    except Exception as e:
        print(f"[ERROR] Exception en get_nearby_drivers: {str(e)}")
        print(tb.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al buscar conductores cercanos: {str(e)}"
        )


@router.get("/{client_request_id}", tags=["Passengers"], description="""
Consulta el estado y la información detallada de una solicitud de viaje específica.

**Permisos de Acceso:**
- El cliente que creó la solicitud puede ver todos los detalles de su solicitud
- El conductor asignado a la solicitud puede ver todos los detalles de la solicitud que le fue asignada
- Otros usuarios no tienen acceso a esta información

**Parámetros:**
- `client_request_id`: ID de la solicitud de viaje.

**Respuesta:**
Incluye el detalle completo de la solicitud, incluyendo:
- Información básica de la solicitud (estado, tarifas, ubicaciones)
- Información del cliente (nombre, teléfono, calificación)
- Información del conductor asignado (si existe)
- Información del vehículo (si hay conductor asignado)
- Método de pago seleccionado
- Review del viaje (si existe)

**Nota de Seguridad:**
Este endpoint implementa validación de permisos para asegurar que solo el cliente dueño de la solicitud o el conductor asignado puedan acceder a la información.
""")
def get_client_request_detail(
    request: Request,
    client_request_id: UUID,
    session: SessionDep
):
    """
    Consulta el estado y la información detallada de una Client Request específica.
    Solo permite acceso al cliente dueño de la solicitud o al conductor asignado.
    """
    user_id = request.state.user_id
    return get_client_request_detail_service(session, client_request_id, user_id)


@router.get("/distance", description="""
Consulta la distancia y el tiempo estimado entre dos puntos usando Google Distance Matrix API.

**Parámetros:**
- `origin_lat`: Latitud de origen.
- `origin_lng`: Longitud de origen.
- `destination_lat`: Latitud de destino.
- `destination_lng`: Longitud de destino.

**Respuesta:**
Devuelve la distancia y el tiempo estimado entre los puntos especificados.
""")
def get_time_and_distance(
    origin_lat: float = Query(..., example=4.718136,
                              description="Latitud de origen"),
    origin_lng: float = Query(..., example=-74.07317,
                              description="Longitud de origen"),
    destination_lat: float = Query(..., example=4.702468,
                                   description="Latitud de destino"),
    destination_lng: float = Query(..., example=-
                                   74.109776, description="Longitud de destino")
):
    """
    Consulta la distancia y el tiempo estimado entre dos puntos usando Google Distance Matrix API.
    Args:
        origin_lat: Latitud de origen
        origin_lng: Longitud de origen
        destination_lat: Latitud de destino
        destination_lng: Longitud de destino
    Returns:
        Respuesta JSON de Google Distance Matrix
    """
    try:
        return get_time_and_distance_service(origin_lat, origin_lng, destination_lat, destination_lng)
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": str(e)})


@router.get("/by-status/{status}", tags=["Passengers"], description="""
Devuelve una lista de solicitudes de viaje del usuario autenticado filtradas por el estado enviado en el parámetro.

**Parámetros:**
- `status`: Estado por el cual filtrar las solicitudes. Debe ser uno de:
  - `CREATED`: Solicitud recién creada, esperando conductor
  - `PENDING`: Solicitud asignada a conductor ocupado, esperando que termine su viaje actual
  - `ACCEPTED`: Conductor asignado, esperando inicio del viaje
  - `ON_THE_WAY`: Conductor en camino al punto de recogida
  - `ARRIVED`: Conductor llegó al punto de recogida
  - `TRAVELLING`: Viaje en curso
  - `FINISHED`: Viaje finalizado, pendiente de pago
  - `PAID`: Viaje pagado y completado
  - `CANCELLED`: Solicitud cancelada

**Respuesta:**
Devuelve una lista de solicitudes de viaje del usuario autenticado con el estado especificado.
Incluye información del conductor asignado (nombre y selfie) para el historial de viajes.
""")
def get_client_requests_by_status(
    request: Request,
    session: SessionDep,
    status: str = Path(..., description="Estado por el cual filtrar las solicitudes. Estados válidos: CREATED, PENDING, ACCEPTED, ON_THE_WAY, ARRIVED, TRAVELLING, FINISHED, PAID, CANCELLED")
):
    """
    Devuelve una lista de solicitudes de viaje del usuario autenticado filtradas por el estatus enviado en el parámetro.
    """
    # Obtener el user_id del token
    user_id = request.state.user_id

    # Validar que el status sea uno de los permitidos
    if status not in StatusEnum.__members__:
        raise HTTPException(
            status_code=400,
            detail=f"Status inválido. Debe ser uno de: {', '.join(StatusEnum.__members__.keys())}"
        )

    # Obtener las solicitudes filtradas por status y user_id
    return get_client_requests_by_status_service(session, status, user_id)


@router.get("/by-driver-status/{status}", tags=["Drivers"], description="""
Devuelve una lista de solicitudes de viaje asociadas a un conductor filtradas por el estado enviado en el parámetro.

**Parámetros:**
- `status`: Estado por el cual filtrar las solicitudes. Debe ser uno de:
  - `ON_THE_WAY`: Conductor en camino al punto de recogida
  - `ARRIVED`: Conductor llegó al punto de recogida
  - `TRAVELLING`: Viaje en curso
  - `FINISHED`: Viaje finalizado, pendiente de pago
  - `PAID`: Viaje pagado y completado
  - `CANCELLED`: Solicitud cancelada
            
**Respuesta:**
Devuelve una lista de solicitudes de viaje asociadas al conductor con el estado especificado.
Incluye información del cliente (nombre y selfie) para el historial de viajes del conductor.
""")
def get_driver_requests_by_status(
    request: Request,
    session: SessionDep,
    status: str = Path(..., description="Estado por el cual filtrar las solicitudes. Estados válidos: ON_THE_WAY, ARRIVED, TRAVELLING, FINISHED, PAID, CANCELLED")
):
    """
    Devuelve una lista de solicitudes de viaje asociadas a un conductor filtradas por el estado enviado en el parámetro.
    Los estados CREATED y ACCEPTED no están disponibles ya que no son relevantes para los conductores.
    """
    # Obtener el user_id del token
    user_id = request.state.user_id

    # Validar que el status sea uno de los permitidos
    valid_states = {"ON_THE_WAY", "ARRIVED",
                    "TRAVELLING", "FINISHED", "PAID", "CANCELLED"}
    if status not in valid_states:
        raise HTTPException(
            status_code=400,
            detail=f"Status inválido. Debe ser uno de: {', '.join(valid_states)}"
        )

    # Obtener las solicitudes filtradas por id_driver_assigned y status
    return get_driver_requests_by_status_service(session, user_id, status)


@router.post("/", response_model=ClientRequestResponse, status_code=status.HTTP_201_CREATED, tags=["Passengers"], description="""
Crea una nueva solicitud de viaje para un cliente.

**Parámetros:**
- `pickup_lat`: Latitud del punto de recogida.
- `pickup_lng`: Longitud del punto de recogida.
- `destination_lat`: Latitud del destino.
- `destination_lng`: Longitud del destino.
- `fare_offered`: Tarifa ofrecida.
- `pickup_description`: Descripción del punto de recogida (opcional).
- `destination_description`: Descripción del destino (opcional).
- `type_service_id`: ID del tipo de servicio (obligatorio, por ejemplo 1 para Car Ride, 2 para Motorcycle Ride)
- `payment_method_id`: ID del método de pago (opcional, 1 para cash, 2 para nequi, 3 para daviplata)

**Respuesta:**
Devuelve la solicitud de viaje creada con toda su información.
""")
def create_request(
    request: Request,
    request_data: ClientRequestCreate = Body(
        ...,
        example={
            "fare_offered": 20,
            "pickup_description": "Suba Bogotá",
            "destination_description": "Santa Rosita Engativa, Bogota",
            "pickup_lat": 4.718136,
            "pickup_lng": -74.073170,
            "destination_lat": 4.702468,
            "destination_lng": -74.109776,
            "type_service_id": 1,  # 1 Car or 2 Motorcycle
            "payment_method_id": 1  # 1 cash, 2 nequi, 3 daviplata
        }
    ),
    session: Session = Depends(get_session)
):
    try:
        user_id = request.state.user_id
        user_role = session.query(UserHasRole).filter(
            UserHasRole.id_user == user_id,
            UserHasRole.id_rol == "CLIENT"
        ).first()
        if not user_role or user_role.status != RoleStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail="El usuario no tiene el rol de cliente aprobado. No puede crear solicitudes."
            )
        db_obj = create_client_request(
            session, request_data, id_client=user_id)
        # Lógica de asignación de conductores ocupados/disponibles usando el nuevo DriverSearchService
        print(f"\n🔍 DEBUGGING: Buscando conductores óptimos...")
        print(f"   - Client Lat: {request_data.pickup_lat}")
        print(f"   - Client Lng: {request_data.pickup_lng}")
        print(f"   - Type Service ID: {request_data.type_service_id}")

        optimal_drivers = find_optimal_drivers_with_search_service(
            session,
            request_data.pickup_lat,
            request_data.pickup_lng,
            request_data.type_service_id
        )

        print(f"   - Conductores encontrados: {len(optimal_drivers)}")
        for i, driver in enumerate(optimal_drivers):
            print(
                f"   - Driver {i+1}: {driver.get('type', 'unknown')} - {driver.get('user_id', 'unknown')}")

        assigned = False
        for driver in optimal_drivers:
            if driver["type"] == "available":
                print(
                    f"   ✅ Asignando conductor disponible: {driver.get('user_id')}")
                assigned = True
                break
        if not assigned:
            print(f"   ⚠️ No hay conductores disponibles, buscando ocupados...")
            for driver in optimal_drivers:
                if driver["type"] == "busy":
                    print(
                        f"   🔄 Asignando conductor ocupado: {driver.get('user_id')}")
                    estimated_pickup_time = datetime.now(
                    ) + timedelta(seconds=driver["estimated_time"])
                    success = assign_busy_driver(
                        session,
                        db_obj.id,
                        driver["user_id"],
                        estimated_pickup_time,
                        driver["current_trip_remaining_time"],
                        driver["transit_time"]
                    )
                    print(
                        f"   - Resultado asignación: {'✅ Éxito' if success else '❌ Falló'}")
                    assigned = True
                    break
            if not assigned:
                print(f"   ❌ No se encontraron conductores disponibles ni ocupados")
        # Obtener el nombre del tipo de servicio
        from app.models.type_service import TypeService
        type_service = session.query(TypeService).filter(
            TypeService.id == db_obj.type_service_id).first()
        response = {
            "id": db_obj.id,
            "id_client": db_obj.id_client,
            "fare_offered": db_obj.fare_offered,
            "fare_assigned": db_obj.fare_assigned,
            "pickup_description": db_obj.pickup_description,
            "destination_description": db_obj.destination_description,
            "client_rating": db_obj.client_rating,
            "driver_rating": db_obj.driver_rating,
            "status": str(db_obj.status),
            "pickup_position": wkb_to_coords(db_obj.pickup_position),
            "destination_position": wkb_to_coords(db_obj.destination_position),
            "created_at": db_obj.created_at.isoformat(),
            "updated_at": db_obj.updated_at.isoformat(),
            "type_service_id": db_obj.type_service_id,
            "type_service_name": type_service.name if type_service else None
        }
        return response
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail=f"Error al crear la solicitud de viaje: {str(e)}"
        )


@router.patch("/updateDriverAssigned", tags=["Passengers"], description="""
Asigna un conductor a una solicitud de viaje existente y actualiza el estado y la tarifa si se proporciona.

**Parámetros:**
- `id_client_request`: ID de la solicitud de viaje.
- `id_driver`: user_id que tiene como rol Driver.
- `fare_assigned`: Tarifa asignada (opcional).

**Respuesta:**
Devuelve un mensaje de éxito o error.
""")
def assign_driver(
    request_data: AssignDriverRequest = Body(
        ...,
        example={
            "id_client_request": "00000000-0000-0000-0000-000000000000",
            "id_driver": "00000000-0000-0000-0000-000000000000",
            "fare_assigned": 25
        }
    ),
    session: Session = Depends(get_session)
):
    try:
        import traceback as tb
        from app.models.client_request import ClientRequest

        # 1. Obtener la solicitud
        client_request = session.query(ClientRequest).filter(
            ClientRequest.id == request_data.id_client_request).first()
        if not client_request:
            raise HTTPException(
                status_code=404, detail="Solicitud no encontrada")

        # 2. Obtener el tipo de servicio de la solicitud
        type_service = session.query(TypeService).filter(
            TypeService.id == client_request.type_service_id).first()
        if not type_service:
            raise HTTPException(
                status_code=404, detail="Tipo de servicio no encontrado")

        # 3. Obtener el vehículo del conductor
        from app.models.driver_info import DriverInfo
        from app.models.vehicle_info import VehicleInfo

        driver_info = session.query(DriverInfo).filter(
            DriverInfo.user_id == request_data.id_driver).first()
        if not driver_info:
            raise HTTPException(
                status_code=404, detail="El conductor no tiene información registrada")

        vehicle = session.query(VehicleInfo).filter(
            VehicleInfo.driver_info_id == driver_info.id).first()
        if not vehicle:
            raise HTTPException(
                status_code=404, detail="El conductor no tiene vehículo registrado")

        # 4. Validar compatibilidad de tipo de vehículo
        if vehicle.vehicle_type_id != type_service.vehicle_type_id:
            raise HTTPException(
                status_code=400,
                detail="El conductor no tiene un vehículo compatible con el tipo de servicio solicitado"
            )

        # Verificar si el conductor está ocupado (tiene un viaje activo)
        from app.models.driver_info import DriverInfo

        # Buscar si el conductor tiene un viaje activo
        active_request = session.query(ClientRequest).filter(
            ClientRequest.id_driver_assigned == request_data.id_driver,
            ClientRequest.status.in_([
                "ON_THE_WAY", "ARRIVED", "TRAVELLING"
            ])
        ).first()

        if active_request:
            # El conductor está ocupado, usar assign_busy_driver
            from app.services.client_requests_service import (
                assign_busy_driver,
                calculate_busy_driver_total_time,
                get_busy_driver_config,
                calculate_remaining_trip_time,
                calculate_transit_time
            )
            from datetime import datetime, timedelta

            # Obtener la nueva solicitud para calcular tiempos
            new_request = session.query(ClientRequest).filter(
                ClientRequest.id == request_data.id_client_request
            ).first()

            if not new_request:
                raise HTTPException(
                    status_code=404, detail="Solicitud no encontrada")

            # Calcular tiempos dinámicamente
            config = get_busy_driver_config(session)

            # Calcular tiempo restante del viaje actual (en minutos)
            remaining_time = calculate_remaining_trip_time(
                active_request) / 60.0

            # Calcular tiempo de tránsito al nuevo cliente (en minutos)
            transit_time = calculate_transit_time(
                active_request,
                new_request.pickup_lat,
                new_request.pickup_lng
            ) / 60.0

            print(f"🔍 Tiempos calculados dinámicamente:")
            print(
                f"   - Tiempo restante del viaje actual: {remaining_time:.2f} minutos")
            print(
                f"   - Tiempo de tránsito al nuevo cliente: {transit_time:.2f} minutos")
            print(
                f"   - Tiempo total: {remaining_time + transit_time:.2f} minutos")

            # Calcular tiempo estimado de recogida
            estimated_pickup_time = datetime.now(
                COLOMBIA_TZ) + timedelta(minutes=remaining_time + transit_time)

            success = assign_busy_driver(
                session,
                request_data.id_client_request,
                request_data.id_driver,
                estimated_pickup_time,
                remaining_time,
                transit_time
            )

            if success:
                return {"success": True, "message": "Conductor ocupado asignado correctamente como pendiente"}
            else:
                raise HTTPException(
                    status_code=409,
                    detail="Conductor ocupado no cumple con las validaciones de distancia, tiempo total o tiempo de tránsito"
                )
        else:
            # El conductor está disponible, usar assign_driver_service normal
            return assign_driver_service(
                session,
                request_data.id_client_request,
                request_data.id_driver,
                request_data.fare_assigned
            )
    except HTTPException as e:
        print("[HTTPException]", e.detail)
        print(tb.format_exc())
        raise e
    except Exception as e:
        print("[ERROR] Exception en assign_driver:")
        print(tb.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al asignar el conductor: {str(e)}"
        )


# @router.patch("/updateStatus", description="""
# Actualiza el estado de una solicitud de viaje existente.

# **Parámetros:**
# - `id_client_request`: ID de la solicitud de viaje.
# - `status`: Nuevo estado a asignar.

# **Respuesta:**
# Devuelve un mensaje de éxito o error.
# """)
def update_status(
    id_client_request: UUID = Body(...,
                                   description="ID de la solicitud de viaje"),
    status: str = Body(..., description="Nuevo estado a asignar"),
    session: Session = Depends(get_session)
):
    """
    Actualiza el estado de una solicitud de viaje existente.
    Args:
        id_client_request: ID de la solicitud de viaje
        status: Nuevo estado a asignar
        session: Sesión de base de datos
    Returns:
        Mensaje de éxito o error
    """
    try:
        return update_status_service(session, id_client_request, status)
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Error al actualizar el status: {str(e)}")


@router.patch("/updateClientRating", tags=["Drivers"], description="""
Actualiza la calificación del cliente para una solicitud de viaje. Solo el conductor asignado puede calificar al cliente.
Solo se permite calificar cuando el viaje está en estado PAID.

**Parámetros:**
- `id_client_request`: ID de la solicitud de viaje.
- `client_rating`: Nueva calificación del cliente.

**Respuesta:**
Devuelve un mensaje de éxito o error.
""")
def update_client_rating(
    request: Request,
    id_client_request: UUID = Body(...,
                                   description="ID de la solicitud de viaje"),
    client_rating: float = Body(...,
                                description="Nueva calificación del cliente"),
    session: Session = Depends(get_session)
):
    """
    Actualiza la calificación del cliente para una solicitud de viaje.
    Solo el conductor asignado puede calificar al cliente.
    Solo se permite calificar cuando el viaje está en estado PAID.
    """
    user_id = request.state.user_id
    return update_client_rating_service(session, id_client_request, client_rating, user_id)


@router.patch("/updateDriverRating", tags=["Passengers"], description="""
Actualiza la calificación del conductor para una solicitud de viaje. Solo el cliente puede calificar al conductor.
Solo se permite calificar cuando el viaje está en estado PAID.

**Parámetros:**
- `id_client_request`: ID de la solicitud de viaje.
- `driver_rating`: Nueva calificación del conductor.

**Respuesta:**
Devuelve un mensaje de éxito o error.
""")
def update_driver_rating(
    request: Request,
    id_client_request: UUID = Body(...,
                                   description="ID de la solicitud de viaje"),
    driver_rating: float = Body(...,
                                description="Nueva calificación del conductor"),
    session: Session = Depends(get_session)
):
    """
    Actualiza la calificación del conductor para una solicitud de viaje.
    Solo el cliente puede calificar al conductor.
    Solo se permite calificar cuando el viaje está en estado PAID.
    """
    user_id = request.state.user_id
    return update_driver_rating_service(session, id_client_request, driver_rating, user_id)


@router.get("/drivers-check-suspension", tags=["Drivers"], description="""
            Permite verificar y levantar la suspensión de un conductor específico.""")
def check_driver_suspension_api(
    request: Request,
    session: Session = Depends(get_session)
):
    try:
        driver_id = request.state.user_id
        result = check_and_lift_driver_suspension(session, driver_id)
        return result
    except ValueError as e:
        print(f"ValueError: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[ERROR] Exception en check_driver_suspension: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/updateStatusByDriver", tags=["Drivers"], description="""
Actualiza el estado de una solicitud de viaje, solo permitido para conductores (DRIVER).

**Parámetros:**
- `id_client_request`: ID de la solicitud de viaje.
- `status`: Nuevo estado a asignar (solo ON_THE_WAY, ARRIVED, TRAVELLING, FINISHED, PAID).

**Nota:** El estado PAID puede ser asignado por el conductor cuando el viaje está en estado FINISHED.

**Respuesta:**
Devuelve un mensaje de éxito o error.
""")
def update_status_by_driver(
    request: Request,
    id_client_request: UUID = Body(...,
                                   description="ID de la solicitud de viaje"),
    status: str = Body(..., description="Nuevo estado a asignar"),
    session: Session = Depends(get_session)
):
    """
    Permite al conductor cambiar el estado de la solicitud solo a los estados permitidos.
    """
    user_id = getattr(request.state, 'user_id', None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return update_status_by_driver_service(session, id_client_request, status, user_id)


@router.patch("/clientCanceled", tags=["Passengers"], description="""
Cancela una solicitud de viaje por parte del cliente. Solo se permite cancelar solicitudes en estado CREATED, ACCEPTED, ON_THE_WAY o ARRIVED.

**Parámetros:**
- `id_client_request`: ID de la solicitud de viaje a cancelar.

**Respuesta:**
Devuelve un mensaje de éxito o error.
""")
def update_status_by_client(
    request: Request,
    id_client_request: UUID = Body(..., embed=True,
                                   description="ID de la solicitud de viaje a cancelar"),
    session: Session = Depends(get_session)
):
    """
    Permite al cliente cancelar su solicitud de viaje.
    Solo se permite cancelar solicitudes en estado CREATED, ACCEPTED, ON_THE_WAY o ARRIVED.
    """
    user_id = getattr(request.state, 'user_id', None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return client_canceled_service(session, id_client_request, user_id)


@router.patch("/updateReview", tags=["Passengers"], description="""
Actualiza el review de una solicitud de viaje. Solo el cliente puede agregar un review.
Solo se permite agregar un review cuando el viaje está en estado PAID.

**Parámetros:**
- `id_client_request`: ID de la solicitud de viaje.
- `review`: Review a agregar (máximo 255 caracteres).

**Respuesta:**
Devuelve un mensaje de éxito o error.
""")
def update_review(
    request: Request,
    id_client_request: UUID = Body(...,
                                   description="ID de la solicitud de viaje"),
    review: str = Body(...,
                       description="Review a agregar (máximo 255 caracteres)"),
    session: Session = Depends(get_session)
):
    """
    Permite al cliente agregar un review a su solicitud de viaje.
    Solo se permite cuando el viaje está en estado PAID.
    """
    user_id = request.state.user_id
    return update_review_service(session, id_client_request, review, user_id)


@router.patch("/driver-canceled", tags=["Drivers"], description="""
Permite al conductor cancelar una solicitud de viaje con diferentes reglas según el estado:

**Estados permitidos y consecuencias:**
- `ARRIVED`: Cancelación justificada (cliente no apareció) - Sin penalización
- `ACCEPTED`: Cancelación injustificada - Cuenta para suspensión 
- `ON_THE_WAY`: Cancelación injustificada - Cuenta para suspensión

**Límites de cancelación:**
- Máximo 3 cancelaciones por día
- Máximo 10 cancelaciones por semana
- Suspensión automática de 7 días al exceder límites

**Parámetros:**
- `id_client_request`: ID de la solicitud de viaje a cancelar
- `reason`: Razón opcional de la cancelación

**Respuesta:**
Devuelve un mensaje de éxito con información sobre el impacto de la cancelación.
""")
def driver_cancel_request(
    request: Request,
    cancel_data: DriverCancelRequest = Body(...,
                                            example={
                                                "id_client_request": "00000000-0000-0000-0000-000000000000",
                                                "reason": "Cliente no apareció en el punto de recogida"
                                            }
                                            ),
    session: Session = Depends(get_session)
):
    """
    Permite al conductor cancelar una solicitud de viaje.
    Solo se pueden cancelar solicitudes en estado ARRIVED (cuando el conductor ha llegado al punto de recogida).
    """
    user_id = getattr(request.state, 'user_id', None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return driver_canceled_service(session, cancel_data.id_client_request, user_id, cancel_data.reason)
