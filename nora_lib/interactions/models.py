"""
Model for interactions to be sent to the interactions service.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


class EventType(str, Enum):
    """Event types for the interactions service"""

    AGENT_CONTEXT = "agent:message_context"
    THREAD_FORK = "thread_fork"


class Event(BaseModel):
    """event object to be sent to the interactions service; requires association with a message, thread or channel id"""

    type: str
    actor_id: UUID = Field(
        description="identifies actor writing the event to the interaction service"
    )
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
    data_sender_actor_id: Optional[str] = None  # agent sending the data
    virtual_thread_id: Optional[str] = None  # tool-provided thread
    tool_call_id: Optional[str] = None  # llm-provided thread
    tool_name: Optional[str] = None  # llm identifier for tool


class ReturnedAgentContextEvent(BaseModel):
    """Event format returned by interaction service for agent context events"""

    actor_id: str  # agent that saved this context
    timestamp: str
    data: AgentMessageData
    type: str


class ReturnedAgentContextMessage(BaseModel):
    """Message format returned by interaction service for search by thread"""

    message_id: str
    actor_id: str
    text: str
    ts: str
    annotated_text: Optional[str] = None
    events: Optional[List[ReturnedAgentContextEvent]] = None


class ThreadForkEventData(BaseModel):
    """Event data for a thread fork event"""

    previous_message_id: str


class ReturnedMessage(BaseModel):
    """Message format returned by interaction service for search by thread"""

    message_id: str
    actor_id: str
    text: str
    ts: str
    annotated_text: Optional[str] = None
    events: Optional[List[dict]] = None


class ThreadRelationsResponse(BaseModel):
    """Thread format returned by interaction service for thread relations in a search response"""

    thread_id: str
    events: Optional[List[Event]] = None  # events associated only with the thread
    messages: Optional[List[ReturnedMessage]] = (
        None  # includes events associated with each message
    )


def thread_message_lookup_request(message_id: str, event_type: str) -> dict:
    """retrieve messages and events for the thread associated with a message"""
    return {
        "id": message_id,
        "relations": {
            "thread": {
                "relations": {
                    "messages": {
                        "relations": {"events": {"filter": {"type": event_type}}},
                        "apply_annotations_from_actors": ["*"],
                    },
                }
            }
        },
    }
