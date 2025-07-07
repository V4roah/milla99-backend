from sqlmodel import Session, select
from app.models.user_fcm_token import UserFCMToken
from app.models.user import User
from app.models.client_request import ClientRequest
from app.models.driver_trip_offer import DriverTripOffer
from app.models.driver_info import DriverInfo
from app.models.vehicle_info import VehicleInfo
from app.services.user_fcm_token_service import UserFCMTokenService
from app.utils.notification_templates import NotificationTemplates
from uuid import UUID
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Servicio principal de notificaciones push para Milla99.
    Maneja el envío de notificaciones de negocio usando las plantillas
    y el servicio de FCM.
    """

    def __init__(self, session: Session):
        self.session = session
        self.fcm_service = UserFCMTokenService(session)

    def _get_user_tokens(self, user_id: UUID, active_only: bool = True) -> List[str]:
        """
        Obtiene los tokens FCM de un usuario.

        Args:
            user_id: ID del usuario
            active_only: Si True, solo tokens activos. Si False, todos los tokens.

        Returns:
            Lista de tokens FCM
        """
        try:
            if active_only:
                tokens = self.fcm_service.get_active_tokens(user_id)
            else:
                all_tokens = self.fcm_service.get_all_tokens(user_id)
                tokens = [
                    token.fcm_token for token in all_tokens if token.is_active]

            logger.info(
                f"Obtenidos {len(tokens)} tokens para usuario {user_id}")
            return tokens
        except Exception as e:
            logger.error(
                f"Error obteniendo tokens para usuario {user_id}: {e}")
            return []

    def _send_notification(self, user_id: UUID, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía una notificación a un usuario específico.

        Args:
            user_id: ID del usuario destinatario
            notification_data: Datos de la notificación (title, body, data)

        Returns:
            Resultado del envío
        """
        try:
            tokens = self._get_user_tokens(user_id)
            if not tokens:
                logger.warning(f"No hay tokens activos para usuario {user_id}")
                return {"success": 0, "failed": 0, "error": "No tokens available"}

            result = self.fcm_service.send_notification(
                tokens=tokens,
                title=notification_data["title"],
                body=notification_data["body"],
                data=notification_data.get("data", {})
            )

            logger.info(f"Notificación enviada a usuario {user_id}: {result}")
            return result

        except Exception as e:
            logger.error(
                f"Error enviando notificación a usuario {user_id}: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}

    def _get_driver_info(self, driver_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Obtiene información del conductor para las notificaciones.

        Args:
            driver_id: ID del conductor

        Returns:
            Diccionario con información del conductor
        """
        try:
            driver = self.session.get(User, driver_id)
            if not driver:
                return None

            driver_info = self.session.exec(
                select(DriverInfo).where(DriverInfo.user_id == driver_id)
            ).first()

            vehicle_info = None
            if driver_info:
                vehicle_info = self.session.exec(
                    select(VehicleInfo).where(VehicleInfo.user_id == driver_id)
                ).first()

            return {
                "name": f"{driver_info.first_name} {driver_info.last_name}" if driver_info else "Conductor",
                "vehicle": f"{vehicle_info.brand} {vehicle_info.model} - {vehicle_info.plate}" if vehicle_info else "Vehículo",
                "full_name": driver.full_name
            }
        except Exception as e:
            logger.error(
                f"Error obteniendo información del conductor {driver_id}: {e}")
            return None

    # ===== MÉTODOS DE NOTIFICACIONES PARA CLIENTES =====

    def notify_driver_offer(self, request_id: UUID, driver_id: UUID, fare: float) -> Dict[str, Any]:
        """
        Notifica al cliente cuando un conductor hace una oferta.

        Args:
            request_id: ID de la solicitud
            driver_id: ID del conductor
            fare: Tarifa ofrecida

        Returns:
            Resultado del envío
        """
        try:
            # Obtener información del cliente
            client_request = self.session.get(ClientRequest, request_id)
            if not client_request:
                logger.error(f"Solicitud {request_id} no encontrada")
                return {"success": 0, "failed": 0, "error": "Request not found"}

            # Obtener información del conductor
            driver_info = self._get_driver_info(driver_id)
            if not driver_info:
                logger.error(
                    f"Información del conductor {driver_id} no encontrada")
                return {"success": 0, "failed": 0, "error": "Driver info not found"}

            # Crear notificación
            notification = NotificationTemplates.driver_offer_received(
                request_id=request_id,
                driver_name=driver_info["name"],
                fare=fare
            )

            # Enviar notificación al cliente
            return self._send_notification(client_request.id_client, notification)

        except Exception as e:
            logger.error(f"Error notificando oferta de conductor: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}

    def notify_driver_assigned(self, request_id: UUID, driver_id: UUID) -> Dict[str, Any]:
        """
        Notifica al cliente cuando se asigna un conductor.

        Args:
            request_id: ID de la solicitud
            driver_id: ID del conductor

        Returns:
            Resultado del envío
        """
        try:
            # Obtener información del cliente
            client_request = self.session.get(ClientRequest, request_id)
            if not client_request:
                logger.error(f"Solicitud {request_id} no encontrada")
                return {"success": 0, "failed": 0, "error": "Request not found"}

            # Obtener información del conductor
            driver_info = self._get_driver_info(driver_id)
            if not driver_info:
                logger.error(
                    f"Información del conductor {driver_id} no encontrada")
                return {"success": 0, "failed": 0, "error": "Driver info not found"}

            # Crear notificación
            notification = NotificationTemplates.driver_assigned(
                request_id=request_id,
                driver_name=driver_info["name"],
                vehicle_info=driver_info["vehicle"]
            )

            # Enviar notificación al cliente
            return self._send_notification(client_request.id_client, notification)

        except Exception as e:
            logger.error(f"Error notificando conductor asignado: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}

    def notify_driver_status_change(self, request_id: UUID, status: str, estimated_time: Optional[int] = None) -> Dict[str, Any]:
        """
        Notifica al cliente cuando el conductor cambia el estado del viaje.

        Args:
            request_id: ID de la solicitud
            status: Nuevo estado
            estimated_time: Tiempo estimado (solo para ON_THE_WAY)

        Returns:
            Resultado del envío
        """
        try:
            # Obtener información del cliente
            client_request = self.session.get(ClientRequest, request_id)
            if not client_request:
                logger.error(f"Solicitud {request_id} no encontrada")
                return {"success": 0, "failed": 0, "error": "Request not found"}

            # Crear notificación según el estado
            if status == "ON_THE_WAY":
                notification = NotificationTemplates.driver_on_the_way(
                    request_id=request_id,
                    estimated_time=estimated_time or 10
                )
            elif status == "ARRIVED":
                notification = NotificationTemplates.driver_arrived(
                    request_id=request_id)
            elif status == "TRAVELLING":
                notification = NotificationTemplates.trip_started(
                    request_id=request_id)
            elif status == "FINISHED":
                fare = client_request.fare_assigned or client_request.fare_offered or 0
                notification = NotificationTemplates.trip_finished(
                    request_id=request_id,
                    fare=fare
                )
            else:
                logger.warning(
                    f"Estado {status} no tiene notificación configurada")
                return {"success": 0, "failed": 0, "error": "Status not configured"}

            # Enviar notificación al cliente
            return self._send_notification(client_request.id_client, notification)

        except Exception as e:
            logger.error(f"Error notificando cambio de estado: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}

    def notify_trip_cancelled_by_driver(self, request_id: UUID, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Notifica al cliente cuando el conductor cancela el viaje.

        Args:
            request_id: ID de la solicitud
            reason: Razón de la cancelación

        Returns:
            Resultado del envío
        """
        try:
            # Obtener información del cliente
            client_request = self.session.get(ClientRequest, request_id)
            if not client_request:
                logger.error(f"Solicitud {request_id} no encontrada")
                return {"success": 0, "failed": 0, "error": "Request not found"}

            # Crear notificación
            notification = NotificationTemplates.trip_cancelled_by_driver(
                request_id=request_id,
                reason=reason
            )

            # Enviar notificación al cliente
            return self._send_notification(client_request.id_client, notification)

        except Exception as e:
            logger.error(f"Error notificando cancelación por conductor: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}

    # ===== MÉTODOS DE NOTIFICACIONES PARA CONDUCTORES =====

    def notify_trip_assigned(self, request_id: UUID, driver_id: UUID) -> Dict[str, Any]:
        """
        Notifica al conductor cuando se le asigna un viaje.

        Args:
            request_id: ID de la solicitud
            driver_id: ID del conductor

        Returns:
            Resultado del envío
        """
        try:
            # Obtener información de la solicitud
            client_request = self.session.get(ClientRequest, request_id)
            if not client_request:
                logger.error(f"Solicitud {request_id} no encontrada")
                return {"success": 0, "failed": 0, "error": "Request not found"}

            # Crear notificación
            notification = NotificationTemplates.trip_assigned(
                request_id=request_id,
                pickup_address=client_request.pickup_description or "Punto de recogida",
                destination_address=client_request.destination_description or "Destino",
                fare=client_request.fare_assigned or client_request.fare_offered or 0
            )

            # Enviar notificación al conductor
            return self._send_notification(driver_id, notification)

        except Exception as e:
            logger.error(f"Error notificando viaje asignado: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}

    def notify_trip_cancelled_by_client(self, request_id: UUID, driver_id: UUID) -> Dict[str, Any]:
        """
        Notifica al conductor cuando el cliente cancela el viaje.

        Args:
            request_id: ID de la solicitud
            driver_id: ID del conductor

        Returns:
            Resultado del envío
        """
        try:
            # Crear notificación
            notification = NotificationTemplates.trip_cancelled_by_client(
                request_id=request_id)

            # Enviar notificación al conductor
            return self._send_notification(driver_id, notification)

        except Exception as e:
            logger.error(f"Error notificando cancelación por cliente: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}

    def notify_payment_received(self, request_id: UUID, driver_id: UUID, amount: float) -> Dict[str, Any]:
        """
        Notifica al conductor cuando recibe un pago.

        Args:
            request_id: ID de la solicitud
            driver_id: ID del conductor
            amount: Monto recibido

        Returns:
            Resultado del envío
        """
        try:
            # Crear notificación
            notification = NotificationTemplates.payment_received(
                request_id=request_id,
                amount=amount
            )

            # Enviar notificación al conductor
            return self._send_notification(driver_id, notification)

        except Exception as e:
            logger.error(f"Error notificando pago recibido: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}

    # ===== MÉTODOS DE NOTIFICACIONES GENERALES =====

    def notify_account_approved(self, user_id: UUID, user_type: str) -> Dict[str, Any]:
        """
        Notifica cuando se aprueba la cuenta de un usuario.

        Args:
            user_id: ID del usuario
            user_type: Tipo de usuario (CLIENT, DRIVER)

        Returns:
            Resultado del envío
        """
        try:
            # Crear notificación
            notification = NotificationTemplates.account_approved(
                user_type=user_type)

            # Enviar notificación
            return self._send_notification(user_id, notification)

        except Exception as e:
            logger.error(f"Error notificando cuenta aprobada: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}

    def notify_account_rejected(self, user_id: UUID, user_type: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Notifica cuando se rechaza la cuenta de un usuario.

        Args:
            user_id: ID del usuario
            user_type: Tipo de usuario (CLIENT, DRIVER)
            reason: Razón del rechazo

        Returns:
            Resultado del envío
        """
        try:
            # Crear notificación
            notification = NotificationTemplates.account_rejected(
                user_type=user_type,
                reason=reason
            )

            # Enviar notificación
            return self._send_notification(user_id, notification)

        except Exception as e:
            logger.error(f"Error notificando cuenta rechazada: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}

    def send_custom_notification(self, user_id: UUID, title: str, body: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Envía una notificación personalizada.

        Args:
            user_id: ID del usuario destinatario
            title: Título de la notificación
            body: Cuerpo de la notificación
            data: Datos adicionales

        Returns:
            Resultado del envío
        """
        try:
            notification = {
                "title": title,
                "body": body,
                "data": data or {}
            }

            return self._send_notification(user_id, notification)

        except Exception as e:
            logger.error(f"Error enviando notificación personalizada: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}

    # ===== MÉTODOS DE NOTIFICACIONES PARA SOLICITUDES PENDIENTES =====

    def notificar_solicitud_pendiente(self, request_id: UUID, driver_id: UUID, estimated_wait_time: int) -> Dict[str, Any]:
        """
        Notifica al conductor cuando se le asigna una solicitud pendiente.

        Args:
            request_id: ID de la solicitud pendiente
            driver_id: ID del conductor
            estimated_wait_time: Tiempo estimado de espera en minutos

        Returns:
            Resultado del envío
        """
        try:
            # Obtener información de la solicitud
            client_request = self.session.get(ClientRequest, request_id)
            if not client_request:
                logger.error(f"Solicitud {request_id} no encontrada")
                return {"success": 0, "failed": 0, "error": "Request not found"}

            # Crear notificación
            notification = NotificationTemplates.pending_request_assigned(
                request_id=request_id,
                pickup_address=client_request.pickup_description or "Punto de recogida",
                destination_address=client_request.destination_description or "Destino",
                estimated_wait_time=estimated_wait_time
            )

            # Enviar notificación al conductor
            return self._send_notification(driver_id, notification)

        except Exception as e:
            logger.error(f"Error notificando solicitud pendiente: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}

    def notificar_cambio_estado_pendiente(self, request_id: UUID, driver_id: UUID, new_status: str, status_description: str) -> Dict[str, Any]:
        """
        Notifica al conductor cuando cambia el estado de su solicitud pendiente.

        Args:
            request_id: ID de la solicitud pendiente
            driver_id: ID del conductor
            new_status: Nuevo estado de la solicitud
            status_description: Descripción del cambio de estado

        Returns:
            Resultado del envío
        """
        try:
            # Crear notificación
            notification = NotificationTemplates.pending_request_status_change(
                request_id=request_id,
                new_status=new_status,
                status_description=status_description
            )

            # Enviar notificación al conductor
            return self._send_notification(driver_id, notification)

        except Exception as e:
            logger.error(f"Error notificando cambio de estado pendiente: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}

    def notificar_solicitud_pendiente_disponible(self, request_id: UUID, driver_id: UUID) -> Dict[str, Any]:
        """
        Notifica al conductor cuando su solicitud pendiente está disponible para aceptar.

        Args:
            request_id: ID de la solicitud pendiente
            driver_id: ID del conductor

        Returns:
            Resultado del envío
        """
        try:
            # Obtener información de la solicitud
            client_request = self.session.get(ClientRequest, request_id)
            if not client_request:
                logger.error(f"Solicitud {request_id} no encontrada")
                return {"success": 0, "failed": 0, "error": "Request not found"}

            # Crear notificación
            notification = NotificationTemplates.pending_request_available(
                request_id=request_id,
                pickup_address=client_request.pickup_description or "Punto de recogida",
                destination_address=client_request.destination_description or "Destino"
            )

            # Enviar notificación al conductor
            return self._send_notification(driver_id, notification)

        except Exception as e:
            logger.error(
                f"Error notificando solicitud pendiente disponible: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}

    def notificar_solicitud_pendiente_cancelada(self, request_id: UUID, driver_id: UUID, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Notifica al conductor cuando se cancela su solicitud pendiente.

        Args:
            request_id: ID de la solicitud pendiente
            driver_id: ID del conductor
            reason: Razón de la cancelación

        Returns:
            Resultado del envío
        """
        try:
            # Crear notificación
            notification = NotificationTemplates.pending_request_cancelled(
                request_id=request_id,
                reason=reason
            )

            # Enviar notificación al conductor
            return self._send_notification(driver_id, notification)

        except Exception as e:
            logger.error(
                f"Error notificando cancelación de solicitud pendiente: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}
