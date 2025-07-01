import socketio
import json
from datetime import datetime
from app.services.chat_service import create_chat_message, get_unread_count_for_conversation
from app.models.chat_message import ChatMessageCreate, MessageStatus
from app.core.db import get_session
from uuid import UUID

# Configura Redis como message manager
mgr = socketio.AsyncRedisManager('redis://localhost:6379/0')
# sio = socketio.AsyncServer(
#     async_mode='asgi',
#     client_manager=mgr,
#     cors_allowed_origins='*'
# )
sio = socketio.AsyncServer(async_mode='asgi')


@sio.event
async def connect(sid, environ):
    print(f'Cliente conectado: {sid}')


@sio.event
async def disconnect(sid):
    print(f'Cliente desconectado: {sid}')
    await sio.emit('driver_disconnected', {'id_socket': sid})


@sio.event
async def message(sid, data):
    print(f'Datos del cliente en socket: {sid}: {data}')
    await sio.emit(
        'new_message',
        data,
        to=sid
    )


@sio.event
async def change_driver_position(sid, data):
    # Si data es string, conviértelo a dict
    if isinstance(data, str):
        data = json.loads(data)
    print(f'Emitio nueva posicion en socket: {sid}: {data}')
    await sio.emit(
        'new_driver_position',
        {
            'id_socket': sid,
            'id': data['id'],
            'lat': data['lat'],
            'lng': data['lng']
        }
    )


@sio.event
async def new_client_request(sid, data):
    # Si data es string, conviértelo a dict
    if isinstance(data, str):
        data = json.loads(data)
    print(
        f'El cliente emitio una nueva solicitud de servicio en socket: {sid}: {data}')
    await sio.emit(
        'created_client_request',
        {
            'id_socket': sid,
            'id_client_request': data['id_client_request'],
        }
    )


@sio.event
async def new_driver_offer(sid, data):
    # Si data es string, conviértelo a dict
    if isinstance(data, str):
        data = json.loads(data)
    print(
        f'El conductor emitio una nueva oferta de servicio en socket: {sid}: {data}')
    await sio.emit(
        f'created_driver_offer/{data["id_client_request"]}',
        {
            'id_socket': sid
        }
    )


@sio.event
async def new_driver_assigned(sid, data):
    # Si data es string, conviértelo a dict
    if isinstance(data, str):
        data = json.loads(data)
    print(
        f'El cliente emitio una nueva asignacion de conductor en socket: {sid}: {data}')
    await sio.emit(
        f'driver_assigned/{data["id_driver"]}',
        {
            'id_socket': sid,
            "id_client_request": data["id_client_request"]
        }
    )


@sio.event
async def trip_change_driver_position(sid, data):
    # Si data es string, conviértelo a dict
    if isinstance(data, str):
        data = json.loads(data)
    print(f'El conductor actualizo su posicion en el socket: {sid}: {data}')
    await sio.emit(
        f'trip_new_driver_position/{data["id_client"]}',
        {
            'id_socket': sid,
            'lat': data['lat'],
            'lng': data['lng']
        }
    )


@sio.event
async def update_status_trip(sid, data):
    # Si data es string, conviértelo a dict
    if isinstance(data, str):
        data = json.loads(data)
    print(f'Se actualizo el estado de la viaje en el socket: {sid}: {data}')
    await sio.emit(
        f'new_status_trip/{data["id_client_request"]}',
        {
            'id_socket': sid,
            'status': data['status'],
            'id_client_request': data['id_client_request']
        }
    )


@sio.event
async def client_to_driver_message(sid, data):
    """
    Cliente envía mensaje al conductor con persistencia en BD y notificaciones.
    - Evento: client_to_driver_message
    - El conductor debe escuchar: client_message/{id_driver} (reemplaza {id_driver} por el ID real del conductor)
    - JSON de ejemplo para enviar:
        {
            "id_driver": "uuid-del-conductor",
            "message": "te demoras mucho?",
            "client_id": "uuid-del-cliente",
            "client_name": "Cliente Ejemplo",
            "id_client_request": "uuid-de-la-solicitud"
        }
    - El conductor recibe:
        {
            "id_socket": "g4FrvjlHyMEWc71EAAAB",
            "message": "te demoras mucho?",
            "client_id": "uuid-del-cliente",
            "client_name": "Cliente Ejemplo",
            "id_client_request": "uuid-de-la-solicitud",
            "timestamp": "2025-06-06T16:10:43.170016",
            "unread_count": 3,
            "message_id": "uuid-del-mensaje"
        }
    """
    # Si data es string, conviértelo a dict
    if isinstance(data, str):
        data = json.loads(data)
    print(f'Mensaje del cliente al conductor: {sid}: {data}')

    try:
        # Guardar mensaje en base de datos
        session = next(get_session())
        message_data = ChatMessageCreate(
            receiver_id=UUID(data["id_driver"]),
            client_request_id=UUID(data["id_client_request"]),
            message=data['message']
        )

        chat_message = create_chat_message(
            session, UUID(data["client_id"]), message_data)

        # Obtener conteo de mensajes no leídos
        unread_count = get_unread_count_for_conversation(
            session,
            UUID(data["id_client_request"]),
            UUID(data["id_driver"])
        )

        # Emitir el mensaje al conductor específico con información adicional
        await sio.emit(
            f'client_message/{data["id_driver"]}',
            {
                'id_socket': sid,
                'message': data['message'],
                'client_id': data['client_id'],
                'client_name': data['client_name'],
                'id_client_request': data['id_client_request'],
                'timestamp': datetime.utcnow().isoformat(),
                'unread_count': unread_count,
                'message_id': str(chat_message.id)
            }
        )

        # Emitir notificación de mensaje no leído
        await sio.emit(
            f'unread_message_notification/{data["id_driver"]}',
            {
                'conversation_id': data['id_client_request'],
                'unread_count': unread_count,
                'last_message': data['message'],
                'other_user_name': data['client_name'],
                'last_message_time': datetime.utcnow().isoformat()
            }
        )

    except Exception as e:
        print(f"Error al procesar mensaje del cliente: {str(e)}")
        # Emitir mensaje de error
        await sio.emit(
            f'client_message/{data["id_driver"]}',
            {
                'id_socket': sid,
                'message': data['message'],
                'client_id': data['client_id'],
                'client_name': data['client_name'],
                'id_client_request': data['id_client_request'],
                'timestamp': datetime.utcnow().isoformat(),
                'error': 'Error al guardar mensaje'
            }
        )


@sio.event
async def driver_to_client_message(sid, data):
    """
    Conductor envía mensaje al cliente con persistencia en BD y notificaciones.
    - Evento: driver_to_client_message
    - El cliente debe escuchar: driver_message/{id_client} (reemplaza {id_client} por el ID real del cliente)
    - JSON de ejemplo para enviar:
        {
            "id_client": "uuid-del-cliente",
            "message": "estoy a 5 minutos",
            "driver_id": "uuid-del-conductor",
            "driver_name": "Conductor Ejemplo",
            "id_client_request": "uuid-de-la-solicitud"
        }
    - El cliente recibe:
        {
            "id_socket": "JQ51eDnz2gxBGz7eAAAD",
            "message": "estoy a 5 minutos",
            "driver_id": "uuid-del-conductor",
            "driver_name": "Conductor Ejemplo",
            "id_client_request": "uuid-de-la-solicitud",
            "timestamp": "2025-06-06T16:13:14.784023",
            "unread_count": 2,
            "message_id": "uuid-del-mensaje"
        }
    """
    # Si data es string, conviértelo a dict
    if isinstance(data, str):
        data = json.loads(data)
    print(f'Mensaje del conductor al cliente: {sid}: {data}')

    try:
        # Guardar mensaje en base de datos
        session = next(get_session())
        message_data = ChatMessageCreate(
            receiver_id=UUID(data["id_client"]),
            client_request_id=UUID(data["id_client_request"]),
            message=data['message']
        )

        chat_message = create_chat_message(
            session, UUID(data["driver_id"]), message_data)

        # Obtener conteo de mensajes no leídos
        unread_count = get_unread_count_for_conversation(
            session,
            UUID(data["id_client_request"]),
            UUID(data["id_client"])
        )

        # Emitir el mensaje al cliente específico con información adicional
        await sio.emit(
            f'driver_message/{data["id_client"]}',
            {
                'id_socket': sid,
                'message': data['message'],
                'driver_id': data['driver_id'],
                'driver_name': data['driver_name'],
                'id_client_request': data['id_client_request'],
                'timestamp': datetime.utcnow().isoformat(),
                'unread_count': unread_count,
                'message_id': str(chat_message.id)
            }
        )

        # Emitir notificación de mensaje no leído
        await sio.emit(
            f'unread_message_notification/{data["id_client"]}',
            {
                'conversation_id': data['id_client_request'],
                'unread_count': unread_count,
                'last_message': data['message'],
                'other_user_name': data['driver_name'],
                'last_message_time': datetime.utcnow().isoformat()
            }
        )

    except Exception as e:
        print(f"Error al procesar mensaje del conductor: {str(e)}")
        # Emitir mensaje de error
        await sio.emit(
            f'driver_message/{data["id_client"]}',
            {
                'id_socket': sid,
                'message': data['message'],
                'driver_id': data['driver_id'],
                'driver_name': data['driver_name'],
                'id_client_request': data['id_client_request'],
                'timestamp': datetime.utcnow().isoformat(),
                'error': 'Error al guardar mensaje'
            }
        )
