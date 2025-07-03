from fastapi import APIRouter, Response, Depends
from app.utils.metrics import metrics
from app.core.dependencies.admin_auth import get_current_admin
from app.core.db import SessionDep
from app.services.statistics_service import StatisticsService
from datetime import date, timedelta
import time

router = APIRouter()


@router.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """
    Endpoint para métricas de Prometheus
    """
    metrics_data = metrics.get_metrics()
    return Response(content=metrics_data, media_type="text/plain")


@router.get("/health", tags=["Monitoring"])
async def health_check():
    """
    Health check simple
    """
    return {
        "status": "healthy",
        "uptime_seconds": metrics.get_metrics().split('\n')[-1].split()[-1]
    }


@router.get("/business-metrics", tags=["Monitoring"])
async def get_business_metrics():
    """
    Métricas específicas de negocio
    """
    return metrics.get_business_metrics()


@router.get("/admin-metrics-prometheus", tags=["Monitoring"])
async def get_admin_metrics_prometheus(
    session: SessionDep
):
    """
    Endpoint público que expone las estadísticas administrativas en formato Prometheus
    para que Prometheus y Grafana puedan consumirlas directamente.
    NO requiere autenticación para permitir scraping automático.
    """
    try:
        # Obtener estadísticas de los últimos 30 días por defecto
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        service = StatisticsService(session)
        stats = service.get_summary_statistics(
            start_date=start_date,
            end_date=end_date
        )

        # Convertir a formato Prometheus
        prometheus_metrics = []

        # User Stats
        user_stats = stats.get('user_stats', {})
        prometheus_metrics.extend([
            f'milla99_active_drivers {user_stats.get("active_drivers", 0)}',
            f'milla99_approved_docs {user_stats.get("approved_docs", 0)}',
            f'milla99_registered_vehicles {user_stats.get("registered_vehicles", 0)}',
            f'milla99_active_clients {user_stats.get("active_clients", 0)}'
        ])

        # Service Stats
        service_stats = stats.get('service_stats', {})
        prometheus_metrics.extend([
            f'milla99_completed_services {service_stats.get("completed_services", 0)}',
            f'milla99_cancelled_services {service_stats.get("cancelled_services", 0)}',
            f'milla99_cancellation_rate {service_stats.get("cancellation_rate", 0)}'
        ])

        # Financial Stats
        financial_stats = stats.get('financial_stats', {})
        prometheus_metrics.extend([
            f'milla99_total_income {financial_stats.get("total_income", 0)}',
            f'milla99_total_commission {financial_stats.get("total_commission", 0)}',
            f'milla99_total_withdrawals {financial_stats.get("total_withdrawals", 0)}',
            f'milla99_net_income {financial_stats.get("net_income", 0)}',
            f'milla99_average_driver_income {financial_stats.get("average_driver_income", 0)}'
        ])

        # Revenue Breakdown
        revenue_breakdown = financial_stats.get('revenue_breakdown', {})
        prometheus_metrics.extend([
            f'milla99_total_gross_revenue {revenue_breakdown.get("total_gross_revenue", 0)}',
            f'milla99_driver_net_income {revenue_breakdown.get("driver_net_income", 0)}',
            f'milla99_platform_commission {revenue_breakdown.get("platform_commission", 0)}',
            f'milla99_referral_payments {revenue_breakdown.get("referral_payments", 0)}',
            f'milla99_driver_savings {revenue_breakdown.get("driver_savings", 0)}',
            f'milla99_company_net_profit {revenue_breakdown.get("company_net_profit", 0)}'
        ])

        # Cash Flow Management
        cash_flow = financial_stats.get('cash_flow_management', {})
        prometheus_metrics.extend([
            f'milla99_total_money_in_system {cash_flow.get("total_money_in_system", 0)}',
            f'milla99_available_for_withdrawals {cash_flow.get("available_for_withdrawals", 0)}',
            f'milla99_reserved_money {cash_flow.get("reserved_money", 0)}',
            f'milla99_reserve_percentage {cash_flow.get("reserve_percentage", 0)}'
        ])

        # Drivers Analytics
        drivers_analytics = stats.get('drivers_analytics', {})
        driver_counts = drivers_analytics.get('driver_counts', {})
        prometheus_metrics.extend([
            f'milla99_total_drivers {driver_counts.get("total_drivers", 0)}',
            f'milla99_approved_drivers {driver_counts.get("approved_drivers", 0)}',
            f'milla99_pending_drivers {driver_counts.get("pending_drivers", 0)}',
            f'milla99_rejected_drivers {driver_counts.get("rejected_drivers", 0)}',
            f'milla99_suspended_drivers {driver_counts.get("suspended_drivers", 0)}',
            f'milla99_fully_verified_drivers {driver_counts.get("fully_verified_drivers", 0)}',
            f'milla99_new_drivers_this_month {driver_counts.get("new_drivers_this_month", 0)}'
        ])

        driver_activity = drivers_analytics.get('driver_activity', {})
        prometheus_metrics.extend([
            f'milla99_active_drivers_30_days {driver_activity.get("active_drivers_30_days", 0)}',
            f'milla99_active_drivers_7_days {driver_activity.get("active_drivers_7_days", 0)}',
            f'milla99_inactive_drivers {driver_activity.get("inactive_drivers", 0)}',
            f'milla99_activity_rate_30_days {driver_activity.get("activity_rate_30_days", 0)}'
        ])

        driver_rates = drivers_analytics.get('driver_rates', {})
        prometheus_metrics.extend([
            f'milla99_approval_rate {driver_rates.get("approval_rate", 0)}',
            f'milla99_verification_rate {driver_rates.get("verification_rate", 0)}',
            f'milla99_churn_rate {driver_rates.get("churn_rate", 0)}'
        ])

        # Suspension Stats
        suspension_stats = stats.get('suspended_drivers_stats', {})
        prometheus_metrics.extend([
            f'milla99_total_suspended_drivers {suspension_stats.get("total_suspended_drivers", 0)}',
            f'milla99_suspensions_lifted {suspension_stats.get("suspensions_lifted", 0)}',
            f'milla99_still_suspended {suspension_stats.get("still_suspended", 0)}'
        ])

        # Timestamp para indicar cuándo se generaron las métricas
        prometheus_metrics.append(
            f'milla99_metrics_timestamp {int(time.time())}')

        return Response(content='\n'.join(prometheus_metrics), media_type="text/plain")

    except Exception as e:
        # En caso de error, devolver métricas básicas
        return Response(
            content=f'milla99_metrics_error 1\nmilla99_metrics_error_message "{str(e)}"',
            media_type="text/plain"
        )


@router.get("/admin-metrics-prometheus-secure", tags=["Monitoring"])
async def get_admin_metrics_prometheus_secure(
    session: SessionDep,
    current_admin=Depends(get_current_admin)
):
    """
    Endpoint seguro que expone las estadísticas administrativas en formato Prometheus.
    Requiere autenticación de administrador para acceso manual.
    """
    try:
        # Obtener estadísticas de los últimos 30 días por defecto
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        service = StatisticsService(session)
        stats = service.get_summary_statistics(
            start_date=start_date,
            end_date=end_date
        )

        # Convertir a formato Prometheus
        prometheus_metrics = []

        # User Stats
        user_stats = stats.get('user_stats', {})
        prometheus_metrics.extend([
            f'milla99_active_drivers {user_stats.get("active_drivers", 0)}',
            f'milla99_approved_docs {user_stats.get("approved_docs", 0)}',
            f'milla99_registered_vehicles {user_stats.get("registered_vehicles", 0)}',
            f'milla99_active_clients {user_stats.get("active_clients", 0)}'
        ])

        # Service Stats
        service_stats = stats.get('service_stats', {})
        prometheus_metrics.extend([
            f'milla99_completed_services {service_stats.get("completed_services", 0)}',
            f'milla99_cancelled_services {service_stats.get("cancelled_services", 0)}',
            f'milla99_cancellation_rate {service_stats.get("cancellation_rate", 0)}'
        ])

        # Financial Stats
        financial_stats = stats.get('financial_stats', {})
        prometheus_metrics.extend([
            f'milla99_total_income {financial_stats.get("total_income", 0)}',
            f'milla99_total_commission {financial_stats.get("total_commission", 0)}',
            f'milla99_total_withdrawals {financial_stats.get("total_withdrawals", 0)}',
            f'milla99_net_income {financial_stats.get("net_income", 0)}',
            f'milla99_average_driver_income {financial_stats.get("average_driver_income", 0)}'
        ])

        # Revenue Breakdown
        revenue_breakdown = financial_stats.get('revenue_breakdown', {})
        prometheus_metrics.extend([
            f'milla99_total_gross_revenue {revenue_breakdown.get("total_gross_revenue", 0)}',
            f'milla99_driver_net_income {revenue_breakdown.get("driver_net_income", 0)}',
            f'milla99_platform_commission {revenue_breakdown.get("platform_commission", 0)}',
            f'milla99_referral_payments {revenue_breakdown.get("referral_payments", 0)}',
            f'milla99_driver_savings {revenue_breakdown.get("driver_savings", 0)}',
            f'milla99_company_net_profit {revenue_breakdown.get("company_net_profit", 0)}'
        ])

        # Cash Flow Management
        cash_flow = financial_stats.get('cash_flow_management', {})
        prometheus_metrics.extend([
            f'milla99_total_money_in_system {cash_flow.get("total_money_in_system", 0)}',
            f'milla99_available_for_withdrawals {cash_flow.get("available_for_withdrawals", 0)}',
            f'milla99_reserved_money {cash_flow.get("reserved_money", 0)}',
            f'milla99_reserve_percentage {cash_flow.get("reserve_percentage", 0)}'
        ])

        # Drivers Analytics
        drivers_analytics = stats.get('drivers_analytics', {})
        driver_counts = drivers_analytics.get('driver_counts', {})
        prometheus_metrics.extend([
            f'milla99_total_drivers {driver_counts.get("total_drivers", 0)}',
            f'milla99_approved_drivers {driver_counts.get("approved_drivers", 0)}',
            f'milla99_pending_drivers {driver_counts.get("pending_drivers", 0)}',
            f'milla99_rejected_drivers {driver_counts.get("rejected_drivers", 0)}',
            f'milla99_suspended_drivers {driver_counts.get("suspended_drivers", 0)}',
            f'milla99_fully_verified_drivers {driver_counts.get("fully_verified_drivers", 0)}',
            f'milla99_new_drivers_this_month {driver_counts.get("new_drivers_this_month", 0)}'
        ])

        driver_activity = drivers_analytics.get('driver_activity', {})
        prometheus_metrics.extend([
            f'milla99_active_drivers_30_days {driver_activity.get("active_drivers_30_days", 0)}',
            f'milla99_active_drivers_7_days {driver_activity.get("active_drivers_7_days", 0)}',
            f'milla99_inactive_drivers {driver_activity.get("inactive_drivers", 0)}',
            f'milla99_activity_rate_30_days {driver_activity.get("activity_rate_30_days", 0)}'
        ])

        driver_rates = drivers_analytics.get('driver_rates', {})
        prometheus_metrics.extend([
            f'milla99_approval_rate {driver_rates.get("approval_rate", 0)}',
            f'milla99_verification_rate {driver_rates.get("verification_rate", 0)}',
            f'milla99_churn_rate {driver_rates.get("churn_rate", 0)}'
        ])

        # Suspension Stats
        suspension_stats = stats.get('suspended_drivers_stats', {})
        prometheus_metrics.extend([
            f'milla99_total_suspended_drivers {suspension_stats.get("total_suspended_drivers", 0)}',
            f'milla99_suspensions_lifted {suspension_stats.get("suspensions_lifted", 0)}',
            f'milla99_still_suspended {suspension_stats.get("still_suspended", 0)}'
        ])

        # Timestamp para indicar cuándo se generaron las métricas
        prometheus_metrics.append(
            f'milla99_metrics_timestamp {int(time.time())}')

        return Response(content='\n'.join(prometheus_metrics), media_type="text/plain")

    except Exception as e:
        # En caso de error, devolver métricas básicas
        return Response(
            content=f'milla99_metrics_error 1\nmilla99_metrics_error_message "{str(e)}"',
            media_type="text/plain"
        )
