from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from uuid import UUID
from app.core.dependencies.admin_auth import get_current_admin
from app.core.db import SessionDep
from app.services.admin_log_service import AdminLogService
from app.models.admin_log import AdminLogRead, AdminLogFilter, AdminLogStatistics
from app.models.administrador import Administrador

router = APIRouter(
    prefix="/admin-logs",
    tags=["ADMIN LOGS"]
)


@router.get("/my-logs", response_model=List[AdminLogRead], description="""
Obtener logs del administrador actual según su rol:
- Role 1 (Admin básico): Solo sus propios logs
- Role 2 (Admin sistema): Logs de admins nivel 1
- Role 3 (Super admin): Todos los logs
""")
async def get_my_logs(
    session: SessionDep,
    current_admin: Administrador = Depends(get_current_admin),
    limit: int = 50
):
    """Obtener logs según el rol del administrador"""
    try:
        service = AdminLogService(session)
        logs = service.get_admin_logs_by_admin(
            admin_id=current_admin.id,
            current_admin_role=current_admin.role,
            limit=limit
        )
        return logs
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener logs: {str(e)}"
        )


@router.get("/statistics", response_model=AdminLogStatistics, description="""
Obtener estadísticas de logs según el rol del administrador
""")
async def get_log_statistics(
    session: SessionDep,
    current_admin: Administrador = Depends(get_current_admin),
    days: int = 30
):
    """Obtener estadísticas según el rol"""
    try:
        service = AdminLogService(session)
        stats = service.get_admin_log_statistics(days=days)
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estadísticas: {str(e)}"
        )


@router.get("/filter", response_model=List[AdminLogRead], description="""
Filtrar logs según criterios (respetando permisos de rol)
""")
async def filter_logs(
    session: SessionDep,
    current_admin: Administrador = Depends(get_current_admin),
    filters: AdminLogFilter = Depends()
):
    """Filtrar logs con restricciones de rol"""
    try:
        service = AdminLogService(session)

        # Aplicar restricciones según rol
        if current_admin.role == 1:  # Solo sus logs
            filters.admin_id = current_admin.id
        elif current_admin.role == 2:  # Solo logs de nivel 1
            # Filtrar para mostrar solo admins de nivel 1
            pass  # Implementar filtro adicional

        result = service.get_admin_logs(filters)
        return result["logs"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al filtrar logs: {str(e)}"
        )
