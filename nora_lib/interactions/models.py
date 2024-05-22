"""
Model for interactions to be sent to the interactions service.
"""

import json
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, ConfigDict


class Surface(str, Enum):
    SLACK = "Slack"
    WEB = "NoraWebapp"


class Annotation(BaseModel):
    # Need this config to stringify numeric values in attributes.
    # Otherwise, we'll get 'Input should be a valid string' error.
    model_config = ConfigDict(coerce_numbers_to_str=True)

    tag: str
    span: Tuple[int, int]
    attributes: Optional[Dict[str, str]] = None


class AnnotationBatch(BaseModel):
    actor_id: UUID
    message_id: str
    annotations: List[Annotation]

    @field_serializer("actor_id")
    def serialize_actor_id(self, actor_id: UUID):
        return str(actor_id)


class Message(BaseModel):
    message_id: str
    actor_id: UUID
    text: str
    thread_id: Optional[str]
    channel_id: str
    surface: Surface
    ts: datetime
    annotations: List[Annotation] = Field(default_factory=list)

    @field_serializer("actor_id")
    def serialize_actor_id(self, actor_id: UUID):
        return str(actor_id)

    @field_serializer("ts")
    def serialize_ts(self, ts: datetime):
        return ts.isoformat()


class Event(BaseModel):
    """event object to be sent to the interactions service; requires association with a message, thread or channel id"""

    type: str
    actor_id: UUID = Field(
        description="identifies actor writing the event to the interaction service"
    )
    timestamp: datetime
    text: Optional[str] = None
    data: dict = Field(default_factory=dict)
    message_id: Optional[str] = None
    thread_id: Optional[str] = None
    channel_id: Optional[str] = None

    @field_serializer("actor_id")
    def serialize_actor_id(self, actor_id: UUID):
        return str(actor_id)

    @field_serializer("timestamp")
    def serialize_timestamp(self, timestamp: datetime):
        return timestamp.isoformat()


class ReturnedMessage(BaseModel):
    """Message format returned by interaction service"""

    actor_id: UUID
    text: str
    ts: datetime
    message_id: Optional[str] = None
    annotated_text: Optional[str] = None
    events: List[Event] = Field(default_factory=list)
    thread_id: Optional[str] = None
    channel_id: Optional[str] = None
    annotations: List[Annotation] = Field(default_factory=list)

    @classmethod
    def from_event(cls, event: Event) -> "ReturnedMessage":
        """Convert an event to a message"""
        return ReturnedMessage(
            actor_id=event.actor_id,
            text=json.dumps(event.data),
            ts=event.timestamp,
            message_id=event.message_id,
        )


class AgentMessageData(BaseModel):
    """capture requests to and responses from tools within Events"""

    message_data: dict  # dict of agent/tool request/response format
    data_sender_actor_id: Optional[str] = None  # agent sending the data
    virtual_thread_id: Optional[str] = None  # tool-provided thread
    tool_call_id: Optional[str] = None  # llm-provided thread
    tool_name: Optional[str] = None  # llm identifier for tool


class ReturnedAgentContextEvent(BaseModel):
    """Event format returned by interaction service for agent context events"""

    actor_id: UUID  # agent that saved this context
    timestamp: datetime
    data: AgentMessageData
    type: str


class ReturnedAgentContextMessage(BaseModel):
    """Message format returned by interaction service for search by thread"""

    message_id: str
    actor_id: UUID
    text: str
    ts: str
    annotated_text: Optional[str] = None
    events: List[ReturnedAgentContextEvent] = Field(default_factory=list)


class ThreadRelationsResponse(BaseModel):
    """Thread format returned by interaction service for thread relations in a search response"""

    thread_id: str
    events: List[Event] = Field(
        default_factory=list
    )  # events associated only with the thread
    messages: List[ReturnedMessage] = Field(
        default_factory=list
    )  # includes events associated with each message


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
