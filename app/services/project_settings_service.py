from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.project_settings import ProjectSettings, ProjectSettingsUpdate,ProjectSettingsCreate
from datetime import datetime 


def update_project_settings_service(session: Session, settings_data: ProjectSettingsUpdate):
    """
    Actualiza la configuración del proyecto. 
    Si no existe ningún registro, crea uno nuevo.
    """
    # Buscar el primer registro (asumiendo que solo hay uno)
    settings = session.query(ProjectSettings).first()
    
    if not settings:
        # Si no existe, crear uno nuevo con los valores proporcionados
        # Necesitarás valores por defecto para los campos requeridos
        raise HTTPException(
            status_code=404, 
            detail="No se encontró configuración del proyecto. Crea una configuración primero."
        )
    
    # Actualizar solo los campos que no son None
    update_data = settings_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        if hasattr(settings, field):
            setattr(settings, field, value)
    
    # Actualizar timestamp
    settings.updated_at = datetime.utcnow()
    
    try:
        session.add(settings)
        session.commit()
        session.refresh(settings)
        return settings
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar configuración: {str(e)}")


def get_project_settings_service(session: Session):
    """
    Obtiene la configuración actual del proyecto.
    """
    settings = session.query(ProjectSettings).first()
    
    if not settings:
        raise HTTPException(
            status_code=404, 
            detail="No se encontró configuración del proyecto"
        )
    
    return settings


def create_project_settings_service(session: Session, settings_data: ProjectSettingsCreate):
    """
    Crea la configuración inicial del proyecto.
    """
    # Verificar que no exista ya una configuración
    existing = session.query(ProjectSettings).first()
    if existing:
        raise HTTPException(
            status_code=400, 
            detail="Ya existe una configuración del proyecto. Usa el endpoint de actualización."
        )
    
    settings = ProjectSettings(**settings_data.model_dump())
    
    try:
        session.add(settings)
        session.commit()
        session.refresh(settings)
        return settings
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear configuración: {str(e)}")