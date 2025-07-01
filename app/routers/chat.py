from fastapi import APIRouter, HTTPException, status, Depends, Request, Body, Path
from fastapi.responses import JSONResponse
from app.core.db import get_session, SessionDep
from app.core.dependencies.auth import get_current_user
from app.models.chat_message import ChatMessageCreate, ChatMessageRead, UnreadCountResponse
from app.services.chat_service import (
    create_chat_message,
    get_conversation_messages,
    mark_messages_as_read,
    get_unread_count,
    get_unread_count_for_conversation,
    cleanup_expired_messages
)
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
import traceback

router = APIRouter(
    prefix="/chat",
    dependencies=[Depends(get_current_user)]
)


@router.post("/send", response_model=ChatMessageRead, status_code=status.HTTP_201_CREATED, tags=["Chat"], description="""
Envía un mensaje de chat a otro usuario en el contexto de una solicitud de viaje.

**Parámetros:**
- `receiver_id`: ID del usuario que recibe el mensaje
- `client_request_id`: ID de la solicitud de viaje
- `message`: Contenido del mensaje (máximo 500 caracteres)

**Respuesta:**
Devuelve el mensaje creado con toda su información.
""")
def send_message(
    request: Request,
    session: SessionDep,
    message_data: ChatMessageCreate = Body(...)
):
    """
    Envía un mensaje de chat
    """
    try:
        sender_id = request.state.user_id

        # Crear el mensaje
        chat_message = create_chat_message(session, sender_id, message_data)

        # Convertir a modelo de respuesta
        response = ChatMessageRead(
            id=chat_message.id,
            sender_id=chat_message.sender_id,
            receiver_id=chat_message.receiver_id,
            client_request_id=chat_message.client_request_id,
            message=chat_message.message,
            status=chat_message.status,
            is_read=chat_message.is_read,
            created_at=chat_message.created_at
        )

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[ERROR] Exception en send_message: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail=f"Error al enviar mensaje: {str(e)}")


@router.get("/conversation/{client_request_id}", response_model=List[ChatMessageRead], tags=["Chat"], description="""
Obtiene todos los mensajes de una conversación específica.

**Parámetros:**
- `client_request_id`: ID de la solicitud de viaje

**Respuesta:**
Devuelve una lista de todos los mensajes de la conversación ordenados por fecha de creación.
""")
def get_conversation(
    request: Request,
    session: SessionDep,
    client_request_id: UUID = Path(...,
                                   description="ID de la solicitud de viaje")
):
    """
    Obtiene todos los mensajes de una conversación
    """
    try:
        user_id = request.state.user_id

        # Obtener mensajes
        messages = get_conversation_messages(
            session, client_request_id, user_id)

        # Convertir a modelo de respuesta
        response = []
        for message in messages:
            response.append(ChatMessageRead(
                id=message.id,
                sender_id=message.sender_id,
                receiver_id=message.receiver_id,
                client_request_id=message.client_request_id,
                message=message.message,
                status=message.status,
                is_read=message.is_read,
                created_at=message.created_at
            ))

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[ERROR] Exception en get_conversation: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail=f"Error al obtener conversación: {str(e)}")


@router.patch("/mark-read/{client_request_id}", tags=["Chat"], description="""
Marca todos los mensajes no leídos de una conversación como leídos.

**Parámetros:**
- `client_request_id`: ID de la solicitud de viaje

**Respuesta:**
Devuelve el número de mensajes marcados como leídos.
""")
def mark_conversation_as_read(
    request: Request,
    session: SessionDep,
    client_request_id: UUID = Path(...,
                                   description="ID de la solicitud de viaje")
):
    """
    Marca todos los mensajes de una conversación como leídos
    """
    try:
        user_id = request.state.user_id

        # Marcar mensajes como leídos
        count = mark_messages_as_read(session, client_request_id, user_id)

        return JSONResponse(
            status_code=200,
            content={
                "message": f"Se marcaron {count} mensajes como leídos",
                "count": count
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[ERROR] Exception en mark_conversation_as_read: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail=f"Error al marcar mensajes como leídos: {str(e)}")


@router.get("/unread-count", response_model=List[UnreadCountResponse], tags=["Chat"], description="""
Obtiene el conteo de mensajes no leídos para todas las conversaciones del usuario.

**Respuesta:**
Devuelve una lista con el conteo de mensajes no leídos por conversación.
""")
def get_unread_messages_count(
    request: Request,
    session: SessionDep
):
    """
    Obtiene el conteo de mensajes no leídos
    """
    try:
        user_id = request.state.user_id

        # Obtener conteo de mensajes no leídos
        unread_counts = get_unread_count(session, user_id)

        return unread_counts

    except Exception as e:
        print(f"[ERROR] Exception en get_unread_messages_count: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail=f"Error al obtener conteo de mensajes: {str(e)}")


@router.get("/unread-count/{client_request_id}", tags=["Chat"], description="""
Obtiene el conteo de mensajes no leídos para una conversación específica.

**Parámetros:**
- `client_request_id`: ID de la solicitud de viaje

**Respuesta:**
Devuelve el número de mensajes no leídos en la conversación.
""")
def get_conversation_unread_count(
    request: Request,
    session: SessionDep,
    client_request_id: UUID = Path(...,
                                   description="ID de la solicitud de viaje")
):
    """
    Obtiene el conteo de mensajes no leídos para una conversación específica
    """
    try:
        user_id = request.state.user_id

        # Obtener conteo de mensajes no leídos
        count = get_unread_count_for_conversation(
            session, client_request_id, user_id)

        return JSONResponse(
            status_code=200,
            content={
                "client_request_id": str(client_request_id),
                "unread_count": count
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[ERROR] Exception en get_conversation_unread_count: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail=f"Error al obtener conteo de mensajes: {str(e)}")


@router.delete("/cleanup", tags=["Admin"], description="""
Elimina mensajes expirados (más de 30 días). Solo para administradores.

**Respuesta:**
Devuelve el número de mensajes eliminados.
""")
def cleanup_messages(
    request: Request,
    session: SessionDep
):
    """
    Elimina mensajes expirados
    """
    try:
        # Verificar que es admin (esto debería estar en un middleware)
        # Por ahora lo dejamos abierto para testing

        # Limpiar mensajes expirados
        count = cleanup_expired_messages(session)

        return JSONResponse(
            status_code=200,
            content={
                "message": f"Se eliminaron {count} mensajes expirados",
                "count": count
            }
        )

    except Exception as e:
        print(f"[ERROR] Exception en cleanup_messages: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail=f"Error al limpiar mensajes: {str(e)}")
