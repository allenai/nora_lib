from enum import Enum
from typing import Any, Dict, Generic, Optional, TypeVar, Union
from pydantic import BaseModel, Field


R = TypeVar("R", bound=BaseModel)


class TaskStatus(str, Enum):
    """Valid statuses for async tasks."""

    STARTED = "STARTED"
    FAILED = "FAILED"  # this process had an error, but thread can continue
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"  # backing process has terminated, thread cannot continue


# Deprecated: Use TaskStatus enum instead
TASK_STATUSES = {s.name: s.value for s in TaskStatus}


class AsyncTaskState(BaseModel, Generic[R]):
    """Models the current state of an asynchronous request."""

    task_id: str = Field(
        "Identifies the long-running task so that its status and eventual result"
        "can be checked in follow-up calls."
    )
    estimated_time: str = Field(
        description="How long we expect this task to take from start to finish."
    )
    task_status: Union[TaskStatus, str] = Field(
        description="Current human-readable status of the task. Use TaskStatus enum values for standard statuses."
    )
    task_result: Optional[R] = Field(description="Final result of the task.")
    extra_state: Dict[str, Any] = Field(
        description="Any extra task-specific state can go in here as free-form JSON-serializable dictionary."
    )
