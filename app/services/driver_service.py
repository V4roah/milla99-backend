from sqlmodel import Session, select
from fastapi import HTTPException, status, UploadFile
from app.models.driver_documents import DriverDocuments, DriverDocumentsCreate
from app.models.project_settings import ProjectSettings
from app.models.user import User, UserCreate, UserRead
from app.models.role import Role
from app.models.driver_info import DriverInfo, DriverInfoCreate
from app.models.vehicle_info import VehicleInfo, VehicleInfoCreate
from app.models.driver import DriverFullRead, DriverDocumentsInput
from app.core.db import engine
from app.services.upload_service import upload_service, DocumentType
from typing import Optional, Dict
from app.models.driver_response import (
    DriverFullResponse, UserResponse, DriverInfoResponse, VehicleInfoResponse, DriverDocumentsResponse
)
from app.utils.uploads import uploader
from decimal import Decimal
import traceback
from app.models.verify_mount import VerifyMount
from app.models.transaction import Transaction, TransactionType
import uuid
from app.core.config import settings
import os
from app.models.driver_savings import DriverSavings, SavingsType
from app.models.client_request import ClientRequest, StatusEnum
from app.models.user_has_roles import UserHasRole, RoleStatus
from datetime import datetime
import pytz
from uuid import UUID

COLOMBIA_TZ = pytz.timezone("America/Bogota")


class DriverService:
    def __init__(self, session: Session):
        self.session = session

    async def create_driver(
        self,
        user_data: UserCreate,
        driver_info_data: DriverInfoCreate,
        vehicle_info_data: VehicleInfoCreate,
        driver_documents_data: DriverDocumentsInput,
        selfie: UploadFile = None
    ) -> DriverFullResponse:
        print("\n=== INICIANDO CREACIÓN DE DRIVER ===")
        with Session(engine) as session:
            try:
                print("1. Verificando usuario existente...")
                # Buscar usuario por teléfono y país
                existing_user = session.exec(
                    select(User).where(
                        User.phone_number == user_data.phone_number,
                        User.country_code == user_data.country_code
                    )
                ).first()

                if existing_user:
                    print(f"Usuario existente encontrado: {existing_user.id}")
                    # Verificar si ya tiene el rol DRIVER
                    driver_role = session.exec(
                        select(Role).where(Role.id == "DRIVER")).first()
                    if not driver_role:
                        raise HTTPException(
                            status_code=500, detail="Rol DRIVER no existe")
                    
                    # Verificar si ya tiene rol CLIENT
                    client_role = session.exec(
                        select(Role).where(Role.id == "CLIENT")).first()
                    if not client_role:
                        raise HTTPException(
                            status_code=500, detail="Rol CLIENT no existe")
                    
                    # Verificar si ya tiene rol DRIVER asignado
                    existing_driver_role = session.exec(
                        select(UserHasRole).where(
                            UserHasRole.id_user == existing_user.id,
                            UserHasRole.id_rol == "DRIVER"
                        )
                    ).first()
                    
                    # Verificar si ya tiene rol CLIENT asignado
                    existing_client_role = session.exec(
                        select(UserHasRole).where(
                            UserHasRole.id_user == existing_user.id,
                            UserHasRole.id_rol == "CLIENT"
                        )
                    ).first()
                    
                    if existing_driver_role:
                        # Ya es conductor, verificar si ya tiene driver_info
                        existing_driver = session.exec(
                            select(DriverInfo)
                            .where(DriverInfo.user_id == existing_user.id)
                        ).first()
                        if existing_driver:
                            driver_info = session.exec(
                                select(DriverInfo).where(
                                    DriverInfo.id == existing_driver.id)
                            ).first()
                            vehicle_info = session.exec(
                                select(VehicleInfo).where(
                                    VehicleInfo.driver_info_id == driver_info.id,
                                    VehicleInfo.vehicle_type_id == 1
                                )
                            ).first()
                            if vehicle_info:
                                raise HTTPException(
                                    status_code=400,
                                    detail="Ya existe un conductor de tipo carro para este usuario.")
                        user = existing_user
                    else:
                        # Asignar el rol DRIVER
                        existing_user.roles.append(driver_role)
                        
                        # Si no tiene rol CLIENT, asignarlo también
                        if not existing_client_role:
                            existing_user.roles.append(client_role)
                            print("Rol CLIENT asignado automáticamente al conductor")
                        
                        session.add(existing_user)
                        session.commit()
                        session.refresh(existing_user)
                        user = existing_user
                else:
                    print("2. Creando nuevo usuario...")
                    # Crear el Usuario
                    user = User(**user_data.dict())
                    session.add(user)
                    session.commit()
                    session.refresh(user)
                    print(f"Usuario creado con ID: {user.id}")

                    print("3. Creando DriverSavings...")
                    # Crear DriverSavings con mount=0
                    driver_savings = DriverSavings(
                        mount=0, user_id=user.id, status=SavingsType.SAVING)
                    session.add(driver_savings)
                    session.commit()
                    session.refresh(driver_savings)
                    print("DriverSavings creado")

                    print("4. Asignando roles DRIVER y CLIENT...")
                    # Asignar el rol DRIVER
                    driver_role = session.exec(
                        select(Role).where(Role.id == "DRIVER")).first()
                    if not driver_role:
                        raise HTTPException(
                            status_code=500, detail="Rol DRIVER no existe")
                    
                    # Asignar el rol CLIENT también
                    client_role = session.exec(
                        select(Role).where(Role.id == "CLIENT")).first()
                    if not client_role:
                        raise HTTPException(
                            status_code=500, detail="Rol CLIENT no existe")
                    
                    # Asignar ambos roles
                    user.roles.append(driver_role)
                    user.roles.append(client_role)
                    session.add(user)
                    session.commit()
                    session.refresh(user)
                    print("Roles DRIVER y CLIENT asignados")

                print("5. Procesando selfie...")
                # --- SELFIE OBLIGATORIA Y GUARDADO ---
                if not selfie:
                    raise HTTPException(
                        status_code=400,
                        detail="El campo 'selfie' es obligatorio para crear un conductor."
                    )
                selfie_dir = os.path.join("static", "uploads", "users")
                os.makedirs(selfie_dir, exist_ok=True)
                selfie_ext = os.path.splitext(selfie.filename)[-1] or ".jpg"
                selfie_filename = f"selfie_{user.phone_number}_{uuid.uuid4().hex}{selfie_ext}"
                selfie_path = os.path.join(selfie_dir, selfie_filename)
                # Evitar sobrescribir
                while os.path.exists(selfie_path):
                    selfie_filename = f"selfie_{user.phone_number}_{uuid.uuid4().hex}{selfie_ext}"
                    selfie_path = os.path.join(selfie_dir, selfie_filename)
                print(f"Guardando selfie en: {selfie_path}")
                with open(selfie_path, "wb") as f:
                    f.write(await selfie.read())
                selfie_url = f"{settings.STATIC_URL_PREFIX}/users/{selfie_filename}"
                user.selfie_url = selfie_url
                session.add(user)
                session.commit()
                session.refresh(user)
                print("Selfie guardada y URL actualizada")

                print("6. Creando VerifyMount...")
                # Crear VerifyMount con mount=0
                verify_mount = VerifyMount(user_id=user.id, mount=0)
                session.add(verify_mount)
                session.commit()
                session.refresh(verify_mount)
                print("VerifyMount creado")

                print("7. Creando DriverInfo...")
                # 4. Crear el DriverInfo (ya no maneja selfie_url)
                driver_info = DriverInfo(
                    **driver_info_data.dict(),
                    user_id=user.id
                )
                session.add(driver_info)
                session.commit()
                session.refresh(driver_info)
                print(f"DriverInfo creado con ID: {driver_info.id}")

                print("8. Creando VehicleInfo...")
                # 5. Crear el VehicleInfo
                vehicle_info = VehicleInfo(
                    **vehicle_info_data.dict(),
                    driver_info_id=driver_info.id
                )
                session.add(vehicle_info)
                session.commit()
                session.refresh(vehicle_info)
                print(f"VehicleInfo creado con ID: {vehicle_info.id}")

                print("9. Procesando documentos...")
                # 6. Manejar los documentos
                docs = []

                # Función auxiliar para manejar la subida de documentos
                async def handle_document_upload(
                    file: Optional[UploadFile],
                    doc_type: str,
                    side: Optional[str] = None,
                    existing_url: Optional[str] = None
                ) -> Optional[str]:
                    if file:
                        doc_info = await upload_service.save_document_dbtype(
                            file=file,
                            driver_id=driver_info.id,
                            document_type=doc_type,
                            side=side,
                            description=f"{doc_type} {side if side else ''}"
                        )
                        return uploader.get_file_url(doc_info["url"])
                    return existing_url

                # Tarjeta de propiedad
                if driver_documents_data.property_card_front or driver_documents_data.property_card_back:
                    property_front_url = await handle_document_upload(
                        driver_documents_data.property_card_front,
                        "property_card",
                        "front",
                        driver_documents_data.property_card_front_url
                    )
                    property_back_url = await handle_document_upload(
                        driver_documents_data.property_card_back,
                        "property_card",
                        "back",
                        driver_documents_data.property_card_back_url
                    )
                    docs.append(DriverDocuments(
                        driver_info_id=driver_info.id,
                        vehicle_info_id=vehicle_info.id,
                        document_type_id=1,  # 1 = Tarjeta de propiedad
                        document_front_url=property_front_url,
                        document_back_url=property_back_url,
                        expiration_date=None
                    ))

                # Licencia de conducir
                if (driver_documents_data.license_front or driver_documents_data.license_back or
                        driver_documents_data.license_expiration_date):
                    license_front_url = await handle_document_upload(
                        driver_documents_data.license_front,
                        "license",
                        "front",
                        driver_documents_data.license_front_url
                    )
                    license_back_url = await handle_document_upload(
                        driver_documents_data.license_back,
                        "license",
                        "back",
                        driver_documents_data.license_back_url
                    )
                    docs.append(DriverDocuments(
                        driver_info_id=driver_info.id,
                        vehicle_info_id=vehicle_info.id,
                        document_type_id=2,  # 2 = Licencia
                        document_front_url=license_front_url,
                        document_back_url=license_back_url,
                        expiration_date=driver_documents_data.license_expiration_date
                    ))

                # SOAT
                if driver_documents_data.soat or driver_documents_data.soat_expiration_date:
                    soat_url = await handle_document_upload(
                        driver_documents_data.soat,
                        "soat",
                        None,
                        driver_documents_data.soat_url
                    )
                    docs.append(DriverDocuments(
                        driver_info_id=driver_info.id,
                        vehicle_info_id=vehicle_info.id,
                        document_type_id=3,  # 3 = SOAT
                        document_front_url=soat_url,
                        expiration_date=driver_documents_data.soat_expiration_date
                    ))

                # Tecnomecánica
                if (driver_documents_data.vehicle_technical_inspection or
                        driver_documents_data.vehicle_technical_inspection_expiration_date):
                    tech_url = await handle_document_upload(
                        driver_documents_data.vehicle_technical_inspection,
                        "technical_inspections",
                        None,
                        driver_documents_data.vehicle_technical_inspection_url
                    )
                    docs.append(DriverDocuments(
                        driver_info_id=driver_info.id,
                        vehicle_info_id=vehicle_info.id,
                        document_type_id=4,  # 4 = Tecnomecánica
                        document_front_url=tech_url,
                        expiration_date=driver_documents_data.vehicle_technical_inspection_expiration_date
                    ))

                for doc in docs:
                    session.add(doc)
                session.commit()

                # Consultar documentos actualizados desde la base de datos
                property_card_doc = session.exec(
                    select(DriverDocuments).where(
                        DriverDocuments.driver_info_id == driver_info.id,
                        DriverDocuments.document_type_id == 1
                    )
                ).first()

                license_doc = session.exec(
                    select(DriverDocuments).where(
                        DriverDocuments.driver_info_id == driver_info.id,
                        DriverDocuments.document_type_id == 2
                    )
                ).first()

                soat_doc = session.exec(
                    select(DriverDocuments).where(
                        DriverDocuments.driver_info_id == driver_info.id,
                        DriverDocuments.document_type_id == 3
                    )
                ).first()

                vehicle_tech_doc = session.exec(
                    select(DriverDocuments).where(
                        DriverDocuments.driver_info_id == driver_info.id,
                        DriverDocuments.document_type_id == 4
                    )
                ).first()

                session.refresh(user)
                print(
                    f"DEBUG selfie_url del usuario REFRESH: {user.selfie_url}")
                response = DriverFullResponse(
                    user=UserResponse(
                        id=user.id,
                        full_name=user.full_name,
                        country_code=user.country_code,
                        phone_number=user.phone_number,
                        selfie_url=user.selfie_url
                    ),
                    driver_info=DriverInfoResponse(
                        first_name=driver_info.first_name,
                        last_name=driver_info.last_name,
                        birth_date=str(driver_info.birth_date),
                        email=driver_info.email,
                        selfie_url=user.selfie_url
                    ),
                    vehicle_info=VehicleInfoResponse(
                        brand=vehicle_info.brand,
                        model=vehicle_info.model,
                        model_year=vehicle_info.model_year,
                        color=vehicle_info.color,
                        plate=vehicle_info.plate,
                        vehicle_type_id=vehicle_info.vehicle_type_id
                    ),
                    driver_documents=DriverDocumentsResponse(
                        property_card_front_url=property_card_doc.document_front_url if property_card_doc else None,
                        property_card_back_url=property_card_doc.document_back_url if property_card_doc else None,
                        license_front_url=license_doc.document_front_url if license_doc else None,
                        license_back_url=license_doc.document_back_url if license_doc else None,
                        license_expiration_date=str(
                            license_doc.expiration_date) if license_doc and license_doc.expiration_date else None,
                        soat_url=soat_doc.document_front_url if soat_doc else None,
                        soat_expiration_date=str(
                            soat_doc.expiration_date) if soat_doc and soat_doc.expiration_date else None,
                        vehicle_technical_inspection_url=vehicle_tech_doc.document_front_url if vehicle_tech_doc else None,
                        vehicle_technical_inspection_expiration_date=str(
                            vehicle_tech_doc.expiration_date) if vehicle_tech_doc and vehicle_tech_doc.expiration_date else None
                    )
                )
                existing_user = session.exec(
                    select(ProjectSettings).where(ProjectSettings.id == 1)).first()
                bonus = Decimal(existing_user.bonus)
                # Crear transacción de bono y actualizar mount
                bonus_transaction = Transaction(
                    user_id=user.id,
                    income=bonus,
                    expense=0,
                    type=TransactionType.BONUS,
                    client_request_id=None
                )
                session.add(bonus_transaction)
                session.commit()
                # Actualizar el mount en VerifyMount
                verify_mount.mount += bonus
                session.add(verify_mount)
                session.commit()

                return response

            except Exception as e:
                session.rollback()
                print(f"Error en create_driver: {str(e)}")
                print(traceback.format_exc())
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error al crear el conductor: {str(e)}"
                )

    def get_driver_detail_service(self, session: Session, driver_id: int):
        """
        Devuelve la información personal, de usuario y del vehículo de un conductor dado su driver_id.
        """
        from app.models.driver_info import DriverInfo
        from app.models.user import User
        from app.models.vehicle_info import VehicleInfo
        from sqlalchemy import select

        driver_info = session.get(DriverInfo, driver_id)
        if not driver_info:
            raise HTTPException(
                status_code=404, detail="DriverInfo no encontrado")

        # Obtener el usuario asociado
        user = session.get(User, driver_info.user_id)
        user_data = {
            "id": user.id,
            "full_name": user.full_name,
            "country_code": user.country_code,
            "phone_number": user.phone_number
        } if user else None

        # Obtener el vehículo asociado
        vehicle_info = session.exec(
            select(VehicleInfo).where(
                VehicleInfo.driver_info_id == driver_info.id)
        ).scalars().first()

        vehicle_data = {
            "brand": vehicle_info.brand,
            "model": vehicle_info.model,
            "model_year": vehicle_info.model_year,
            "color": vehicle_info.color,
            "plate": vehicle_info.plate,
            "vehicle_type_id": vehicle_info.vehicle_type_id
        } if vehicle_info else None

        return {
            "user": user_data,
            "driver_info": {
                "id": driver_info.id,
                "first_name": driver_info.first_name,
                "last_name": driver_info.last_name,
                "email": driver_info.email,
                "selfie_url": driver_info.user.selfie_url if hasattr(driver_info, 'user') and hasattr(driver_info.user, 'selfie_url') else None
            },
            "vehicle_info": vehicle_data
        }

    def has_pending_request(self, driver_id: UUID) -> bool:
        """
        Verifica si un conductor tiene una solicitud pendiente
        """
        driver_info = self.session.query(DriverInfo).filter(
            DriverInfo.user_id == driver_id
        ).first()

        if not driver_info:
            return False

        return driver_info.pending_request_id is not None

    def accept_pending_request(self, driver_id: UUID, client_request_id: UUID) -> bool:
        """
        Acepta una solicitud pendiente para un conductor
        """
        try:
            # Verificar que el conductor existe
            driver_info = self.session.query(DriverInfo).filter(
                DriverInfo.user_id == driver_id
            ).first()

            if not driver_info:
                return False

            # Verificar que la solicitud existe y está disponible
            client_request = self.session.query(ClientRequest).filter(
                ClientRequest.id == client_request_id,
                # ✅ ACTUALIZAR: Permitir solicitudes PENDING
                ClientRequest.status.in_(
                    [StatusEnum.CREATED, StatusEnum.PENDING])
            ).first()

            if not client_request:
                return False

            # Verificar que la solicitud no esté ya asignada a otro conductor
            if client_request.id_driver_assigned is not None:
                return False

            # Verificar que la solicitud no esté ya asignada como pendiente a otro conductor
            if client_request.assigned_busy_driver_id is not None and client_request.assigned_busy_driver_id != driver_id:
                return False

            # Asignar la solicitud al conductor
            driver_info.pending_request_id = client_request_id
            driver_info.pending_request_accepted_at = datetime.now(COLOMBIA_TZ)

            # Actualizar la solicitud
            client_request.assigned_busy_driver_id = driver_id

            self.session.add(driver_info)
            self.session.add(client_request)
            self.session.commit()

            return True

        except Exception as e:
            self.session.rollback()
            print(f"Error accepting pending request: {e}")
            return False

    def complete_pending_request(self, user_id: UUID) -> bool:
        """
        Completa la solicitud pendiente de un conductor (cuando termina su viaje actual)
        Usa el precio de la oferta aceptada por el cliente, o el precio base si no hay oferta
        """
        try:
            print(f"DEBUG: Completing pending request for user {user_id}")
            driver_info = self.session.query(DriverInfo).filter(
                DriverInfo.user_id == user_id
            ).first()
            print(
                f"DEBUG: Driver pending_request_id: {driver_info.pending_request_id if driver_info else None}")
            if not driver_info or driver_info.pending_request_id is None:
                print(f"DEBUG: No pending request for user {user_id}")
                return False
            client_request = self.session.query(ClientRequest).filter(
                ClientRequest.id == driver_info.pending_request_id
            ).first()
            print(
                f"DEBUG: Found client request: {client_request.id if client_request else None}")
            if not client_request:
                print(
                    f"DEBUG: Client request {driver_info.pending_request_id} not found")
                return False

            # Buscar la oferta aceptada del conductor para esta solicitud
            from app.models.driver_trip_offer import DriverTripOffer
            accepted_offer = self.session.query(DriverTripOffer).filter(
                DriverTripOffer.id_client_request == client_request.id,
                DriverTripOffer.id_driver == user_id
            ).first()
            
            if accepted_offer:
                # Usar el precio de la oferta aceptada
                client_request.fare_assigned = accepted_offer.fare_offer
                print(
                    f"DEBUG: Using accepted offer price - fare_assigned: {accepted_offer.fare_offer}")
            else:
                # Si no hay oferta aceptada, usar el precio base del cliente
                client_request.fare_assigned = client_request.fare_offered
                print(
                    f"DEBUG: Using client's offered price - fare_assigned: {client_request.fare_assigned}")

            # ✅ ACTUALIZAR: Cambiar de PENDING a ACCEPTED cuando el conductor completa su viaje actual
            client_request.id_driver_assigned = user_id
            client_request.status = StatusEnum.ACCEPTED
            client_request.assigned_busy_driver_id = None
            client_request.estimated_pickup_time = None
            client_request.driver_current_trip_remaining_time = None
            client_request.driver_transit_time = None
            driver_info.pending_request_id = None
            driver_info.pending_request_accepted_at = None
            self.session.add(driver_info)
            self.session.add(client_request)
            self.session.commit()
            print(
                f"DEBUG: Pending request completed and cleaned for user {user_id}")
            print(
                f"DEBUG: After complete - driver_info.pending_request_id: {driver_info.pending_request_id}")
            print(
                f"DEBUG: After complete - client_request.id_driver_assigned: {client_request.id_driver_assigned}, status: {client_request.status}, fare_assigned: {client_request.fare_assigned}")
            return True
        except Exception as e:
            self.session.rollback()
            print(f"Error completing pending request: {e}")
            return False

    def cancel_pending_request(self, user_id: UUID) -> bool:
        """
        Cancela la solicitud pendiente de un conductor
        """
        try:
            print(f"DEBUG: Canceling pending request for user {user_id}")
            driver_info = self.session.query(DriverInfo).filter(
                DriverInfo.user_id == user_id
            ).first()
            print(
                f"DEBUG: Driver pending_request_id before cancel: {driver_info.pending_request_id if driver_info else None}")
            if not driver_info or driver_info.pending_request_id is None:
                print(
                    f"DEBUG: No pending request to cancel for user {user_id}")
                return False
            client_request = self.session.query(ClientRequest).filter(
                ClientRequest.id == driver_info.pending_request_id
            ).first()
            print(
                f"DEBUG: Client request before cancel: {client_request.id if client_request else None}")
            if not client_request:
                print(
                    f"DEBUG: No client request found to cancel for user {user_id}")
                return False
            client_request.assigned_busy_driver_id = None
            client_request.estimated_pickup_time = None
            client_request.driver_current_trip_remaining_time = None
            client_request.driver_transit_time = None
            driver_info.pending_request_id = None
            driver_info.pending_request_accepted_at = None
            self.session.add(driver_info)
            self.session.add(client_request)
            self.session.commit()
            print(f"DEBUG: Pending request canceled for user {user_id}")
            return True
        except Exception as e:
            self.session.rollback()
            print(f"Error canceling pending request: {e}")
            return False

    def get_driver_status(self, driver_id: UUID) -> Dict:
        """
        Obtiene el estado completo de un conductor
        """
        print(f"DEBUG: Getting status for driver {driver_id}")
        driver_info = self.session.query(DriverInfo).filter(
            DriverInfo.user_id == driver_id
        ).first()
        print(f"DEBUG: Driver info: {driver_info}")
        if not driver_info:
            print(f"DEBUG: Driver not found: {driver_id}")
            return {"status": "not_found"}
        active_request = self.session.query(ClientRequest).filter(
            ClientRequest.id_driver_assigned == driver_id,
            ClientRequest.status.in_([
                StatusEnum.ON_THE_WAY, StatusEnum.ARRIVED, StatusEnum.TRAVELLING])
        ).first()
        print(
            f"DEBUG: Active request: {active_request.id if active_request else None}")
        pending_request = None
        if driver_info.pending_request_id:
            pending_request = self.session.query(ClientRequest).filter(
                ClientRequest.id == driver_info.pending_request_id
            ).first()
        print(
            f"DEBUG: Pending request: {pending_request.id if pending_request else None}")
        status = "available"
        if active_request:
            if pending_request:
                status = "busy_with_pending"
            else:
                status = "busy_available"
        elif pending_request:
            status = "pending_only"
        print(f"DEBUG: Status for driver {driver_id}: {status}")
        return {
            "status": status,
            "active_request": active_request.id if active_request else None,
            "pending_request": pending_request.id if pending_request else None,
            "pending_request_accepted_at": driver_info.pending_request_accepted_at
        }

    def get_driver_pending_request(self, user_id: UUID) -> Optional[Dict]:
        """
        Obtiene los detalles de la solicitud pendiente de un conductor
        """
        print(
            f"DEBUG: get_driver_pending_request called for user {user_id}")
        driver_info = self.session.query(DriverInfo).filter(
            DriverInfo.user_id == user_id
        ).first()
        print(
            f"DEBUG: Driver {user_id} - pending_request_id: {driver_info.pending_request_id if driver_info else None}")
        if not driver_info or driver_info.pending_request_id is None:
            print(f"DEBUG: No pending request for user {user_id}")
            return None
        client_request = self.session.query(ClientRequest).filter(
            ClientRequest.id == driver_info.pending_request_id
        ).first()
        print(
            f"DEBUG: Found pending request: {client_request.id if client_request else None}")
        if not client_request:
            print(
                f"DEBUG: Pending request {driver_info.pending_request_id} not found")
            return None
        print(f"DEBUG: Returning pending request data for user {user_id}")
        return {
            "request_id": str(client_request.id),
            "client_id": str(client_request.id_client),
            "pickup_description": client_request.pickup_description,
            "destination_description": client_request.destination_description,
            "fare_offered": client_request.fare_offered,
            "estimated_pickup_time": client_request.estimated_pickup_time,
            "driver_current_trip_remaining_time": client_request.driver_current_trip_remaining_time,
            "driver_transit_time": client_request.driver_transit_time,
            "accepted_at": driver_info.pending_request_accepted_at
        }
