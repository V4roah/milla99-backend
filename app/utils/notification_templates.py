from typing import Dict, Any, Optional
from uuid import UUID


class NotificationTemplates:
    """
    Plantillas de notificaciones push para Milla99.
    Contiene títulos, mensajes y datos para cada tipo de evento.
    """

    # ===== NOTIFICACIONES PARA CLIENTES =====

    @staticmethod
    def driver_offer_received(request_id: UUID, driver_name: str, fare: float) -> Dict[str, Any]:
        """Notificación cuando un conductor hace una oferta."""
        return {
            "title": "¡Nueva oferta de viaje!",
            "body": f"{driver_name} ha hecho una oferta de ${fare:,.0f} para tu viaje",
            "data": {
                "type": "driver_offer",
                "request_id": str(request_id),
                "action": "view_offers"
            }
        }

    @staticmethod
    def driver_assigned(request_id: UUID, driver_name: str, vehicle_info: str) -> Dict[str, Any]:
        """Notificación cuando se asigna un conductor al viaje."""
        return {
            "title": "¡Conductor asignado!",
            "body": f"{driver_name} con {vehicle_info} está en camino",
            "data": {
                "type": "driver_assigned",
                "request_id": str(request_id),
                "action": "view_trip"
            }
        }

    @staticmethod
    def driver_on_the_way(request_id: UUID, estimated_time: int) -> Dict[str, Any]:
        """Notificación cuando el conductor está en camino."""
        return {
            "title": "Conductor en camino",
            "body": f"Tu conductor llegará en aproximadamente {estimated_time} minutos",
            "data": {
                "type": "driver_on_the_way",
                "request_id": str(request_id),
                "action": "track_driver"
            }
        }

    @staticmethod
    def driver_arrived(request_id: UUID) -> Dict[str, Any]:
        """Notificación cuando el conductor llega al punto de recogida."""
        return {
            "title": "¡Tu conductor ha llegado!",
            "body": "Tu conductor está esperando en el punto de recogida",
            "data": {
                "type": "driver_arrived",
                "request_id": str(request_id),
                "action": "view_trip"
            }
        }

    @staticmethod
    def trip_started(request_id: UUID) -> Dict[str, Any]:
        """Notificación cuando inicia el viaje."""
        return {
            "title": "Viaje iniciado",
            "body": "¡Disfruta tu viaje! Tu conductor te llevará a tu destino",
            "data": {
                "type": "trip_started",
                "request_id": str(request_id),
                "action": "view_trip"
            }
        }

    @staticmethod
    def trip_finished(request_id: UUID, fare: float) -> Dict[str, Any]:
        """Notificación cuando termina el viaje."""
        return {
            "title": "Viaje finalizado",
            "body": f"Tu viaje ha terminado. Total a pagar: ${fare:,.0f}",
            "data": {
                "type": "trip_finished",
                "request_id": str(request_id),
                "action": "rate_driver"
            }
        }

    @staticmethod
    def trip_cancelled_by_driver(request_id: UUID, reason: Optional[str] = None) -> Dict[str, Any]:
        """Notificación cuando el conductor cancela el viaje."""
        message = "El conductor ha cancelado tu viaje"
        if reason:
            message += f": {reason}"

        return {
            "title": "Viaje cancelado",
            "body": message,
            "data": {
                "type": "trip_cancelled_by_driver",
                "request_id": str(request_id),
                "action": "find_new_driver"
            }
        }

    # ===== NOTIFICACIONES PARA CONDUCTORES =====

    @staticmethod
    def trip_assigned(request_id: UUID, pickup_address: str, destination_address: str, fare: float) -> Dict[str, Any]:
        """Notificación cuando se asigna un viaje al conductor."""
        return {
            "title": "¡Nuevo viaje asignado!",
            "body": f"Viaje de {pickup_address} a {destination_address} por ${fare:,.0f}",
            "data": {
                "type": "trip_assigned",
                "request_id": str(request_id),
                "action": "view_trip"
            }
        }

    @staticmethod
    def trip_cancelled_by_client(request_id: UUID) -> Dict[str, Any]:
        """Notificación cuando el cliente cancela el viaje."""
        return {
            "title": "Viaje cancelado",
            "body": "El cliente ha cancelado el viaje",
            "data": {
                "type": "trip_cancelled_by_client",
                "request_id": str(request_id),
                "action": "find_new_trip"
            }
        }

    @staticmethod
    def payment_received(request_id: UUID, amount: float) -> Dict[str, Any]:
        """Notificación cuando el conductor recibe el pago."""
        return {
            "title": "Pago recibido",
            "body": f"Has recibido ${amount:,.0f} por el viaje",
            "data": {
                "type": "payment_received",
                "request_id": str(request_id),
                "action": "view_earnings"
            }
        }

    # ===== NOTIFICACIONES GENERALES =====

    @staticmethod
    def account_approved(user_type: str) -> Dict[str, Any]:
        """Notificación cuando se aprueba la cuenta del usuario."""
        return {
            "title": "¡Cuenta aprobada!",
            "body": f"Tu cuenta de {user_type} ha sido aprobada. ¡Ya puedes usar Milla99!",
            "data": {
                "type": "account_approved",
                "user_type": user_type,
                "action": "start_using_app"
            }
        }

    @staticmethod
    def account_rejected(user_type: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Notificación cuando se rechaza la cuenta del usuario."""
        message = f"Tu cuenta de {user_type} no fue aprobada"
        if reason:
            message += f": {reason}"

        return {
            "title": "Cuenta no aprobada",
            "body": message,
            "data": {
                "type": "account_rejected",
                "user_type": user_type,
                "action": "contact_support"
            }
        }

    @staticmethod
    def maintenance_mode(message: str) -> Dict[str, Any]:
        """Notificación de mantenimiento."""
        return {
            "title": "Mantenimiento programado",
            "body": message,
            "data": {
                "type": "maintenance_mode",
                "action": "wait"
            }
        }

    @staticmethod
    def promotional_offer(title: str, message: str, offer_id: str) -> Dict[str, Any]:
        """Notificación promocional."""
        return {
            "title": title,
            "body": message,
            "data": {
                "type": "promotional_offer",
                "offer_id": offer_id,
                "action": "view_offer"
            }
        }

    # ===== NOTIFICACIONES PARA SOLICITUDES PENDIENTES =====

    @staticmethod
    def pending_request_assigned(request_id: UUID, pickup_address: str, destination_address: str, estimated_wait_time: int) -> Dict[str, Any]:
        """Notificación cuando se asigna una solicitud pendiente al conductor."""
        return {
            "title": "¡Solicitud pendiente asignada!",
            "body": f"Viaje de {pickup_address} a {destination_address}. Disponible en ~{estimated_wait_time} min",
            "data": {
                "type": "pending_request_assigned",
                "request_id": str(request_id),
                "action": "view_pending_request"
            }
        }

    @staticmethod
    def pending_request_status_change(request_id: UUID, new_status: str, status_description: str) -> Dict[str, Any]:
        """Notificación cuando cambia el estado de una solicitud pendiente."""
        return {
            "title": f"Solicitud pendiente: {new_status}",
            "body": status_description,
            "data": {
                "type": "pending_request_status_change",
                "request_id": str(request_id),
                "new_status": new_status,
                "action": "view_pending_request"
            }
        }

    @staticmethod
    def pending_request_available(request_id: UUID, pickup_address: str, destination_address: str) -> Dict[str, Any]:
        """Notificación cuando una solicitud pendiente está disponible para aceptar."""
        return {
            "title": "¡Solicitud pendiente disponible!",
            "body": f"Tu solicitud de {pickup_address} a {destination_address} está lista para aceptar",
            "data": {
                "type": "pending_request_available",
                "request_id": str(request_id),
                "action": "accept_pending_request"
            }
        }

    @staticmethod
    def pending_request_cancelled(request_id: UUID, reason: Optional[str] = None) -> Dict[str, Any]:
        """Notificación cuando se cancela una solicitud pendiente."""
        message = "Tu solicitud pendiente ha sido cancelada"
        if reason:
            message += f": {reason}"

        return {
            "title": "Solicitud pendiente cancelada",
            "body": message,
            "data": {
                "type": "pending_request_cancelled",
                "request_id": str(request_id),
                "action": "find_new_trip"
            }
        }
