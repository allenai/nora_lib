"""
Handles IO for asynchronous task-related state.
Currently just reads/writes from local disk,
the best and most robust mechanism.

A StateManager instance must be initialized with
a concrete subclass of `AsyncTaskState`, as implemented
by dependent projects.
"""

import json
import os
from typing import Generic, Optional, Type

from nora_lib.tasks.models import AsyncTaskState, R, TASK_STATUSES


class NoSuchTaskException(Exception):
    def __init__(self, task_id: str):
        self._task_id = task_id

    def __str__(self):
        return f"No record found for task {self._task_id}"


class StateManager(Generic[R]):
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

    def update_status(self, task_id: str, new_status: str) -> None:
        state = self.read_state(task_id)
        state.task_status = new_status
        self.write_state(state)

    def save_result(self, task_id: str, task_result: R) -> None:
        state = self.read_state(task_id)
        state.task_status = TASK_STATUSES["COMPLETED"]
        state.task_result = task_result
        self.write_state(state)
