from typing import Dict, Any

from nora_lib.interactions.models import Surface
from pydantic import BaseModel, Field


class MessageAgentContext(BaseModel):
    """
    Identifiers for the triggering user message
    """

    message_id: str
    thread_id: str
    channel_id: str
    surface: Surface


class PubsubAgentContext(BaseModel):
    """
    The pubsub namespace in which the Handler is running
    """

    base_url: str
    namespace: str


class ToolConfigAgentContext(BaseModel):
    """
    The name of the tool config being used by the handler (handler-best-quality, low-cost, etc.)
    """

    config_name: str
    overrides: Dict[str, Any] = Field(default_factory=dict)


class AgentContext(BaseModel):
    """
    Information that needs to be passed from the Handler to tool agents
    """

    message: MessageAgentContext
    pubsub: PubsubAgentContext
    tool_config: ToolConfigAgentContext
