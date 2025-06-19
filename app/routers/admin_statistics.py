from fastapi import APIRouter, Depends, Query, status
from typing import Dict, Any, Optional
from datetime import date
from uuid import UUID

from app.core.dependencies.admin_auth import get_current_admin
from app.core.db import SessionDep
from app.services.statistics_service import StatisticsService

router = APIRouter(
    prefix="/admin/statistics",
    tags=["ADMIN - Statistics"],
    dependencies=[Depends(get_current_admin)]
)


@router.get("/summary", response_model=Dict[str, Any])
def get_admin_statistics_summary(
    session: SessionDep,
    start_date: Optional[date] = Query(
        None, description="Fecha de inicio para el rango de estadísticas (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(
        None, description="Fecha de fin para el rango de estadísticas (YYYY-MM-DD)"),
    service_type_id: Optional[int] = Query(
        None, description="ID del tipo de servicio para filtrar (ej. 1 para Carro, 2 para Motocicleta)"),
    driver_id: Optional[UUID] = Query(
        None, description="ID del conductor para filtrar estadísticas por conductor"),
):
    """
    Obtiene un resumen completo de estadísticas administrativas con métricas críticas para la toma de decisiones.

    **Parámetros:**
    - **`start_date`**: Fecha de inicio del período para las estadísticas (YYYY-MM-DD)
    - **`end_date`**: Fecha de fin del período para las estadísticas (YYYY-MM-DD)
    - **`service_type_id`**: Filtra las estadísticas por un tipo de servicio específico
    - **`driver_id`**: Filtra las estadísticas para un conductor específico

    **Respuesta incluye las siguientes secciones:**

    **1. Estadísticas de Usuarios (`user_stats`):**
    - Conductores activos, documentos aprobados, vehículos registrados
    - Clientes activos únicos en el período

    **2. Estadísticas de Servicios (`service_stats`):**
    - Servicios completados y cancelados
    - Tasa de cancelación y distribución por tipo de servicio

    **3. Métricas Financieras Críticas (`financial_metrics`):**
    - **Revenue Breakdown**: Desglose detallado de ingresos (brutos, conductores, comisiones, referidos, ahorros)
    - **Cash Flow Management**: Gestión de liquidez (dinero total, disponible, reservado, salud financiera)
    - **Withdrawal Tracking**: Seguimiento de retiros (diario, semanal, quincenal, mensual con tendencias)
    - **Liquidity Alerts**: Alertas automáticas de liquidez y recomendaciones

    **4. Análisis de Rentabilidad (`profitability_analysis`):**
    - **Rentabilidad por Tipo de Servicio**: Ingresos, costos, ganancias y márgenes por tipo
    - **Rentabilidad por Zona**: Análisis geográfico de rentabilidad
    - **Tendencias de Rentabilidad**: Comparación con períodos anteriores
    - **KPIs de Rentabilidad**: Margen neto, ROI, punto de equilibrio

    **5. Análisis por Tipo de Vehículo (`vehicle_analytics`):**
    - **Conductores por Tipo**: Distribución de conductores por tipo de vehículo
    - **Rendimiento por Tipo**: Ingresos, viajes, calificaciones por tipo de vehículo
    - **Top Performers**: Mejores conductores por tipo de vehículo
    - **Resumen Comparativo**: Análisis comparativo entre tipos de vehículo

    **6. Drivers Analytics (`drivers_analytics`):**
    - **Driver Counts**: Total, aprobados, pendientes, rechazados, suspendidos, verificados
    - **Driver Activity**: Actividad en últimos 7 y 30 días, conductores inactivos
    - **Driver Rates**: Tasas de aprobación, verificación y retención
    - **Verification Status**: Estado de verificación (completa, parcial, no verificada)
    - **Summary**: Métricas resumidas de crecimiento y retención

    **7. Estadísticas de Suspensiones (`suspension_stats`):**
    - Conductores suspendidos actualmente
    - Suspensiones levantadas en el período
    - Detalles de estado de suspensiones

    **Casos de Uso:**
    - **Gestión Financiera**: Monitoreo de liquidez y flujo de caja
    - **Análisis de Rentabilidad**: Identificación de servicios y zonas más rentables
    - **Gestión de Conductores**: Seguimiento de verificación, actividad y retención
    - **Optimización de Flota**: Análisis por tipo de vehículo
    - **Alertas Operacionales**: Detección temprana de problemas de liquidez

    **Nota:** Las métricas de liquidez son críticas para garantizar la operación continua del sistema.
    """
    service = StatisticsService(session)
    return service.get_summary_statistics(
        start_date=start_date,
        end_date=end_date,
        service_type_id=service_type_id,
        # Convertir UUID a str para el servicio
        driver_id=str(driver_id) if driver_id else None
    )
