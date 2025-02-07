from enum import Enum
import uuid
from typing import Optional

from pydantic import BaseModel, Field

from nora_lib.serializers import (
    UuidWithSerializer,
    DatetimeWithSerializer,
)


class RunState(str, Enum):
    """State of a step"""

    CREATED = "created"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class StepProgress(BaseModel):
    """Data class for step progress. This goes into the `data` field in `Event`."""

    # A short message, e.g. "searching for $query". Recommend < 100 chars.
    short_desc: str
    # Detailed message.
    long_desc: Optional[str] = None
    # Updates on the same unit of work have the same step_id.
    step_id: UuidWithSerializer = Field(default_factory=uuid.uuid4)
    # Inner steps can be constituent to some outer step, effectively a tree.
    parent_step_id: Optional[UuidWithSerializer] = None
    # Populated if this step is due to an async task.
    task_id: Optional[str] = None

    # Enum of possible states.
    run_state: RunState = RunState.CREATED
    # DB timestamp when this step was defined/created.
    created_at: Optional[DatetimeWithSerializer] = None
    # When this step started running.
    started_at: Optional[DatetimeWithSerializer] = None
    # Estimated finish time, if available.
    finish_est: Optional[DatetimeWithSerializer] = None
    # When this step stopped running, whether that was due to success or failure.
    finished_at: Optional[DatetimeWithSerializer] = None
    # Error message in case of terminal step failure.
    error_message: Optional[str] = None
