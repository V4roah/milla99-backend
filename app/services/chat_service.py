from sqlmodel import Session, select, and_, or_, func
from app.models.chat_message import ChatMessage, ChatMessageCreate, MessageStatus, UnreadCountResponse
from app.models.user import User
from app.models.client_request import ClientRequest
from datetime import datetime, timedelta
from uuid import UUID
import pytz
from typing import List, Optional

COLOMBIA_TZ = pytz.timezone("America/Bogota")


def create_chat_message(session: Session, sender_id: UUID, message_data: ChatMessageCreate) -> ChatMessage:
    """
    Crea un nuevo mensaje de chat y lo guarda en la base de datos.
    Solo permite mensajes si el ClientRequest no está en estado PAID.
    Usa el mismo patrón del listener para manejar sesiones consistentes.
    """
    # Obtener la conexión actual para crear una sesión fresca
    connection = session.bind

    # Crear sesión fresca vinculada a la misma conexión (mismo patrón del listener)
    fresh_session = Session(bind=connection)

    try:
        # Usar sesión fresca para obtener el estado más reciente
        client_request = fresh_session.get(
            ClientRequest, message_data.client_request_id)
        if not client_request:
            raise ValueError("Solicitud de viaje no encontrada")

        if client_request.status in ["PAID", "CANCELLED"]:
            # Eliminar mensajes automáticamente usando la misma sesión
            cleanup_chat_messages_for_request(fresh_session, client_request.id)
            if client_request.status == "PAID":
                raise ValueError(
                    "No se pueden enviar mensajes en un viaje completado")
            else:
                raise ValueError(
                    "No se pueden enviar mensajes en un viaje cancelado")

        # Crear mensaje usando la sesión fresca
        chat_message = ChatMessage(
            sender_id=sender_id,
            receiver_id=message_data.receiver_id,
            client_request_id=message_data.client_request_id,
            message=message_data.message,
            status=MessageStatus.SENT
        )

        fresh_session.add(chat_message)
        fresh_session.commit()
        fresh_session.refresh(chat_message)

        return chat_message

    except Exception as e:
        fresh_session.rollback()
        raise
    finally:
        fresh_session.close()


def get_conversation_messages(session: Session, client_request_id: UUID, user_id: UUID) -> List[ChatMessage]:
    """
    Obtiene todos los mensajes de una conversación específica.
    Si el ClientRequest está en estado PAID, retorna lista vacía.
    Usa el mismo patrón del listener para manejar sesiones consistentes.
    """
    print(f"🔍 DEBUG get_conversation_messages:")
    print(f"  - client_request_id: {client_request_id}")
    print(f"  - user_id: {user_id}")

    # Obtener la conexión actual para crear una sesión fresca
    connection = session.bind

    # Crear sesión fresca vinculada a la misma conexión (mismo patrón del listener)
    fresh_session = Session(bind=connection)

    try:
        # Verificar que el usuario tiene acceso a esta conversación
        client_request = fresh_session.get(ClientRequest, client_request_id)
        if not client_request:
            print(f"  ❌ ClientRequest no encontrado")
            raise ValueError("Solicitud de viaje no encontrada")

        print(f"  - ClientRequest encontrado: {client_request.id}")
        print(f"  - Estado: {client_request.status}")
        print(f"  - id_client: {client_request.id_client}")
        print(f"  - id_driver_assigned: {client_request.id_driver_assigned}")

        if client_request.id_client != user_id and client_request.id_driver_assigned != user_id:
            print(f"  ❌ Usuario no tiene acceso")
            raise ValueError("No tienes acceso a esta conversación")

        # Si el viaje está completado (PAID) o cancelado (CANCELLED), no hay mensajes (se eliminaron automáticamente)
        if client_request.status in ["PAID", "CANCELLED"]:
            print(
                f"  ✅ Estado {client_request.status} - retornando lista vacía")
            return []

        # Obtener mensajes ordenados por fecha de creación
        statement = select(ChatMessage).where(
            ChatMessage.client_request_id == client_request_id
        ).order_by(ChatMessage.created_at.asc())

        messages = fresh_session.exec(statement).all()
        print(f"  - Mensajes encontrados: {len(messages)}")

        for i, msg in enumerate(messages):
            print(
                f"    Mensaje {i+1}: {msg.message} (sender: {msg.sender_id})")

        return messages

    except Exception as e:
        fresh_session.rollback()
        raise
    finally:
        fresh_session.close()


def mark_messages_as_read(session: Session, client_request_id: UUID, user_id: UUID) -> int:
    """
    Marca todos los mensajes no leídos de una conversación como leídos
    Retorna el número de mensajes marcados como leídos
    """
    # Verificar que el usuario tiene acceso a esta conversación
    client_request = session.get(ClientRequest, client_request_id)
    if not client_request:
        raise ValueError("Solicitud de viaje no encontrada")

    if client_request.id_client != user_id and client_request.id_driver_assigned != user_id:
        raise ValueError("No tienes acceso a esta conversación")

    # Marcar mensajes como leídos
    statement = select(ChatMessage).where(
        and_(
            ChatMessage.client_request_id == client_request_id,
            ChatMessage.receiver_id == user_id,
            ChatMessage.is_read == False
        )
    )

    unread_messages = session.exec(statement).all()

    for message in unread_messages:
        message.is_read = True
        message.status = MessageStatus.READ

    session.commit()

    return len(unread_messages)


def get_unread_count(session: Session, user_id: UUID) -> List[UnreadCountResponse]:
    """
    Obtiene el conteo de mensajes no leídos para todas las conversaciones del usuario
    """
    # Obtener todas las conversaciones donde el usuario participa
    client_requests_statement = select(ClientRequest).where(
        or_(
            ClientRequest.id_client == user_id,
            ClientRequest.id_driver_assigned == user_id
        )
    )

    client_requests = session.exec(client_requests_statement).all()
    unread_counts = []

    for client_request in client_requests:
        # Obtener el último mensaje no leído
        last_message_statement = select(ChatMessage).where(
            and_(
                ChatMessage.client_request_id == client_request.id,
                ChatMessage.receiver_id == user_id,
                ChatMessage.is_read == False
            )
        ).order_by(ChatMessage.created_at.desc()).limit(1)

        last_message = session.exec(last_message_statement).first()

        if last_message:
            # Contar mensajes no leídos
            count_statement = select(func.count(ChatMessage.id)).where(
                and_(
                    ChatMessage.client_request_id == client_request.id,
                    ChatMessage.receiver_id == user_id,
                    ChatMessage.is_read == False
                )
            )

            unread_count = session.exec(count_statement).first()

            # Obtener nombre del otro usuario
            other_user_id = last_message.sender_id
            other_user = session.get(User, other_user_id)
            other_user_name = other_user.full_name if other_user else "Usuario"

            unread_counts.append(UnreadCountResponse(
                conversation_id=client_request.id,
                unread_count=unread_count,
                last_message=last_message.message,
                other_user_name=other_user_name,
                last_message_time=last_message.created_at
            ))

    return unread_counts


def cleanup_chat_messages_for_request(session: Session, client_request_id: UUID) -> int:
    """
    Elimina todos los mensajes de chat de una solicitud específica.
    Se usa cuando el ClientRequest cambia a estado PAID.
    Retorna el número de mensajes eliminados
    """
    statement = select(ChatMessage).where(
        ChatMessage.client_request_id == client_request_id
    )

    # Verificar si es una sesión de SQLModel o SQLAlchemy
    if hasattr(session, 'exec'):
        # Es una sesión de SQLModel
        messages = session.exec(statement).all()
    else:
        # Es una sesión de SQLAlchemy
        messages = session.execute(statement).scalars().all()

    count = len(messages)

    for message in messages:
        session.delete(message)

    session.commit()

    return count


def get_conversation_participants(session: Session, client_request_id: UUID) -> tuple[UUID, UUID]:
    """
    Obtiene los IDs de los participantes de una conversación (cliente y conductor)
    """
    client_request = session.get(ClientRequest, client_request_id)
    if not client_request:
        raise ValueError("Solicitud de viaje no encontrada")

    if not client_request.id_driver_assigned:
        raise ValueError("No hay conductor asignado a esta solicitud")

    return client_request.id_client, client_request.id_driver_assigned


def update_message_status(session: Session, message_id: UUID, status: MessageStatus) -> ChatMessage:
    """
    Actualiza el estado de un mensaje específico
    """
    message = session.get(ChatMessage, message_id)
    if not message:
        raise ValueError("Mensaje no encontrado")

    message.status = status
    session.commit()
    session.refresh(message)

    return message
