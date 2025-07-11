from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Path, Request, Security
from sqlmodel import Session
from typing import List, Optional
from fastapi.responses import JSONResponse
import json
from sqlalchemy import select
import traceback
import os
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from uuid import UUID

from app.models.driver import DriverCreate, DriverDocumentsInput, DriverFullCreate, DriverFullRead
from app.core.db import get_session
from app.models.user import UserRead
from app.services.driver_service import DriverService
from app.models.driver_full_read import DriverFullRead
from app.models.driver_response import DriverFullResponse, UserResponse, DriverInfoResponse, VehicleInfoResponse, DriverDocumentsResponse
from app.utils.uploads import uploader
from app.models.driver_info import DriverInfo
from app.models.vehicle_info import VehicleInfo
from app.models.driver_documents import DriverDocuments
from app.models.user import User
from app.models.document_type import DocumentType
from app.core.config import settings
from app.core.dependencies.auth import get_current_user
from app.services.user_service import UserService

router = APIRouter(prefix="/drivers", tags=["Drivers"])

bearer_scheme = HTTPBearer()


@router.post("/", response_model=DriverFullResponse, status_code=status.HTTP_201_CREATED, description="""
Crea un nuevo conductor con sus documentos.

**Parámetros:**
- `user`: Cadena JSON con los datos del usuario.
- `driver_info`: Cadena JSON con los datos del conductor.
- `vehicle_info`: Cadena JSON con los datos del vehículo.
- `driver_documents`: Cadena JSON con las fechas de vencimiento de los documentos.
- `selfie`: Archivo de la selfie del conductor (OBLIGATORIO).
- `property_card_front`: Archivo del frente de la tarjeta de propiedad (opcional).
- `property_card_back`: Archivo del reverso de la tarjeta de propiedad (opcional).
- `license_front`: Archivo del frente de la licencia de conducir (opcional).
- `license_back`: Archivo del reverso de la licencia de conducir (opcional).
- `soat`: Archivo del SOAT (opcional).
- `vehicle_technical_inspection`: Archivo de la revisión técnico mecánica (opcional).

**Respuesta:**
Devuelve la información registrada del conductor, usuario, vehículo y documentos.
""")
async def create_driver(
    user: str = Form(...),
    driver_info: str = Form(...),
    vehicle_info: str = Form(...),
    driver_documents: str = Form(...),
    selfie: UploadFile = File(...),
    property_card_front: Optional[UploadFile] = File(None),
    property_card_back: Optional[UploadFile] = File(None),
    license_front: Optional[UploadFile] = File(None),
    license_back: Optional[UploadFile] = File(None),
    soat: Optional[UploadFile] = File(None),
    vehicle_technical_inspection: Optional[UploadFile] = File(None),
    session: Session = Depends(get_session)
):
    """
    Crea un nuevo conductor con sus documentos.

    Los datos se pueden enviar de dos formas:
    1. Como JSON en los campos user, driver_info, vehicle_info y driver_documents
    2. Como archivos individuales para cada documento

    Args:
        user: JSON string con los datos del usuario
        driver_info: JSON string con los datos del conductor
        vehicle_info: JSON string con los datos del vehículo
        driver_documents: JSON string con las fechas de vencimiento de los documentos
        selfie: Foto de selfie del conductor
        property_card_front: Frente de la tarjeta de propiedad
        property_card_back: Reverso de la tarjeta de propiedad
        license_front: Frente de la licencia de conducir
        license_back: Reverso de la licencia de conducir
        soat: SOAT
        vehicle_technical_inspection: Revisión técnico mecánica
    """
    try:
        user_data = json.loads(user)
        driver_info_data = json.loads(driver_info)
        vehicle_info_data = json.loads(vehicle_info)
        driver_documents_data = json.loads(driver_documents)

        driver_docs = DriverDocumentsInput(
            property_card_front=property_card_front,
            property_card_back=property_card_back,
            license_front=license_front,
            license_back=license_back,
            license_expiration_date=driver_documents_data.get(
                "license_expiration_date"),
            soat=soat,
            soat_expiration_date=driver_documents_data.get(
                "soat_expiration_date"),
            vehicle_technical_inspection=vehicle_technical_inspection,
            vehicle_technical_inspection_expiration_date=driver_documents_data.get(
                "vehicle_technical_inspection_expiration_date"),
            property_card_front_url=driver_documents_data.get(
                "property_card_front_url"),
            property_card_back_url=driver_documents_data.get(
                "property_card_back_url"),
            license_front_url=driver_documents_data.get("license_front_url"),
            license_back_url=driver_documents_data.get("license_back_url"),
            soat_url=driver_documents_data.get("soat_url"),
            vehicle_technical_inspection_url=driver_documents_data.get(
                "vehicle_technical_inspection_url")
        )

        driver_data = DriverFullCreate(
            user=user_data,
            driver_info=driver_info_data,
            vehicle_info=vehicle_info_data,
            driver_documents=driver_docs,
            selfie=selfie
        )

        service = DriverService(session)
        result = await service.create_driver(
            user_data=driver_data.user,
            driver_info_data=driver_data.driver_info,
            vehicle_info_data=driver_data.vehicle_info,
            driver_documents_data=driver_data.driver_documents,
            selfie=selfie
        )

        return DriverFullResponse(
            user=UserResponse(
                id=result.user.id,
                full_name=result.user.full_name,
                country_code=result.user.country_code,
                phone_number=result.user.phone_number,
                selfie_url=result.user.selfie_url if hasattr(
                    result.user, 'selfie_url') else None
            ),
            driver_info=DriverInfoResponse(
                first_name=result.driver_info.first_name,
                last_name=result.driver_info.last_name,
                birth_date=str(result.driver_info.birth_date),
                email=result.driver_info.email,
                selfie_url=result.user.selfie_url if hasattr(
                    result.user, 'selfie_url') else None
            ),
            vehicle_info=VehicleInfoResponse(
                brand=result.vehicle_info.brand,
                model=result.vehicle_info.model,
                model_year=result.vehicle_info.model_year,
                color=result.vehicle_info.color,
                plate=result.vehicle_info.plate,
                vehicle_type_id=result.vehicle_info.vehicle_type_id
            ),
            driver_documents=result.driver_documents
        )

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al decodificar JSON: {str(e)}"
        )
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear el conductor: {str(e)}"
        )


@router.patch("/me", response_model=DriverFullResponse, status_code=status.HTTP_200_OK, description="""
Actualiza la información de un conductor y sus documentos, (toma el user_id desde el token).

**Parámetros:**
- `first_name`: Nombre del conductor (opcional).
- `last_name`: Apellido del conductor (opcional).
- `birth_date`: Fecha de nacimiento del conductor (opcional).
- `email`: Correo electrónico del conductor (opcional).
- `selfie`: Archivo de la selfie del conductor (opcional).
- `brand`: Marca del vehículo (opcional).
- `model`: Modelo del vehículo (opcional).
- `model_year`: Año del modelo del vehículo (opcional).
- `color`: Color del vehículo (opcional).
- `plate`: Placa del vehículo (opcional).
- `vehicle_type_id`: ID del tipo de vehículo (opcional).
- `property_card_front`: Archivo del frente de la tarjeta de propiedad (opcional).
- `property_card_back`: Archivo del reverso de la tarjeta de propiedad (opcional).
- `license_front`: Archivo del frente de la licencia de conducir (opcional).
- `license_back`: Archivo del reverso de la licencia de conducir (opcional).
- `soat`: Archivo del SOAT (opcional).
- `vehicle_technical_inspection`: Archivo de la revisión técnico mecánica (opcional).
- `license_expiration_date`: Fecha de vencimiento de la licencia (opcional).
- `soat_expiration_date`: Fecha de vencimiento del SOAT (opcional).
- `vehicle_technical_inspection_expiration_date`: Fecha de vencimiento de la revisión técnico mecánica (opcional).

**Respuesta:**
Devuelve la información actualizada del conductor, usuario, vehículo y documentos.
""")
async def update_driver(
    request: Request,
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    birth_date: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    brand: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    model_year: Optional[int] = Form(None),
    color: Optional[str] = Form(None),
    plate: Optional[str] = Form(None),
    vehicle_type_id: Optional[int] = Form(None),
    property_card_front: Optional[UploadFile] = File(None),
    property_card_back: Optional[UploadFile] = File(None),
    license_front: Optional[UploadFile] = File(None),
    license_back: Optional[UploadFile] = File(None),
    soat: Optional[UploadFile] = File(None),
    vehicle_technical_inspection: Optional[UploadFile] = File(None),
    license_expiration_date: Optional[str] = Form(None),
    soat_expiration_date: Optional[str] = Form(None),
    vehicle_technical_inspection_expiration_date: Optional[str] = Form(None),
    selfie: Optional[UploadFile] = File(None),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user)
):
    # Obtener el user_id desde el token
    user_id = request.state.user_id
    # Buscar el driver_info correspondiente a este usuario
    driver_info = session.exec(select(DriverInfo).where(
        DriverInfo.user_id == user_id)).scalars().first()
    if not driver_info:
        raise HTTPException(
            status_code=404, detail="No se encontró información de conductor para este usuario.")
    driver_id = driver_info.id

    # Buscar la información del vehículo asociada al conductor
    vehicle_info = session.exec(
        select(VehicleInfo).where(VehicleInfo.driver_info_id == driver_info.id)
    ).scalars().first()
    if not vehicle_info:
        raise HTTPException(
            status_code=404, detail="VehicleInfo no encontrado para este driver")

    # Actualizar datos personales del conductor
    if first_name is not None:
        driver_info.first_name = first_name
    if last_name is not None:
        driver_info.last_name = last_name
    if birth_date is not None:
        driver_info.birth_date = birth_date
    if email is not None:
        driver_info.email = email

    # Actualizar datos del vehículo
    if brand is not None:
        vehicle_info.brand = brand
    if model is not None:
        vehicle_info.model = model
    if model_year is not None:
        vehicle_info.model_year = model_year
    if color is not None:
        vehicle_info.color = color
    if plate is not None:
        vehicle_info.plate = plate
    if vehicle_type_id is not None:
        vehicle_info.vehicle_type_id = vehicle_type_id

    # Obtener los IDs de tipo de documento dinámicamente
    property_card_type = session.exec(
        select(DocumentType).where(DocumentType.name == "property_card")
    ).scalars().first()
    property_card_type_id = property_card_type.id if property_card_type else None
    license_type = session.exec(
        select(DocumentType).where(DocumentType.name == "license")
    ).scalars().first()
    license_type_id = license_type.id if license_type else None
    soat_type = session.exec(
        select(DocumentType).where(DocumentType.name == "soat")
    ).scalars().first()
    soat_type_id = soat_type.id if soat_type else None
    vehicle_tech_type = session.exec(
        select(DocumentType).where(
            DocumentType.name == "technical_inspections")
    ).scalars().first()
    vehicle_tech_type_id = vehicle_tech_type.id if vehicle_tech_type else None

    # Actualizar documentos del conductor
    doc_types = [
        (property_card_front, "property_card", "front", property_card_type_id),
        (property_card_back, "property_card", "back", property_card_type_id),
        (license_front, "license", "front", license_type_id),
        (license_back, "license", "back", license_type_id),
        (soat, "soat", None, soat_type_id),
        (vehicle_technical_inspection,
         "technical_inspections", None, vehicle_tech_type_id)
    ]
    for file, doc_type, side, doc_type_id in doc_types:
        if file is not None and doc_type_id is not None:
            # Guardar el archivo y actualizar la URL en el documento correspondiente
            url = await uploader.save_driver_document(
                file=file,
                driver_id=driver_info.id,
                document_type=doc_type,
                subfolder=side
            )
            doc = session.exec(
                select(DriverDocuments).where(
                    DriverDocuments.driver_info_id == driver_info.id,
                    DriverDocuments.document_type_id == doc_type_id
                )
            ).scalars().first()
            if doc:
                if side == "front":
                    doc.document_front_url = url
                elif side == "back":
                    doc.document_back_url = url
                else:
                    doc.document_front_url = url
            else:
                session.add(DriverDocuments(
                    driver_info_id=driver_info.id,
                    vehicle_info_id=vehicle_info.id,
                    document_type_id=doc_type_id,
                    document_front_url=url if side != "back" else None,
                    document_back_url=url if side == "back" else None
                ))

    # Consultar documentos actualizados para la respuesta
    property_card_doc = session.exec(
        select(DriverDocuments).where(
            DriverDocuments.driver_info_id == driver_info.id,
            DriverDocuments.document_type_id == property_card_type_id
        )
    ).scalars().first()
    license_doc = session.exec(
        select(DriverDocuments).where(
            DriverDocuments.driver_info_id == driver_info.id,
            DriverDocuments.document_type_id == license_type_id
        )
    ).scalars().first()
    soat_doc = session.exec(
        select(DriverDocuments).where(
            DriverDocuments.driver_info_id == driver_info.id,
            DriverDocuments.document_type_id == soat_type_id
        )
    ).scalars().first()
    vehicle_tech_doc = session.exec(
        select(DriverDocuments).where(
            DriverDocuments.driver_info_id == driver_info.id,
            DriverDocuments.document_type_id == vehicle_tech_type_id
        )
    ).scalars().first()

    # Actualizar fechas de vencimiento de los documentos
    if license_expiration_date is not None:
        doc = session.exec(
            select(DriverDocuments).where(
                DriverDocuments.driver_info_id == driver_info.id,
                DriverDocuments.document_type_id == 2
            )
        ).scalars().first()
        if doc:
            doc.expiration_date = license_expiration_date
    if soat_expiration_date is not None:
        doc = session.exec(
            select(DriverDocuments).where(
                DriverDocuments.driver_info_id == driver_info.id,
                DriverDocuments.document_type_id == 3
            )
        ).scalars().first()
        if doc:
            doc.expiration_date = soat_expiration_date
    if vehicle_technical_inspection_expiration_date is not None:
        doc = session.exec(
            select(DriverDocuments).where(
                DriverDocuments.driver_info_id == driver_info.id,
                DriverDocuments.document_type_id == 4
            )
        ).scalars().first()
        if doc:
            doc.expiration_date = vehicle_technical_inspection_expiration_date

    # Actualizar selfie del usuario si se recibe un archivo
    if selfie is not None:
        try:
            print(
                f"[DEBUG PATCH] Actualizando selfie para user_id={user_id}, archivo={selfie.filename}")
            UserService(session).update_selfie(user_id, selfie)
            user = session.exec(select(User).where(
                User.id == user_id)).scalars().first()
            print(
                f"[DEBUG PATCH] selfie_url actualizado: {user.selfie_url if user else 'Usuario no encontrado'}")
        except Exception as e:
            print(f"[ERROR PATCH] Error actualizando selfie: {e}")
            traceback.print_exc()

    # Guardar todos los cambios en la base de datos
    session.commit()

    # Consultar el usuario actualizado para la respuesta
    user = session.exec(select(User).where(
        User.id == user_id)).scalars().first()

    return {
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "country_code": user.country_code,
            "phone_number": user.phone_number,
            "selfie_url": user.selfie_url,
        },
        "driver_info": {
            "first_name": driver_info.first_name,
            "last_name": driver_info.last_name,
            "birth_date": str(driver_info.birth_date),
            "email": driver_info.email,
        },
        "vehicle_info": {
            "brand": vehicle_info.brand,
            "model": vehicle_info.model,
            "model_year": vehicle_info.model_year,
            "color": vehicle_info.color,
            "plate": vehicle_info.plate,
            "vehicle_type_id": vehicle_info.vehicle_type_id,
        },
        "driver_documents": {
            "property_card_front_url": property_card_doc.document_front_url if property_card_doc else None,
            "property_card_back_url": property_card_doc.document_back_url if property_card_doc else None,
            "license_front_url": license_doc.document_front_url if license_doc else None,
            "license_back_url": license_doc.document_back_url if license_doc else None,
            "license_expiration_date": str(license_doc.expiration_date) if license_doc and license_doc.expiration_date else None,
            "soat_url": soat_doc.document_front_url if soat_doc else None,
            "soat_expiration_date": str(soat_doc.expiration_date) if soat_doc and soat_doc.expiration_date else None,
            "vehicle_technical_inspection_url": vehicle_tech_doc.document_front_url if vehicle_tech_doc else None,
            "vehicle_technical_inspection_expiration_date": str(vehicle_tech_doc.expiration_date) if vehicle_tech_doc and vehicle_tech_doc.expiration_date else None,
        }
    }


@router.get("/me", response_model=DriverFullResponse, description="""
Devuelve la información personal, de usuario y del vehículo del conductor autenticado (toma el user_id desde el token).

**Respuesta:**
Incluye la información personal, de usuario, del vehículo y documentos del conductor.
""")
def get_driver_me(
    request: Request,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user)
):
    # Obtener el user_id desde el token
    user_id = request.state.user_id
    # Buscar el driver_info correspondiente a este usuario
    driver_info = session.query(DriverInfo).filter(
        DriverInfo.user_id == user_id).first()
    if not driver_info:
        raise HTTPException(
            status_code=404, detail="No se encontró información de conductor para este usuario.")
    driver_id = driver_info.id
    # Usar el servicio existente para obtener el detalle completo
    service = DriverService(session)
    return service.get_driver_detail_service(session, driver_id)


@router.post("/pending-request/accept", status_code=status.HTTP_200_OK, description="""
Acepta una solicitud pendiente del conductor.

**Parámetros:**
- `client_request_id`: ID de la solicitud del cliente a aceptar (UUID).

**Respuesta:**
Devuelve un mensaje de confirmación si la solicitud se aceptó correctamente.
""")
async def accept_pending_request(
    client_request_id: UUID,
    request: Request,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """
    Acepta una solicitud pendiente del conductor.

    Args:
        client_request_id: ID de la solicitud del cliente a aceptar (UUID)
        request: Request object para obtener el user_id del token
        session: Sesión de base de datos
        current_user: Usuario autenticado
    """
    import traceback
    try:
        print(f"🔍 DEBUG: accept_pending_request endpoint llamado")
        print(f"   - client_request_id: {client_request_id}")

        # Obtener el user_id desde el token
        user_id = request.state.user_id
        print(f"   - user_id del token: {user_id}")

        # Usar el servicio para aceptar la solicitud pendiente
        service = DriverService(session)
        print(
            f"   - Llamando service.accept_pending_request({user_id}, {client_request_id})")
        success = service.accept_pending_request(user_id, client_request_id)
        print(f"   - Resultado del servicio: {success}")

        if success:
            print(f"✅ Solicitud pendiente aceptada correctamente")
            return {"message": "Solicitud pendiente aceptada correctamente"}
        else:
            print(f"❌ No se pudo aceptar la solicitud pendiente")
            raise HTTPException(
                status_code=400, detail="No se pudo aceptar la solicitud pendiente")

    except HTTPException:
        print(f"⚠️ HTTPException capturada y re-lanzada")
        raise
    except Exception as e:
        print(f"❌ Error aceptando solicitud pendiente: {e}")
        print(f"   - Traceback completo:")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )


@router.post("/pending-request/complete", status_code=status.HTTP_200_OK, description="""
Completa una solicitud pendiente del conductor (marca como completada).
Usa el precio de la oferta aceptada por el cliente, o el precio base si no hay oferta.

**Respuesta:**
Devuelve un mensaje de confirmación si la solicitud se completó correctamente.
""")
async def complete_pending_request(
    request: Request,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """
    Completa una solicitud pendiente del conductor.
    Usa el precio de la oferta aceptada por el cliente, o el precio base si no hay oferta.

    Args:
        request: Request object para obtener el user_id del token
        session: Sesión de base de datos
        current_user: Usuario autenticado
    """
    try:
        # Obtener el user_id desde el token
        user_id = request.state.user_id

        # Usar el servicio para completar la solicitud pendiente
        service = DriverService(session)
        success = service.complete_pending_request(user_id)

        if success:
            return {"message": "Solicitud pendiente completada correctamente"}
        else:
            raise HTTPException(
                status_code=400, detail="No se pudo completar la solicitud pendiente. Verifique que el precio ofrecido no sea menor al precio base del cliente.")

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error completando solicitud pendiente: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )


@router.post("/pending-request/cancel", status_code=status.HTTP_200_OK, description="""
Cancela una solicitud pendiente del conductor.

**Respuesta:**
Devuelve un mensaje de confirmación si la solicitud se canceló correctamente.
""")
async def cancel_pending_request(
    request: Request,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """
    Cancela una solicitud pendiente del conductor.

    Args:
        request: Request object para obtener el user_id del token
        session: Sesión de base de datos
        current_user: Usuario autenticado
    """
    try:
        # Obtener el user_id desde el token
        user_id = request.state.user_id

        # Usar el servicio para cancelar la solicitud pendiente
        service = DriverService(session)
        success = service.cancel_pending_request(user_id)

        if success:
            return {"message": "Solicitud pendiente cancelada correctamente"}
        else:
            raise HTTPException(
                status_code=400, detail="No se pudo cancelar la solicitud pendiente")

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error cancelando solicitud pendiente: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )


@router.get("/pending-request", description="""
Obtiene la información de la solicitud pendiente del conductor.

**Respuesta:**
Devuelve la información de la solicitud pendiente si existe, o null si no hay solicitud pendiente.
""")
async def get_pending_request(
    request: Request,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """
    Obtiene la información de la solicitud pendiente del conductor.

    Args:
        request: Request object para obtener el user_id del token
        session: Sesión de base de datos
        current_user: Usuario autenticado
    """
    try:
        # Obtener el user_id desde el token
        user_id = request.state.user_id

        # Usar el servicio para obtener la solicitud pendiente
        service = DriverService(session)
        pending_request = service.get_driver_pending_request(user_id)

        return {"pending_request": pending_request}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error obteniendo solicitud pendiente: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )


@router.post("/pending-request/offer", status_code=status.HTTP_200_OK, description="""
Hace una oferta de precio para una solicitud pendiente del conductor.
Permite al conductor ofrecer un precio diferente al precio base del cliente.

**Parámetros:**
- `fare_offer`: Precio ofrecido por el conductor (debe ser mayor o igual al precio base del cliente).

**Respuesta:**
Devuelve un mensaje de confirmación si la oferta se creó correctamente.
""")
async def make_pending_request_offer(
    request: Request,
    fare_offer: float,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """
    Hace una oferta de precio para una solicitud pendiente del conductor.

    Args:
        request: Request object para obtener el user_id del token
        fare_offer: Precio ofrecido por el conductor
        session: Sesión de base de datos
        current_user: Usuario autenticado
    """
    try:
        # Obtener el user_id desde el token
        user_id = request.state.user_id

        # Obtener la información del conductor
        driver_info = session.query(DriverInfo).filter(
            DriverInfo.user_id == user_id
        ).first()

        if not driver_info or driver_info.pending_request_id is None:
            raise HTTPException(
                status_code=400,
                detail="No tienes una solicitud pendiente para hacer oferta"
            )

        # Obtener la solicitud pendiente
        from app.models.client_request import ClientRequest
        client_request = session.query(ClientRequest).filter(
            ClientRequest.id == driver_info.pending_request_id
        ).first()

        if not client_request:
            raise HTTPException(
                status_code=404,
                detail="Solicitud pendiente no encontrada"
            )

        # Validar que el precio ofrecido no sea menor al precio base del cliente
        if fare_offer < client_request.fare_offered:
            raise HTTPException(
                status_code=400,
                detail=f"El precio ofrecido ({fare_offer}) no puede ser menor al precio base del cliente ({client_request.fare_offered})"
            )

        # Crear la oferta usando el servicio de ofertas
        from app.services.driver_trip_offer_service import DriverTripOfferService
        offer_service = DriverTripOfferService(session)

        offer_data = {
            "id_driver": user_id,
            "id_client_request": client_request.id,
            "fare_offer": fare_offer,
            "time": 0,  # Se calculará automáticamente
            "distance": 0  # Se calculará automáticamente
        }

        offer = offer_service.create_offer(offer_data)

        return {"message": "Oferta creada exitosamente", "offer_id": str(offer.id), "fare_offer": fare_offer, "client_request_id": str(client_request.id)}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creando oferta de solicitud pendiente: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )


@router.post("/pending-request/client-accept", status_code=status.HTTP_200_OK, description="""
El cliente acepta la oferta del conductor para una solicitud pendiente.
Permite al cliente confirmar que acepta el precio ofrecido por el conductor.

**Parámetros:**
- `client_request_id`: ID de la solicitud del cliente a aceptar (UUID).

**Respuesta:**
Devuelve un mensaje de confirmación si la oferta se aceptó correctamente.
""")
async def client_accept_pending_request_offer(
    client_request_id: UUID,
    request: Request,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """
    El cliente acepta la oferta del conductor para una solicitud pendiente.

    Args:
        client_request_id: ID de la solicitud del cliente a aceptar (UUID)
        request: Request object para obtener el user_id del token
        session: Sesión de base de datos
        current_user: Usuario autenticado
    """
    try:
        # Obtener el user_id desde el token
        user_id = request.state.user_id

        # Verificar que el usuario es un cliente
        from app.models.user_has_roles import UserHasRole, RoleStatus
        user_role = session.query(UserHasRole).filter(
            UserHasRole.id_user == user_id,
            UserHasRole.id_rol == "CLIENT"
        ).first()

        if not user_role or user_role.status != RoleStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail="El usuario no tiene el rol de cliente aprobado"
            )

        # Verificar que la solicitud existe y pertenece al cliente
        from app.models.client_request import ClientRequest
        client_request = session.query(ClientRequest).filter(
            ClientRequest.id == client_request_id,
            ClientRequest.id_client == user_id
        ).first()

        if not client_request:
            raise HTTPException(
                status_code=404,
                detail="Solicitud no encontrada o no pertenece al cliente"
            )

        # Verificar que la solicitud está en estado PENDING
        if client_request.status != "PENDING":
            raise HTTPException(
                status_code=400,
                detail="La solicitud debe estar en estado PENDING para aceptar ofertas"
            )

        # Verificar que hay una oferta del conductor
        from app.models.driver_trip_offer import DriverTripOffer
        offer = session.query(DriverTripOffer).filter(
            DriverTripOffer.id_client_request == client_request_id
        ).first()

        if not offer:
            raise HTTPException(
                status_code=400,
                detail="No hay ofertas del conductor para aceptar"
            )

        # Marcar la oferta como aceptada (podemos agregar un campo accepted en el modelo)
        # Por ahora, simplemente confirmamos que el cliente acepta
        return {
            "message": "Oferta del conductor aceptada correctamente",
            "fare_offer": offer.fare_offer,
            "driver_id": str(offer.id_driver)
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error aceptando oferta del conductor: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )
