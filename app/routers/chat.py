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
    cleanup_expired_messages
)
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
import traceback
from sqlalchemy.sql import select

router = APIRouter(
    prefix="/chat",
    dependencies=[Depends(get_current_user)]
)


@router.post("/send", response_model=ChatMessageRead, status_code=status.HTTP_201_CREATED, tags=["Chat"], description="""
📤 **ENVIAR MENSAJE DE CHAT**

**Propósito:** Envía un mensaje de chat a otro usuario en el contexto de una solicitud de viaje específica.

**Casos de Uso:**
- Cliente envía mensaje al conductor asignado
- Conductor envía mensaje al cliente
- Comunicación durante el viaje activo

**Validaciones:**
- Solo se pueden enviar mensajes si el viaje NO está completado (PAID)
- Solo se pueden enviar mensajes si el viaje NO está cancelado (CANCELLED)
- El usuario debe ser participante del viaje (cliente o conductor asignado)
- Máximo 500 caracteres por mensaje

**Parámetros:**
- `receiver_id`: UUID del usuario que recibe el mensaje
- `client_request_id`: UUID de la solicitud de viaje
- `message`: Contenido del mensaje (máximo 500 caracteres)

**Respuesta Exitosa (201):**
```json
{
  "id": "uuid-del-mensaje",
  "sender_id": "uuid-del-remitente",
  "receiver_id": "uuid-del-destinatario", 
  "client_request_id": "uuid-de-la-solicitud",
  "message": "Hola, ¿dónde estás?",
  "status": "SENT",
  "is_read": false,
  "created_at": "2025-01-01T10:00:00"
}
```

**Errores Posibles:**
- `400`: Viaje completado, cancelado o usuario no autorizado
- `401`: Token de autenticación inválido
- `500`: Error interno del servidor
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
💬 **OBTENER CONVERSACIÓN COMPLETA**

**Propósito:** Obtiene todos los mensajes de una conversación específica entre cliente y conductor.

**Casos de Uso:**
- Cargar historial de mensajes al abrir el chat
- Mostrar conversación completa en la UI
- Sincronizar mensajes después de reconexión

**Validaciones:**
- El usuario debe ser participante del viaje (cliente o conductor asignado)
- Si el viaje está completado (PAID), retorna lista vacía
- Los mensajes se ordenan por fecha de creación (más antiguos primero)

**Parámetros:**
- `client_request_id`: UUID de la solicitud de viaje

**Respuesta Exitosa (200):**
```json
[
  {
    "id": "uuid-del-mensaje-1",
    "sender_id": "uuid-del-cliente",
    "receiver_id": "uuid-del-conductor",
    "client_request_id": "uuid-de-la-solicitud",
    "message": "Hola conductor",
    "status": "READ",
    "is_read": true,
    "created_at": "2025-01-01T10:00:00"
  },
  {
    "id": "uuid-del-mensaje-2", 
    "sender_id": "uuid-del-conductor",
    "receiver_id": "uuid-del-cliente",
    "client_request_id": "uuid-de-la-solicitud",
    "message": "Hola cliente, estoy llegando",
    "status": "SENT",
    "is_read": false,
    "created_at": "2025-01-01T10:05:00"
  }
]
```

**Errores Posibles:**
- `400`: Usuario no autorizado para esta conversación
- `401`: Token de autenticación inválido
- `500`: Error interno del servidor
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
✅ **MARCAR MENSAJES COMO LEÍDOS**

**Propósito:** Marca todos los mensajes no leídos de una conversación como leídos.

**Casos de Uso:**
- Al abrir una conversación (marcar automáticamente)
- Al hacer scroll hasta el final de la conversación
- Al hacer clic en una conversación desde la lista

**Validaciones:**
- El usuario debe ser participante del viaje
- Solo marca mensajes donde el usuario es el receptor
- Actualiza el estado de los mensajes a "READ"

**Parámetros:**
- `client_request_id`: UUID de la solicitud de viaje

**Respuesta Exitosa (200):**
```json
{
  "message": "Se marcaron 3 mensajes como leídos",
  "count": 3
}
```

**Errores Posibles:**
- `400`: Usuario no autorizado para esta conversación
- `401`: Token de autenticación inválido
- `500`: Error interno del servidor
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
📊 **CONTADOR DE MENSAJES NO LEÍDOS**

**Propósito:** Obtiene el conteo de mensajes no leídos para todas las conversaciones del usuario.

**Casos de Uso:**
- Badge en el icono principal de chat (suma total)
- Lista de conversaciones con contadores individuales
- Notificaciones push con número total
- Actualizar UI cuando hay mensajes nuevos

**Validaciones:**
- Solo cuenta mensajes donde el usuario es el receptor
- Solo incluye conversaciones con mensajes no leídos
- Ordenado por fecha del último mensaje (más reciente primero)

**Respuesta Exitosa (200):**
```json
[
  {
    "conversation_id": "uuid-de-la-solicitud-1",
    "unread_count": 3,
    "last_message": "¿Dónde estás?",
    "other_user_name": "Juan Pérez",
    "last_message_time": "2025-01-01T10:00:00"
  },
  {
    "conversation_id": "uuid-de-la-solicitud-2", 
    "unread_count": 1,
    "last_message": "Estoy llegando",
    "other_user_name": "María García",
    "last_message_time": "2025-01-01T09:30:00"
  }
]
```

**Errores Posibles:**
- `401`: Token de autenticación inválido
- `500`: Error interno del servidor
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
