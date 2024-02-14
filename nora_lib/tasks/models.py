from typing import Any, Dict, Generic, Optional, TypeVar
from pydantic import BaseModel, Field


R = TypeVar("R", bound=BaseModel)


TASK_STATUSES = dict(STARTED="STARTED", FAILED="FAILED", COMPLETED="COMPLETED")


class AsyncTaskState(BaseModel, Generic[R]):
    """Models the current state of an asynchronous request."""

    task_id: str = Field(
        "Identifies the long-running task so that its status and eventual result"
        "can be checked in follow-up calls."
    )
    estimated_time: str = Field(
        description="How long we expect this task to take from start to finish."
    )
    task_status: str = Field(description="Current human-readable status of the task.")
    task_result: Optional[R] = Field(description="Final result of the task.")
    extra_state: Dict[str, Any] = Field(
        description="Any extra task-specific state can go in here as free-form JSON-serializable dictionary."
    )
