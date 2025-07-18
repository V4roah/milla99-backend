from sqlmodel import Session, select
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID
import traceback
import inspect

# Importar modelos necesarios
from app.models.user import User
from app.models.client_request import ClientRequest, StatusEnum
from app.models.transaction import Transaction, TransactionType
from app.models.withdrawal import Withdrawal, WithdrawalStatus
from app.models.driver_documents import DriverDocuments, DriverStatus
from app.models.driver_info import DriverInfo
from app.models.vehicle_info import VehicleInfo
from app.models.vehicle_type import VehicleType
from app.models.user_has_roles import UserHasRole, RoleStatus
from app.models.driver_savings import DriverSavings
from app.models.project_settings import ProjectSettings
from app.models.company_account import CompanyAccount, cashflow
from app.models.type_service import TypeService

from sqlalchemy import func, and_, or_, text, case


class StatisticsService:
    def __init__(self, session: Session):
        self.session = session

    def _print_model_fields(self, model_class):
        """Imprime los campos de un modelo para depuración"""
        for field_name, field in model_class.model_fields.items():
            pass

    def _build_date_filter(self, query, start_date: Optional[date], end_date: Optional[date], date_field):
        """Construye el filtro de fechas para una consulta"""
        if start_date:
            query = query.where(date_field >= start_date)
        if end_date:
            end_of_day = datetime(
                end_date.year, end_date.month, end_date.day, 23, 59, 59)
            query = query.where(date_field <= end_of_day)
        return query

    def _get_base_query(self, model, start_date: Optional[date], end_date: Optional[date], date_field):
        """Construye una consulta base con filtros de fecha"""
        query = select(model)
        return self._build_date_filter(query, start_date, end_date, date_field)

    def get_summary_statistics(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        service_type_id: Optional[int] = None,
        driver_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtiene estadísticas resumidas del sistema.

        Args:
            start_date: Fecha de inicio para filtrar estadísticas
            end_date: Fecha de fin para filtrar estadísticas
            service_type_id: ID del tipo de servicio para filtrar
            driver_id: ID del conductor para filtrar

        Returns:
            Dict con estadísticas de usuarios, servicios y finanzas
        """
        try:
            response_data = {}

            # --- 1. Estadísticas de Usuarios ---
            # Total de conductores activos
            active_drivers_query = select(func.count(User.id)).select_from(User).join(
                UserHasRole, and_(
                    User.id == UserHasRole.id_user,
                    UserHasRole.id_rol == "DRIVER",
                    UserHasRole.status == RoleStatus.APPROVED
                )
            )
            active_drivers = self.session.exec(
                active_drivers_query).first() or 0

            # Conductores con documentos aprobados
            approved_docs_query = select(func.count(User.id)).select_from(User).join(
                DriverInfo, User.id == DriverInfo.user_id
            ).join(
                DriverDocuments, and_(
                    DriverInfo.id == DriverDocuments.driver_info_id,
                    DriverDocuments.status == DriverStatus.APPROVED
                )
            )
            approved_docs = self.session.exec(
                approved_docs_query).first() or 0

            # Conductores con vehículos registrados
            registered_vehicles_query = select(func.count(User.id)).select_from(User).join(
                DriverInfo, User.id == DriverInfo.user_id
            ).join(
                VehicleInfo, DriverInfo.id == VehicleInfo.driver_info_id
            )
            registered_vehicles = self.session.exec(
                registered_vehicles_query).first() or 0

            response_data["user_stats"] = {
                "active_drivers": active_drivers,
                "approved_docs": approved_docs,
                "registered_vehicles": registered_vehicles
            }

            # Clientes activos únicos
            active_clients_query = select(func.count(func.distinct(
                ClientRequest.id_client))).select_from(ClientRequest)
            active_clients_query = self._build_date_filter(
                active_clients_query, start_date, end_date, ClientRequest.created_at
            )
            if service_type_id:
                active_clients_query = active_clients_query.where(
                    ClientRequest.type_service_id == service_type_id)
            if driver_id:
                active_clients_query = active_clients_query.where(
                    ClientRequest.id_driver_assigned == driver_id)
            active_clients = self.session.exec(
                active_clients_query).first() or 0

            response_data["user_stats"]["active_clients"] = active_clients

            # --- 2. Estadísticas de Servicios ---
            # Convertir driver_id a UUID si existe
            driver_uuid = UUID(driver_id) if driver_id else None

            # Total de servicios completados
            completed_services_query = select(func.count(ClientRequest.id)).select_from(ClientRequest).where(
                ClientRequest.status == StatusEnum.PAID
            )
            if service_type_id:
                completed_services_query = completed_services_query.where(
                    ClientRequest.type_service_id == service_type_id
                )
            if driver_uuid:
                completed_services_query = completed_services_query.where(
                    ClientRequest.id_driver_assigned == driver_uuid
                )
            completed_services_query = self._build_date_filter(
                completed_services_query, start_date, end_date, ClientRequest.created_at)
            completed_services = self.session.exec(
                completed_services_query).first() or 0

            # Servicios cancelados
            cancelled_services_query = select(func.count(ClientRequest.id)).select_from(ClientRequest).where(
                ClientRequest.status == StatusEnum.CANCELLED
            )
            if service_type_id:
                cancelled_services_query = cancelled_services_query.where(
                    ClientRequest.type_service_id == service_type_id
                )
            if driver_uuid:
                cancelled_services_query = cancelled_services_query.where(
                    ClientRequest.id_driver_assigned == driver_uuid
                )
            cancelled_services_query = self._build_date_filter(
                cancelled_services_query, start_date, end_date, ClientRequest.created_at)
            cancelled_services = self.session.exec(
                cancelled_services_query).first() or 0

            # Servicios completados por tipo de servicio
            completed_services_by_type_query = select(
                TypeService.name, func.count(ClientRequest.id))
            completed_services_by_type_query = completed_services_by_type_query.join(
                TypeService, ClientRequest.type_service_id == TypeService.id
            ).where(
                ClientRequest.status == StatusEnum.PAID
            )
            if service_type_id:
                completed_services_by_type_query = completed_services_by_type_query.where(
                    ClientRequest.type_service_id == service_type_id
                )
            if driver_uuid:
                completed_services_by_type_query = completed_services_by_type_query.where(
                    ClientRequest.id_driver_assigned == driver_uuid
                )
            completed_services_by_type_query = self._build_date_filter(
                completed_services_by_type_query, start_date, end_date, ClientRequest.created_at)
            completed_services_by_type_query = completed_services_by_type_query.group_by(
                TypeService.name)
            completed_services_by_type = self.session.exec(
                completed_services_by_type_query).all()

            # Tasa de cancelación
            total_services = completed_services + cancelled_services
            cancellation_rate = (
                cancelled_services / total_services * 100) if total_services > 0 else 0

            response_data["service_stats"] = {
                "completed_services": completed_services,
                "cancelled_services": cancelled_services,
                "cancellation_rate": round(cancellation_rate, 2),
                "completed_by_type": [
                    {"type_name": name, "count": count}
                    for name, count in completed_services_by_type
                ]
            }

            # --- 3. Estadísticas Financieras ---
            # Obtener configuración del proyecto para porcentajes de comisión
            project_settings = self.session.exec(
                select(ProjectSettings)).first()
            company_commission_rate = float(
                project_settings.company) if project_settings and project_settings.company else 0.0

            # Ingresos totales (de la empresa, incluye servicios y adicionales)
            total_income_query = select(func.sum(CompanyAccount.income)).select_from(CompanyAccount).where(
                or_(
                    CompanyAccount.type == cashflow.SERVICE,
                    CompanyAccount.type == cashflow.ADDITIONAL
                )
            )
            total_income_query = self._build_date_filter(
                total_income_query, start_date, end_date, CompanyAccount.date)
            total_income = self.session.exec(total_income_query).first() or 0

            # Comisiones totales (de la empresa, específicamente por servicios)
            total_commission_query = select(func.sum(CompanyAccount.income)).select_from(CompanyAccount).where(
                CompanyAccount.type == cashflow.SERVICE
            )
            total_commission_query = self._build_date_filter(
                total_commission_query, start_date, end_date, CompanyAccount.date)
            total_commission = self.session.exec(
                total_commission_query).first() or 0

            # Retiros totales (gastos de la empresa por retiros de usuarios)
            total_withdrawals_query = select(func.sum(Transaction.expense)).select_from(Transaction).where(
                Transaction.type == TransactionType.WITHDRAWAL
            )
            if driver_uuid:
                total_withdrawals_query = total_withdrawals_query.where(
                    Transaction.user_id == driver_uuid)
            total_withdrawals_query = self._build_date_filter(
                total_withdrawals_query, start_date, end_date, Transaction.date)
            total_withdrawals = self.session.exec(
                total_withdrawals_query).first() or 0

            net_income = total_income - total_withdrawals

            # Ingresos promedio por conductor
            total_driver_gross_income_query = select(func.sum(ClientRequest.fare_assigned)).where(
                ClientRequest.status == StatusEnum.PAID
            )
            if service_type_id:
                total_driver_gross_income_query = total_driver_gross_income_query.where(
                    ClientRequest.type_service_id == service_type_id
                )
            if driver_uuid:
                total_driver_gross_income_query = total_driver_gross_income_query.where(
                    ClientRequest.id_driver_assigned == driver_uuid
                )
            total_driver_gross_income_query = self._build_date_filter(
                total_driver_gross_income_query, start_date, end_date, ClientRequest.updated_at)
            total_driver_gross_income = self.session.exec(
                total_driver_gross_income_query).first() or 0

            # Contar conductores únicos que completaron viajes
            unique_completed_drivers_query = select(func.count(func.distinct(ClientRequest.id_driver_assigned))).where(
                ClientRequest.status == StatusEnum.PAID,
                # Asegurar que hay un conductor asignado
                ClientRequest.id_driver_assigned != None
            )
            if service_type_id:
                unique_completed_drivers_query = unique_completed_drivers_query.where(
                    ClientRequest.type_service_id == service_type_id
                )
            if driver_uuid:
                unique_completed_drivers_query = unique_completed_drivers_query.where(
                    ClientRequest.id_driver_assigned == driver_uuid
                )
            unique_completed_drivers_query = self._build_date_filter(
                unique_completed_drivers_query, start_date, end_date, ClientRequest.updated_at)
            unique_completed_drivers = self.session.exec(
                unique_completed_drivers_query).first() or 0

            average_driver_income = (
                total_driver_gross_income / unique_completed_drivers
            ) if unique_completed_drivers > 0 else 0

            response_data["financial_stats"] = {
                "total_income": total_income,
                "total_commission": total_commission,
                "total_withdrawals": total_withdrawals,
                "net_income": net_income,
                "average_driver_income": round(average_driver_income, 2)
            }

            # --- 3.1. Revenue Breakdown (Desglose de Ingresos) ---
            # Ingresos brutos totales (todos los viajes completados)
            total_gross_revenue_query = select(func.sum(ClientRequest.fare_assigned)).where(
                ClientRequest.status == StatusEnum.PAID
            )
            if service_type_id:
                total_gross_revenue_query = total_gross_revenue_query.where(
                    ClientRequest.type_service_id == service_type_id
                )
            if driver_uuid:
                total_gross_revenue_query = total_gross_revenue_query.where(
                    ClientRequest.id_driver_assigned == driver_uuid
                )
            total_gross_revenue_query = self._build_date_filter(
                total_gross_revenue_query, start_date, end_date, ClientRequest.updated_at)
            total_gross_revenue = self.session.exec(
                total_gross_revenue_query).first() or 0

            # Pagos totales a referidos
            total_referral_payments_query = select(func.sum(Transaction.income)).where(
                Transaction.type.in_([
                    TransactionType.REFERRAL_1,
                    TransactionType.REFERRAL_2,
                    TransactionType.REFERRAL_3,
                    TransactionType.REFERRAL_4,
                    TransactionType.REFERRAL_5
                ])
            )
            if driver_uuid:
                total_referral_payments_query = total_referral_payments_query.where(
                    Transaction.user_id == driver_uuid
                )
            total_referral_payments_query = self._build_date_filter(
                total_referral_payments_query, start_date, end_date, Transaction.date)
            total_referral_payments = self.session.exec(
                total_referral_payments_query).first() or 0

            # Ahorros totales de conductores
            total_driver_savings_query = select(func.sum(DriverSavings.mount))
            if driver_uuid:
                total_driver_savings_query = total_driver_savings_query.where(
                    DriverSavings.user_id == driver_uuid
                )
            total_driver_savings_query = self._build_date_filter(
                total_driver_savings_query, start_date, end_date, DriverSavings.created_at)
            total_driver_savings = self.session.exec(
                total_driver_savings_query).first() or 0

            # Calcular distribución de ingresos
            driver_net_income = float(
                total_gross_revenue) * 0.85  # 85% para conductores
            # 10% comisión plataforma
            platform_commission = float(total_gross_revenue) * 0.10
            company_net_profit = float(total_income)  # Ya calculado arriba

            response_data["financial_stats"]["revenue_breakdown"] = {
                "total_gross_revenue": float(total_gross_revenue),
                "driver_net_income": round(driver_net_income, 2),
                "platform_commission": round(platform_commission, 2),
                "referral_payments": float(total_referral_payments),
                "driver_savings": float(total_driver_savings),
                "company_net_profit": company_net_profit
            }

            # --- 3.2. Cash Flow Management (Gestión de Liquidez) ---
            # Dinero total en el sistema (ingresos - retiros)
            total_money_in_system = float(total_income - total_withdrawals)

            # Reserva recomendada (10% del total)
            recommended_reserve = total_money_in_system * 0.10
            available_for_withdrawals = total_money_in_system - recommended_reserve

            # Determinar salud del flujo de caja
            if available_for_withdrawals > float(total_withdrawals) * 2:
                cash_flow_health = "healthy"
            elif available_for_withdrawals > float(total_withdrawals):
                cash_flow_health = "warning"
            else:
                cash_flow_health = "critical"

            response_data["financial_stats"]["cash_flow_management"] = {
                "total_money_in_system": total_money_in_system,
                "available_for_withdrawals": round(available_for_withdrawals, 2),
                "reserved_money": round(recommended_reserve, 2),
                "cash_flow_health": cash_flow_health,
                "reserve_percentage": 10.0
            }

            # --- 3.3. Withdrawal Tracking (Seguimiento de Retiros) ---
            # Retiros diarios
            daily_withdrawals_query = select(
                func.sum(Transaction.expense),
                func.count(Transaction.id)
            ).where(
                Transaction.type == TransactionType.WITHDRAWAL,
                Transaction.date >= func.date_sub(
                    func.curdate(), text('INTERVAL 1 DAY'))
            )
            if driver_uuid:
                daily_withdrawals_query = daily_withdrawals_query.where(
                    Transaction.user_id == driver_uuid
                )
            daily_result = self.session.exec(daily_withdrawals_query).first()
            daily_total = float(
                daily_result[0]) if daily_result and daily_result[0] else 0
            daily_count = daily_result[1] if daily_result and daily_result[1] else 0
            daily_average = daily_total / daily_count if daily_count > 0 else 0

            # Retiros semanales
            weekly_withdrawals_query = select(
                func.sum(Transaction.expense),
                func.count(Transaction.id)
            ).where(
                Transaction.type == TransactionType.WITHDRAWAL,
                Transaction.date >= func.date_sub(
                    func.curdate(), text('INTERVAL 7 DAY'))
            )
            if driver_uuid:
                weekly_withdrawals_query = weekly_withdrawals_query.where(
                    Transaction.user_id == driver_uuid
                )
            weekly_result = self.session.exec(weekly_withdrawals_query).first()
            weekly_total = float(
                weekly_result[0]) if weekly_result and weekly_result[0] else 0
            weekly_count = weekly_result[1] if weekly_result and weekly_result[1] else 0
            weekly_average = weekly_total / weekly_count if weekly_count > 0 else 0

            # Retiros quincenales
            biweekly_withdrawals_query = select(
                func.sum(Transaction.expense),
                func.count(Transaction.id)
            ).where(
                Transaction.type == TransactionType.WITHDRAWAL,
                Transaction.date >= func.date_sub(
                    func.curdate(), text('INTERVAL 15 DAY'))
            )
            if driver_uuid:
                biweekly_withdrawals_query = biweekly_withdrawals_query.where(
                    Transaction.user_id == driver_uuid
                )
            biweekly_result = self.session.exec(
                biweekly_withdrawals_query).first()
            biweekly_total = float(
                biweekly_result[0]) if biweekly_result and biweekly_result[0] else 0
            biweekly_count = biweekly_result[1] if biweekly_result and biweekly_result[1] else 0
            biweekly_average = biweekly_total / biweekly_count if biweekly_count > 0 else 0

            # Retiros mensuales
            monthly_withdrawals_query = select(
                func.sum(Transaction.expense),
                func.count(Transaction.id)
            ).where(
                Transaction.type == TransactionType.WITHDRAWAL,
                Transaction.date >= func.date_sub(
                    func.curdate(), text('INTERVAL 30 DAY'))
            )
            if driver_uuid:
                monthly_withdrawals_query = monthly_withdrawals_query.where(
                    Transaction.user_id == driver_uuid
                )
            monthly_result = self.session.exec(
                monthly_withdrawals_query).first()
            monthly_total = float(
                monthly_result[0]) if monthly_result and monthly_result[0] else 0
            monthly_count = monthly_result[1] if monthly_result and monthly_result[1] else 0
            monthly_average = monthly_total / monthly_count if monthly_count > 0 else 0

            # Calcular tendencias
            def get_trend(current, previous):
                if previous == 0:
                    return "stable"
                change = ((current - previous) / previous) * 100
                if change > 10:
                    return "increasing"
                elif change < -10:
                    return "decreasing"
                else:
                    return "stable"

            daily_trend = get_trend(daily_total, weekly_total / 7)
            weekly_trend = get_trend(weekly_total, biweekly_total / 2)
            biweekly_trend = get_trend(biweekly_total, monthly_total / 2)
            # Comparar con mes anterior
            monthly_trend = get_trend(monthly_total, monthly_total)

            response_data["financial_stats"]["withdrawal_tracking"] = {
                "daily": {
                    "total": daily_total,
                    "count": daily_count,
                    "average": round(daily_average, 2),
                    "trend": daily_trend,
                    "percentage_change": 0.0  # Simplificado por ahora
                },
                "weekly": {
                    "total": weekly_total,
                    "count": weekly_count,
                    "average": round(weekly_average, 2),
                    "trend": weekly_trend,
                    "percentage_change": 0.0
                },
                "biweekly": {
                    "total": biweekly_total,
                    "count": biweekly_count,
                    "average": round(biweekly_average, 2),
                    "trend": biweekly_trend,
                    "percentage_change": 0.0
                },
                "monthly": {
                    "total": monthly_total,
                    "count": monthly_count,
                    "average": round(monthly_average, 2),
                    "trend": monthly_trend,
                    "percentage_change": 0.0
                }
            }

            # --- 3.4. Liquidity Alerts (Alertas de Liquidez) ---
            # Verificar si hay fondos suficientes
            insufficient_funds = available_for_withdrawals < float(
                total_withdrawals) * 0.5

            # Verificar tasa de retiros alta
            high_withdrawal_rate = float(daily_total) > (
                total_money_in_system * 0.1)

            # Verificar flujo de caja negativo
            cash_flow_negative = float(total_withdrawals) > float(total_income)

            # Verificar reservas agotadas
            reserve_depleted = available_for_withdrawals < recommended_reserve

            # Generar recomendaciones
            recommendations = []
            if insufficient_funds:
                recommendations.append(
                    "Fondos insuficientes para cubrir retiros pendientes")
            if high_withdrawal_rate:
                recommendations.append(
                    "Tasa de retiros muy alta - monitorear de cerca")
            if cash_flow_negative:
                recommendations.append(
                    "Flujo de caja negativo - revisar ingresos vs gastos")
            if reserve_depleted:
                recommendations.append(
                    "Reservas agotadas - aumentar capital de trabajo")

            if not recommendations:
                recommendations.append(
                    "Estado financiero saludable - mantener monitoreo regular")

            response_data["financial_stats"]["liquidity_alerts"] = {
                "insufficient_funds": insufficient_funds,
                "high_withdrawal_rate": high_withdrawal_rate,
                "cash_flow_negative": cash_flow_negative,
                "reserve_depleted": reserve_depleted,
                "recommendations": recommendations
            }

            # --- 3.5. Profitability Analysis (Análisis de Rentabilidad por Segmento) ---
            # Rentabilidad por tipo de servicio
            profitability_by_service_query = select(
                TypeService.name,
                func.sum(ClientRequest.fare_assigned).label('revenue'),
                func.count(ClientRequest.id).label('trip_count')
            ).join(
                TypeService, ClientRequest.type_service_id == TypeService.id
            ).where(
                ClientRequest.status == StatusEnum.PAID
            )

            if service_type_id:
                profitability_by_service_query = profitability_by_service_query.where(
                    ClientRequest.type_service_id == service_type_id
                )
            if driver_uuid:
                profitability_by_service_query = profitability_by_service_query.where(
                    ClientRequest.id_driver_assigned == driver_uuid
                )

            profitability_by_service_query = self._build_date_filter(
                profitability_by_service_query, start_date, end_date, ClientRequest.created_at
            )
            profitability_by_service_query = profitability_by_service_query.group_by(
                TypeService.name)

            service_profitability_results = self.session.exec(
                profitability_by_service_query).all()

            profit_margin_by_service_type = {}
            for service_name, revenue, trip_count in service_profitability_results:
                revenue = float(revenue) if revenue else 0

                # Calcular costos basados en la distribución estándar
                # 85% para conductores, 10% comisión plataforma, 1% ahorros, 4% empresa
                driver_costs = revenue * 0.85  # 85% para conductores
                platform_commission = revenue * 0.10  # 10% comisión
                driver_savings = revenue * 0.01  # 1% ahorros
                total_costs = driver_costs + platform_commission + driver_savings

                profit = revenue - total_costs
                margin_percentage = (profit / revenue *
                                     100) if revenue > 0 else 0

                profit_margin_by_service_type[service_name.lower().replace(' ', '_')] = {
                    "revenue": revenue,
                    "costs": round(total_costs, 2),
                    "profit": round(profit, 2),
                    "margin_percentage": round(margin_percentage, 2),
                    "trip_count": trip_count,
                    "average_revenue_per_trip": round(revenue / trip_count, 2) if trip_count > 0 else 0
                }

            # Rentabilidad por zona (usando pickup_description)
            profitability_by_zone_query = select(
                ClientRequest.pickup_description,
                func.sum(ClientRequest.fare_assigned).label('revenue'),
                func.count(ClientRequest.id).label('trip_count')
            ).where(
                ClientRequest.status == StatusEnum.PAID,
                ClientRequest.pickup_description.is_not(None)
            )

            if service_type_id:
                profitability_by_zone_query = profitability_by_zone_query.where(
                    ClientRequest.type_service_id == service_type_id
                )
            if driver_uuid:
                profitability_by_zone_query = profitability_by_zone_query.where(
                    ClientRequest.id_driver_assigned == driver_uuid
                )

            profitability_by_zone_query = self._build_date_filter(
                profitability_by_zone_query, start_date, end_date, ClientRequest.created_at
            )
            profitability_by_zone_query = profitability_by_zone_query.group_by(
                ClientRequest.pickup_description)

            zone_profitability_results = self.session.exec(
                profitability_by_zone_query).all()

            profit_margin_by_zone = {}
            for zone_name, revenue, trip_count in zone_profitability_results:
                if not zone_name:  # Saltar zonas sin nombre
                    continue

                revenue = float(revenue) if revenue else 0

                # Calcular costos usando la misma distribución
                driver_costs = revenue * 0.85
                platform_commission = revenue * 0.10
                driver_savings = revenue * 0.01
                total_costs = driver_costs + platform_commission + driver_savings

                profit = revenue - total_costs
                margin_percentage = (profit / revenue *
                                     100) if revenue > 0 else 0

                # Normalizar nombre de zona
                zone_key = zone_name.lower().replace(' ', '_').replace(',', '_').replace('.', '_')

                profit_margin_by_zone[zone_key] = {
                    "zone_name": zone_name,
                    "revenue": revenue,
                    "costs": round(total_costs, 2),
                    "profit": round(profit, 2),
                    "margin_percentage": round(margin_percentage, 2),
                    "trip_count": trip_count,
                    "average_revenue_per_trip": round(revenue / trip_count, 2) if trip_count > 0 else 0
                }

            # Resumen de rentabilidad general
            total_revenue_all_services = sum(
                item["revenue"] for item in profit_margin_by_service_type.values())
            total_costs_all_services = sum(
                item["costs"] for item in profit_margin_by_service_type.values())
            total_profit_all_services = sum(
                item["profit"] for item in profit_margin_by_service_type.values())
            overall_margin = (total_profit_all_services / total_revenue_all_services *
                              100) if total_revenue_all_services > 0 else 0

            response_data["financial_stats"]["profitability_analysis"] = {
                "profit_margin_by_service_type": profit_margin_by_service_type,
                "profit_margin_by_zone": profit_margin_by_zone,
                "overall_summary": {
                    "total_revenue": total_revenue_all_services,
                    "total_costs": round(total_costs_all_services, 2),
                    "total_profit": round(total_profit_all_services, 2),
                    "overall_margin_percentage": round(overall_margin, 2),
                    "most_profitable_service": max(profit_margin_by_service_type.items(), key=lambda x: x[1]["margin_percentage"])[0] if profit_margin_by_service_type else None,
                    "most_profitable_zone": max(profit_margin_by_zone.items(), key=lambda x: x[1]["margin_percentage"])[0] if profit_margin_by_zone else None
                }
            }

            # --- 3.6. Vehicle Type Analytics (Estadísticas Detalladas por Tipo de Vehículo) ---
            # Conductores por tipo de vehículo
            drivers_by_vehicle_type_query = select(
                VehicleType.name,
                func.count(func.distinct(User.id)).label('total_drivers'),
                func.count(func.distinct(
                    case(
                        (and_(
                            ClientRequest.id_driver_assigned.is_not(None),
                            ClientRequest.created_at >= func.date_sub(
                                func.curdate(), text('INTERVAL 30 DAY'))
                        ), User.id),
                        else_=None
                    )
                )).label('active_drivers'),
                func.count(func.distinct(
                    case(
                        (and_(
                            DriverDocuments.status == DriverStatus.APPROVED,
                            DriverDocuments.document_type_id.is_not(None)
                        ), User.id),
                        else_=None
                    )
                )).label('drivers_with_approved_docs')
            ).join(
                UserHasRole, and_(
                    User.id == UserHasRole.id_user,
                    UserHasRole.id_rol == "DRIVER",
                    UserHasRole.status == RoleStatus.APPROVED
                )
            ).join(
                DriverInfo, User.id == DriverInfo.user_id
            ).join(
                VehicleInfo, DriverInfo.id == VehicleInfo.driver_info_id
            ).join(
                VehicleType, VehicleInfo.vehicle_type_id == VehicleType.id
            ).outerjoin(
                ClientRequest, User.id == ClientRequest.id_driver_assigned
            ).outerjoin(
                DriverDocuments, DriverInfo.id == DriverDocuments.driver_info_id
            ).group_by(VehicleType.name)

            drivers_by_vehicle_results = self.session.exec(
                drivers_by_vehicle_type_query).all()

            drivers_by_vehicle_type = {}
            for vehicle_type_name, total_drivers, active_drivers, drivers_with_docs in drivers_by_vehicle_results:
                vehicle_key = vehicle_type_name.lower().replace(' ', '_')
                drivers_by_vehicle_type[vehicle_key] = {
                    "total": total_drivers,
                    "active": active_drivers,
                    "with_approved_docs": drivers_with_docs,
                    "vehicle_type_name": vehicle_type_name
                }

            # Rendimiento por tipo de vehículo
            performance_by_vehicle_query = select(
                VehicleType.name,
                func.count(ClientRequest.id).label('total_trips'),
                func.sum(ClientRequest.fare_assigned).label('total_revenue'),
                func.avg(ClientRequest.fare_assigned).label(
                    'average_trip_value'),
                func.avg(ClientRequest.driver_rating).label('average_rating')
            ).join(
                TypeService, VehicleType.id == TypeService.vehicle_type_id
            ).join(
                ClientRequest, TypeService.id == ClientRequest.type_service_id
            ).where(
                ClientRequest.status == StatusEnum.PAID
            )

            if service_type_id:
                performance_by_vehicle_query = performance_by_vehicle_query.where(
                    ClientRequest.type_service_id == service_type_id
                )
            if driver_uuid:
                performance_by_vehicle_query = performance_by_vehicle_query.where(
                    ClientRequest.id_driver_assigned == driver_uuid
                )

            performance_by_vehicle_query = self._build_date_filter(
                performance_by_vehicle_query, start_date, end_date, ClientRequest.created_at
            )
            performance_by_vehicle_query = performance_by_vehicle_query.group_by(
                VehicleType.name)

            performance_results = self.session.exec(
                performance_by_vehicle_query).all()

            performance_by_vehicle_type = {}
            for vehicle_type_name, total_trips, total_revenue, avg_trip_value, avg_rating in performance_results:
                vehicle_key = vehicle_type_name.lower().replace(' ', '_')
                performance_by_vehicle_type[vehicle_key] = {
                    "total_trips": total_trips,
                    "total_revenue": float(total_revenue) if total_revenue else 0,
                    "average_trip_value": round(float(avg_trip_value), 2) if avg_trip_value else 0,
                    "average_rating": round(float(avg_rating), 2) if avg_rating else 0,
                    "vehicle_type_name": vehicle_type_name
                }

            # Top performers por tipo de vehículo
            top_performers_by_vehicle = {}
            for vehicle_type_name in [vt.name for vt in self.session.exec(select(VehicleType)).all()]:
                vehicle_key = vehicle_type_name.lower().replace(' ', '_')

                top_performers_query = select(
                    User.id,
                    User.full_name,
                    func.count(ClientRequest.id).label('total_trips'),
                    func.sum(ClientRequest.fare_assigned).label(
                        'total_revenue'),
                    func.avg(ClientRequest.driver_rating).label(
                        'average_rating')
                ).join(
                    UserHasRole, and_(
                        User.id == UserHasRole.id_user,
                        UserHasRole.id_rol == "DRIVER",
                        UserHasRole.status == RoleStatus.APPROVED
                    )
                ).join(
                    DriverInfo, User.id == DriverInfo.user_id
                ).join(
                    VehicleInfo, DriverInfo.id == VehicleInfo.driver_info_id
                ).join(
                    VehicleType, VehicleInfo.vehicle_type_id == VehicleType.id
                ).join(
                    ClientRequest, User.id == ClientRequest.id_driver_assigned
                ).where(
                    VehicleType.name == vehicle_type_name,
                    ClientRequest.status == StatusEnum.PAID
                )

                if service_type_id:
                    top_performers_query = top_performers_query.where(
                        ClientRequest.type_service_id == service_type_id
                    )
                if driver_uuid:
                    top_performers_query = top_performers_query.where(
                        ClientRequest.id_driver_assigned == driver_uuid
                    )

                top_performers_query = self._build_date_filter(
                    top_performers_query, start_date, end_date, ClientRequest.created_at
                )
                top_performers_query = top_performers_query.group_by(
                    User.id, User.full_name)
                top_performers_query = top_performers_query.order_by(
                    func.count(ClientRequest.id).desc())
                top_performers_query = top_performers_query.limit(
                    5)  # Top 5 conductores

                top_performers_results = self.session.exec(
                    top_performers_query).all()

                top_performers_by_vehicle[vehicle_key] = [
                    {
                        "driver_id": str(driver_id),
                        "driver_name": driver_name,
                        "vehicle_type": vehicle_type_name,
                        "total_trips": total_trips,
                        "total_revenue": float(total_revenue) if total_revenue else 0,
                        "average_rating": round(float(avg_rating), 2) if avg_rating else 0
                    }
                    for driver_id, driver_name, total_trips, total_revenue, avg_rating in top_performers_results
                ]

            response_data["vehicle_analytics"] = {
                "drivers_by_vehicle_type": drivers_by_vehicle_type,
                "performance_by_vehicle_type": performance_by_vehicle_type,
                "top_performers_by_vehicle": top_performers_by_vehicle,
                "summary": {
                    "total_vehicle_types": len(drivers_by_vehicle_type),
                    "most_popular_vehicle": max(drivers_by_vehicle_type.items(), key=lambda x: x[1]["total"])[0] if drivers_by_vehicle_type else None,
                    "highest_revenue_vehicle": max(performance_by_vehicle_type.items(), key=lambda x: x[1]["total_revenue"])[0] if performance_by_vehicle_type else None,
                    "best_rated_vehicle": max(performance_by_vehicle_type.items(), key=lambda x: x[1]["average_rating"])[0] if performance_by_vehicle_type else None
                }
            }

            # --- 3.7. Drivers Analytics (Análisis Detallado de Conductores) ---
            # Total de conductores registrados
            total_drivers_query = select(func.count(User.id)).select_from(User).join(
                UserHasRole, and_(
                    User.id == UserHasRole.id_user,
                    UserHasRole.id_rol == "DRIVER"
                )
            )
            total_drivers = self.session.exec(total_drivers_query).first() or 0

            # Conductores aprobados
            approved_drivers_query = select(func.count(User.id)).select_from(User).join(
                UserHasRole, and_(
                    User.id == UserHasRole.id_user,
                    UserHasRole.id_rol == "DRIVER",
                    UserHasRole.status == RoleStatus.APPROVED
                )
            )
            approved_drivers = self.session.exec(
                approved_drivers_query).first() or 0

            # Conductores pendientes de aprobación
            pending_drivers_query = select(func.count(User.id)).select_from(User).join(
                UserHasRole, and_(
                    User.id == UserHasRole.id_user,
                    UserHasRole.id_rol == "DRIVER",
                    UserHasRole.status == RoleStatus.PENDING
                )
            )
            pending_drivers = self.session.exec(
                pending_drivers_query).first() or 0

            # Conductores rechazados
            rejected_drivers_query = select(func.count(User.id)).select_from(User).join(
                UserHasRole, and_(
                    User.id == UserHasRole.id_user,
                    UserHasRole.id_rol == "DRIVER",
                    UserHasRole.status == RoleStatus.REJECTED
                )
            )
            rejected_drivers = self.session.exec(
                rejected_drivers_query).first() or 0

            # Conductores suspendidos
            suspended_drivers_query = select(func.count(User.id)).select_from(User).join(
                UserHasRole, and_(
                    User.id == UserHasRole.id_user,
                    UserHasRole.id_rol == "DRIVER",
                    UserHasRole.suspension == True
                )
            )
            suspended_drivers = self.session.exec(
                suspended_drivers_query).first() or 0

            # Conductores con documentos completos aprobados
            fully_verified_drivers_query = select(func.count(func.distinct(User.id))).select_from(User).join(
                UserHasRole, and_(
                    User.id == UserHasRole.id_user,
                    UserHasRole.id_rol == "DRIVER",
                    UserHasRole.status == RoleStatus.APPROVED
                )
            ).join(
                DriverInfo, User.id == DriverInfo.user_id
            ).join(
                DriverDocuments, and_(
                    DriverInfo.id == DriverDocuments.driver_info_id,
                    DriverDocuments.status == DriverStatus.APPROVED
                )
            ).join(
                VehicleInfo, DriverInfo.id == VehicleInfo.driver_info_id
            )
            fully_verified_drivers = self.session.exec(
                fully_verified_drivers_query).first() or 0

            # Conductores activos (con viajes en los últimos 30 días)
            active_drivers_30_days_query = select(func.count(func.distinct(ClientRequest.id_driver_assigned))).where(
                ClientRequest.id_driver_assigned.is_not(None),
                ClientRequest.created_at >= func.date_sub(
                    func.curdate(), text('INTERVAL 30 DAY'))
            )
            active_drivers_30_days = self.session.exec(
                active_drivers_30_days_query).first() or 0

            # Conductores activos (con viajes en los últimos 7 días)
            active_drivers_7_days_query = select(func.count(func.distinct(ClientRequest.id_driver_assigned))).where(
                ClientRequest.id_driver_assigned.is_not(None),
                ClientRequest.created_at >= func.date_sub(
                    func.curdate(), text('INTERVAL 7 DAY'))
            )
            active_drivers_7_days = self.session.exec(
                active_drivers_7_days_query).first() or 0

            # Conductores nuevos este mes
            new_drivers_this_month_query = select(func.count(User.id)).select_from(User).join(
                UserHasRole, and_(
                    User.id == UserHasRole.id_user,
                    UserHasRole.id_rol == "DRIVER"
                )
            ).where(
                User.created_at >= func.date_sub(
                    func.curdate(), text('INTERVAL 30 DAY'))
            )
            new_drivers_this_month = self.session.exec(
                new_drivers_this_month_query).first() or 0

            # Conductores que dejaron de usar la plataforma (sin viajes en 30 días)
            inactive_drivers_query = select(func.count(func.distinct(User.id))).select_from(User).join(
                UserHasRole, and_(
                    User.id == UserHasRole.id_user,
                    UserHasRole.id_rol == "DRIVER",
                    UserHasRole.status == RoleStatus.APPROVED
                )
            ).outerjoin(
                ClientRequest, and_(
                    User.id == ClientRequest.id_driver_assigned,
                    ClientRequest.created_at >= func.date_sub(
                        func.curdate(), text('INTERVAL 30 DAY'))
                )
            ).where(
                ClientRequest.id_driver_assigned.is_(None)
            )
            inactive_drivers = self.session.exec(
                inactive_drivers_query).first() or 0

            # Calcular tasas
            approval_rate = (approved_drivers / total_drivers *
                             100) if total_drivers > 0 else 0
            verification_rate = (
                fully_verified_drivers / approved_drivers * 100) if approved_drivers > 0 else 0
            activity_rate_30_days = (
                active_drivers_30_days / approved_drivers * 100) if approved_drivers > 0 else 0
            churn_rate = (inactive_drivers / approved_drivers *
                          100) if approved_drivers > 0 else 0

            response_data["drivers_analytics"] = {
                "driver_counts": {
                    # Total de conductores registrados
                    "total_drivers": total_drivers,
                    "approved_drivers": approved_drivers,                     # Conductores aprobados
                    # Conductores pendientes de aprobación
                    "pending_drivers": pending_drivers,
                    "rejected_drivers": rejected_drivers,                     # Conductores rechazados
                    # Conductores suspendidos
                    "suspended_drivers": suspended_drivers,
                    # Conductores completamente verificados
                    "fully_verified_drivers": fully_verified_drivers,
                    # Conductores nuevos este mes
                    "new_drivers_this_month": new_drivers_this_month
                },
                "driver_activity": {
                    # Activos en últimos 30 días
                    "active_drivers_30_days": active_drivers_30_days,
                    # Activos en últimos 7 días
                    "active_drivers_7_days": active_drivers_7_days,
                    # Inactivos (sin viajes en 30 días)
                    "inactive_drivers": inactive_drivers,
                    # % de conductores activos
                    "activity_rate_30_days": round(activity_rate_30_days, 2)
                },
                "driver_rates": {
                    # % de aprobación
                    "approval_rate": round(approval_rate, 2),
                    # % de verificación completa
                    "verification_rate": round(verification_rate, 2),
                    # % de conductores inactivos
                    "churn_rate": round(churn_rate, 2)
                },
                "verification_status": {
                    # Completamente verificados
                    "fully_verified": fully_verified_drivers,
                    # Parcialmente verificados
                    "partially_verified": approved_drivers - fully_verified_drivers,
                    "not_verified": total_drivers - approved_drivers          # No verificados
                },
                "summary": {
                    "total_verified_drivers": fully_verified_drivers,         # Total verificados
                    # % de verificación
                    "verification_completion": round(verification_rate, 2),
                    # % de retención
                    "driver_retention": round(100 - churn_rate, 2),
                    # % de crecimiento
                    "growth_rate": round((new_drivers_this_month / total_drivers * 100), 2) if total_drivers > 0 else 0
                }
            }

            # --- 4. Estadísticas de Suspensiones ---
            suspended_drivers_stats = self.batch_check_all_suspended_drivers()
            response_data["suspended_drivers_stats"] = suspended_drivers_stats

            return response_data

        except Exception as e:
            raise

    def batch_check_all_suspended_drivers(self):
        """
        Método para verificar y levantar suspensiones de todos los conductores suspendidos.
        Útil para ejecutar como tarea programada (cron job).

        Returns:
            dict: Resumen de las suspensiones levantadas
        """
        # Importar la función desde client_requests_service
        from app.services.client_requests_service import check_and_lift_driver_suspension

        # Obtener todos los conductores suspendidos
        suspended_drivers = self.session.exec(
            select(UserHasRole).where(
                UserHasRole.id_rol == "DRIVER",
                UserHasRole.suspension == True
            )
        ).all()

        lifted_suspensions = []
        still_suspended = []

        for driver in suspended_drivers:
            result = check_and_lift_driver_suspension(
                self.session, driver.id_user)

            if result["success"] and not result.get("is_suspended", True):
                lifted_suspensions.append({
                    "driver_id": str(driver.id_user),
                    "message": result["message"]
                })
            else:
                still_suspended.append({
                    "driver_id": str(driver.id_user),
                    "message": result["message"]
                })

        return {
            "success": True,
            "total_suspended_drivers": len(suspended_drivers),
            "suspensions_lifted": len(lifted_suspensions),
            "still_suspended": len(still_suspended),
            "lifted_details": lifted_suspensions,
            "still_suspended_details": still_suspended
        }
