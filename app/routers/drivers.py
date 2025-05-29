from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Path, Request, Security
from sqlmodel import Session
from typing import List, Optional
from fastapi.responses import JSONResponse
import json
from sqlalchemy import select
import traceback
import os
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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

router = APIRouter(prefix="/drivers", tags=["drivers"])

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
    session: Session = Depends(get_session),
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
):
    # Obtener el user_id desde el token
    user_id = request.state.user_id
    # Buscar el driver_info correspondiente a este usuario
    driver_info = session.exec(select(DriverInfo).where(
        DriverInfo.user_id == user_id)).first()
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

    # Guardar todos los cambios en la base de datos
    session.commit()

    # Construir y retornar la respuesta con la información actualizada
    return DriverFullResponse(
        user=UserResponse(
            id=driver_info.user.id,
            full_name=driver_info.user.full_name,
            country_code=driver_info.user.country_code,
            phone_number=driver_info.user.phone_number
        ),
        driver_info=DriverInfoResponse(
            first_name=driver_info.first_name,
            last_name=driver_info.last_name,
            birth_date=str(driver_info.birth_date),
            email=driver_info.email,
            selfie_url=driver_info.user.selfie_url if hasattr(
                driver_info, 'user') and hasattr(driver_info.user, 'selfie_url') else None
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


@router.get("/me", response_model=DriverFullResponse, description="""
Devuelve la información personal, de usuario y del vehículo del conductor autenticado (toma el user_id desde el token).

**Respuesta:**
Incluye la información personal, de usuario, del vehículo y documentos del conductor.
""")
def get_driver_me(
    request: Request,
    session: Session = Depends(get_session),
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
):
    # Obtener el user_id desde el token
    user_id = request.state.user_id
    # Buscar el driver_info correspondiente a este usuario
    driver_info = session.exec(select(DriverInfo).where(
        DriverInfo.user_id == user_id)).first()
    if not driver_info:
        raise HTTPException(
            status_code=404, detail="No se encontró información de conductor para este usuario.")
    driver_id = driver_info.id
    # Usar el servicio existente para obtener el detalle completo
    service = DriverService(session)
    return service.get_driver_detail_service(session, driver_id)
