from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from nora_lib.interactions.interactions_service import InteractionsService
from nora_lib.interactions.models import (
    ReturnedMessage,
    ReturnedAgentContextMessage,
    ReturnedAgentContextEvent,
    EventType,
    AgentMessageData,
    Event,
)
from nora_lib.context.models import WrappedTaskObject


class ContextService:
    """
    Save and retrieve task agent context from interaction store
    """

    def __init__(
        self,
        agent_actor_id: str,  # uuid representing this agent in interaction store
        interactions_base_url: str,
        interactions_bearer_token: Optional[str],
        timeout: int = 30,
    ):
        self.interactions_service = self._get_interactions_service(
            interactions_base_url, interactions_bearer_token, timeout
        )
        self.agent_actor_id = agent_actor_id

    def _get_interactions_service(self, url, token, timeout) -> InteractionsService:
        return InteractionsService(url, timeout, token)

    def fetch_context(
        self, request: WrappedTaskObject
    ) -> List[ReturnedAgentContextMessage]:
        message_id = request.message_id

        returned_messages: List[ReturnedMessage] = (
            self.interactions_service.fetch_messages_and_events_for_forked_thread(
                message_id, EventType.AGENT_CONTEXT
            )
        )

        messages_with_filtered_events: List[ReturnedAgentContextMessage] = []
        for message in returned_messages:
            events_saved_by_this_agent: List[ReturnedAgentContextEvent] = []
            if message.events:
                for event in message.events:
                    context_event = ReturnedAgentContextEvent.model_validate(event)
                    if context_event.actor_id == self.agent_actor_id:
                        events_saved_by_this_agent.append(context_event)

                events_saved_by_this_agent.sort(
                    key=lambda event: datetime.fromisoformat(event.timestamp)
                )

            updated_message = ReturnedAgentContextMessage(
                message_id=message.message_id,
                actor_id=message.actor_id,
                text=message.text,
                ts=message.ts,
                annotated_text=message.annotated_text,
                events=events_saved_by_this_agent,
            )

            messages_with_filtered_events.append(updated_message)

        return messages_with_filtered_events

    def save_context(self, event_data: WrappedTaskObject):
        agent_data = AgentMessageData(
            message_data=event_data.model_dump(),
            data_sender_actor_id=event_data.sender_actor_id,
            virtual_thread_id=event_data.virtual_thread_id,
        )
        event = Event(
            type=EventType.AGENT_CONTEXT,
            actor_id=UUID(self.agent_actor_id),
            timestamp=datetime.now(timezone.utc),
            data=agent_data.model_dump(),
            message_id=event_data.message_id,
        )

        self.interactions_service.save_event(event)
