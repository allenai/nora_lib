"""
Model for interactions to be sent to the interactions service.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


class Event(BaseModel):
    """event object to be sent to the interactions service; requires association with a message, thread or channel id"""

    type: str
    actor_id: UUID = Field(description="identifies actor writing the event to the interaction service")
    timestamp: datetime
    text: Optional[str] = None
    data: Optional[dict] = Field(default_factory=dict)
    message_id: Optional[str] = None
    thread_id: Optional[str] = None
    channel_id: Optional[str] = None

    @field_serializer("actor_id")
    def serialize_actor_id(self, actor_id: UUID):
        return str(actor_id)

    @field_serializer("timestamp")
    def serialize_timestamp(self, timestamp: datetime):
        return timestamp.isoformat()

class AgentMessageData(BaseModel):
    """capture requests to and responses from tools within Events"""

    message_data: dict  # dict of agent/tool request/response format
    virtual_thread_id: Optional[str] = None  # tool-provided thread


class ReturnedMessage(BaseModel):
    """Message format returned by interaction service for search by thread"""

    message_id: str
    actor_id: str
    text: str
    ts: str
    annotated_text: Optional[str] = None
    events: Optional[List[dict]] = None





