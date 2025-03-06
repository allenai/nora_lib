from typing import Optional
from uuid import UUID

from nora_lib.impl.interactions.models import Surface
from pydantic import BaseModel


class MessageAgentContext(BaseModel):
    """
    Identifiers for the triggering message
    """

    message_id: str
    thread_id: str
    channel_id: str
    actor_id: UUID
    surface: Surface


class PubsubAgentContext(BaseModel):
    """
    The pubsub namespace in which the Handler is running
    """

    base_url: str
    namespace: str


class ToolConfigAgentContext(BaseModel):
    """
    The name of the tool config being used by the handler (dev, prod, demo, etc.)
    """

    env: str


class AgentContext(BaseModel):
    """
    Information that needs to be passed from the Handler to tool agents
    """

    message: MessageAgentContext
    pubsub: PubsubAgentContext
    tool_config: ToolConfigAgentContext
    step_id: Optional[str] = None
