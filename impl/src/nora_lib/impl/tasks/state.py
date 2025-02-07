"""
Handles IO for asynchronous task-related state.

A StateManager instance must be initialized with
a concrete subclass of `AsyncTaskState`, as implemented
by dependent projects.
"""

import logging
from uuid import UUID
from datetime import datetime, timezone
from typing import Optional, Any
from pydantic import BaseModel

from nora_lib.tasks.models import AsyncTaskState, R
from nora_lib.tasks.state import (
    IStateManager,
    TaskStateFetchException,
    NoSuchTaskException,
)
from nora_lib.impl.interactions.interactions_service import InteractionsService
from nora_lib.impl.interactions.models import Event, ReturnedEvent
from nora_lib.impl.pubsub import PubsubService
from nora_lib.impl.context.agent_context import AgentContext

TASK_STATE_CHANGE_TOPIC = "istore:event:task_state"


class RemoteStateManagerFactory:
    """
    Stores task state in the interaction store
    """

    def __init__(
        self,
        agent_name: str,
        actor_id: UUID,
        interactions_service: InteractionsService,
        pubsub_service: PubsubService,
    ):
        """
        :param agent_name: Used to form the event type that will hold the task state in the interactions store
        :param actor_id: Associated with the events written to the interactions store
        :param interactions_service:
        """
        self.agent_name = agent_name
        self.actor_id = actor_id
        self.interactions_service = interactions_service
        self.pubsub_service = pubsub_service

    def for_message(self, message_id: str) -> IStateManager[R]:
        return RemoteStateManager(
            self.agent_name,
            self.actor_id,
            self.interactions_service,
            self.pubsub_service,
            message_id,
        )

    def for_agent_context(self, context: AgentContext) -> IStateManager[R]:
        return RemoteStateManager(
            self.agent_name,
            self.actor_id,
            self.interactions_service,
            PubsubService(context.pubsub.base_url, context.pubsub.namespace),
            context.message.message_id,
        )


class RemoteStateManager(IStateManager[R]):
    """
    Stores task state in the interaction store
    """

    _TASK_STATE_EVENT_TYPE = "agent:{}:task_state"

    def __init__(
        self,
        agent_name: str,
        actor_id: UUID,
        interactions_service: InteractionsService,
        pubsub_service: PubsubService,
        message_id: str,
    ):
        """
        :param agent_name: Agent that saved the task
        :param actor_id: ID for the agent (ignored when reading)
        :param message_id: The message that initiated the request for task status
        """
        self.agent_name = agent_name
        self.actor_id = actor_id
        self.message_id = message_id
        self.interactions_service = interactions_service
        self.pubsub_service = pubsub_service

    def read_state(self, task_id: str) -> AsyncTaskState[R]:
        event_type = RemoteStateManager._TASK_STATE_EVENT_TYPE.format(self.agent_name)
        response = (
            self.interactions_service.fetch_thread_messages_and_events_for_message(
                self.message_id, [event_type]
            )
        )
        latest_state: Optional[AsyncTaskState[R]] = None
        latest_timestamp = None
        for msg in response.messages or []:
            for event in msg.events or []:
                try:
                    state = AsyncTaskState[Any].model_validate(event.data)
                except Exception as e:
                    # Event json blob has unexpected format
                    raise TaskStateFetchException(
                        f"Event of type {event_type} for message {self.message_id} does not deserialize to AsyncTaskState: {e}"
                    )
                if state.task_id != task_id:
                    continue
                if latest_state is None or (
                    latest_timestamp and event.timestamp > latest_timestamp
                ):
                    latest_state = state
                    latest_timestamp = event.timestamp

        if not latest_state:
            raise NoSuchTaskException(task_id)
        return latest_state

    def write_state(self, state: AsyncTaskState[R]) -> None:
        event_type = RemoteStateManager._TASK_STATE_EVENT_TYPE.format(self.agent_name)
        event = Event(
            type=event_type,
            actor_id=self.actor_id,
            timestamp=datetime.now(tz=timezone.utc),
            message_id=self.message_id,
            data=state.model_dump(),
        )
        event_id = self.interactions_service.save_event(event)
        returned_event = ReturnedEvent(
            event_id=event_id,
            type=event.type,
            actor_id=event.actor_id,
            message_id=event.message_id,
            timestamp=event.timestamp,
        )
        payload = TaskStateChangeNotification(
            agent=self.agent_name, event=returned_event
        )
        try:
            self.pubsub_service.publish(TASK_STATE_CHANGE_TOPIC, payload.model_dump())
        except Exception as e:
            logging.exception(
                f"Failed to publish event to pubsub topic {TASK_STATE_CHANGE_TOPIC} at {self.pubsub_service.base_url}"
            )


class TaskStateChangeNotification(BaseModel):
    agent: str
    event: ReturnedEvent
