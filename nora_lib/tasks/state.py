"""
Handles IO for asynchronous task-related state.

A StateManager instance must be initialized with
a concrete subclass of `AsyncTaskState`, as implemented
by dependent projects.
"""

import json
import os
from uuid import UUID
from datetime import datetime, timezone
from typing import Generic, Optional, Type, Any
from abc import ABC, abstractmethod

from nora_lib.tasks.models import AsyncTaskState, R, TASK_STATUSES
from nora_lib.interactions.interactions_service import InteractionsService
from nora_lib.interactions.models import Event


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
        self, agent_name: str, actor_id: UUID, interactions_service: InteractionsService
    ):
        """
        :param agent_name: Used to form the event type that will hold the task state in the interactions store
        :param actor_id: Associated with the events written to the interactions store
        :param interactions_service:
        """
        self.agent_name = agent_name
        self.actor_id = actor_id
        self.interactions_service = interactions_service

    def for_message(self, message_id: str) -> IStateManager[R]:
        return RemoteStateManager(
            self.agent_name, self.actor_id, self.interactions_service, message_id
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
                    latest_timestamp and event.created_at > latest_timestamp
                ):
                    latest_state = state
                    latest_timestamp = event.created_at

        if not latest_state:
            raise NoSuchTaskException(task_id)
        return latest_state

    def write_state(self, state: AsyncTaskState[R]) -> None:
        event = Event(
            type=RemoteStateManager._TASK_STATE_EVENT_TYPE.format(self.agent_name),
            actor_id=self.actor_id,
            message_id=self.message_id,
            data=state.model_dump(),
        )
        self.interactions_service.save_event(event)
