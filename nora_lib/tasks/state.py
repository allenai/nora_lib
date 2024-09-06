"""
Handles IO for asynchronous task-related state.

A StateManager instance must be initialized with
a concrete subclass of `AsyncTaskState`, as implemented
by dependent projects.
"""

import json
import logging
import os
from uuid import UUID
from datetime import datetime, timezone
from typing import Generic, Optional, Type, Any
from abc import ABC, abstractmethod
from pydantic import BaseModel

from nora_lib.tasks.models import AsyncTaskState, R, TASK_STATUSES
from nora_lib.interactions.interactions_service import InteractionsService
from nora_lib.interactions.models import Event, ReturnedEvent
from nora_lib.pubsub import PubsubService
from nora_lib.context.agent_context import AgentContext

TASK_STATE_CHANGE_TOPIC = "istore:event:task_state"


class NoSuchTaskException(Exception):
    def __init__(self, task_id: str):
        self._task_id = task_id

    def __str__(self):
        return f"No record found for task {self._task_id}"


class IStateManager(ABC, Generic[R]):
    @abstractmethod
    def read_state(self, task_id: str) -> AsyncTaskState[R]:
        pass

    @abstractmethod
    def write_state(self, state: AsyncTaskState[R]) -> None:
        pass

    def update_status(self, task_id: str, new_status: str) -> None:
        state = self.read_state(task_id)
        state.task_status = new_status
        self.write_state(state)

    def save_result(self, task_id: str, task_result: R) -> None:
        state = self.read_state(task_id)
        state.task_status = TASK_STATUSES["COMPLETED"]
        state.task_result = task_result
        self.write_state(state)


class StateManager(IStateManager[R]):
    """
    Stores task state on local disk
    """

    def __init__(self, task_state_class: Type[AsyncTaskState[R]], state_dir) -> None:
        self._task_state_class = task_state_class
        self._state_dir = state_dir

    def read_state(self, task_id: str) -> AsyncTaskState[R]:
        task_state_path = os.path.join(self._state_dir, f"{task_id}.json")
        if not os.path.isfile(task_state_path):
            raise NoSuchTaskException(task_id)

        with open(task_state_path, "r") as f:
            return self._task_state_class(**json.loads(f.read()))

    def write_state(self, state: AsyncTaskState[R]) -> None:
        task_state_path = os.path.join(self._state_dir, f"{state.task_id}.json")
        with open(task_state_path, "w") as f:
            json.dump(state.model_dump(), f)


class TaskStateFetchException(Exception):
    def __init__(self, message: str):
        super().__init__(message)


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
