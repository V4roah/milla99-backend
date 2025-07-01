from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from enum import Enum
from typing import Optional, List
import pytz

COLOMBIA_TZ = pytz.timezone("America/Bogota")


class MessageStatus(str, Enum):
    SENT = "SENT"
    DELIVERED = "DELIVERED" 
    READ = "READ"
    FAILED = "FAILED"


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_message"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    sender_id: UUID = Field(foreign_key="user.id", nullable=False)
    receiver_id: UUID = Field(foreign_key="user.id", nullable=False)
    client_request_id: UUID = Field(foreign_key="client_request.id", nullable=False)
    message: str = Field(max_length=500, nullable=False)
    status: MessageStatus = Field(default=MessageStatus.SENT, nullable=False)
    is_read: bool = Field(default=False, nullable=False)
    
    # Retención temporal - mensajes se eliminan después de 30 días
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ) + timedelta(days=30),
        nullable=False
    )
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ), 
        nullable=False
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(COLOMBIA_TZ)}
    )
    
    # Relaciones
    sender: Optional["User"] = Relationship(
        back_populates="sent_messages",
        sa_relationship_kwargs={"foreign_keys": "[ChatMessage.sender_id]"}
    )
    receiver: Optional["User"] = Relationship(
        back_populates="received_messages", 
        sa_relationship_kwargs={"foreign_keys": "[ChatMessage.receiver_id]"}
    )
    client_request: Optional["ClientRequest"] = Relationship(back_populates="chat_messages")


class ChatMessageCreate(SQLModel):
    receiver_id: UUID = Field(..., description="ID del usuario que recibe el mensaje")
    client_request_id: UUID = Field(..., description="ID de la solicitud de viaje")
    message: str = Field(..., max_length=500, description="Contenido del mensaje")


class ChatMessageRead(SQLModel):
    id: UUID
    sender_id: UUID
    receiver_id: UUID
    client_request_id: UUID
    message: str
    status: MessageStatus
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UnreadCountResponse(SQLModel):
    conversation_id: UUID = Field(..., description="ID de la conversación (client_request_id)")
    unread_count: int = Field(..., description="Número de mensajes no leídos")
    last_message: str = Field(..., description="Último mensaje recibido")
    other_user_name: str = Field(..., description="Nombre del otro usuario")
    last_message_time: datetime = Field(..., description="Hora del último mensaje")
    
    class Config:
        from_attributes = True 