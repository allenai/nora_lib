import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from interactions.interactions_service import InteractionsService
from interactions.models import Event, EventType


class RunState(str, Enum):
    """State of a step"""

    CREATED = "created"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class StepProgress(BaseModel):
    # A short message, e.g. "searching for $query". Recommend < 100 chars.
    short_desc: str
    # Detailed message.
    long_desc: Optional[str] = None
    # Updates on the same unit of work have the same step_id.
    step_id: UUID = uuid.uuid4()
    # Enum of possible states.
    run_state: RunState = RunState.CREATED
    # When this step was defined/created.
    created: datetime = datetime.now(timezone.utc)
    # Inner steps can be constituent to some outer step, effectively a tree.
    parent_step_id: Optional[UUID] = None
    # Populated if this step is due to an async task.
    task_id: Optional[str] = None
    # When this step started running.
    started: Optional[datetime] = None
    # Estimated finish time, if available.
    finish_est: Optional[datetime] = None
    # When this step stopped running, whether that was due to success or failure.
    finished: Optional[datetime] = None
    # Optional error message to diagnose failure.
    error_message: Optional[str] = None


class StepProgressEvent:
    """
    Wrapper around StepProgress to add event metadata and report to interactions service

    Usage:
    # Create/define a step
    find_papers_progress = StepProgressEvent(
        actor_id,
        message_id,
        StepProgress(short_desc="Find papers"),
        interactions_service
    )
    #

    # Start the step
    find_papers_progress.start()

    # Do actual work
    ...
    count_citation_progress = find_papers_progress.create_child_step(short_desc="Count citations")
    ...
    count_citation_progress.start()
    ...
    count_citation_progress.finish(is_success=True)
    ...

    # Finish the step
    find_papers_progress.finish(is_success=False, error_msg="Something went wrong")
    """

    def __init__(
        self,
        actor_id: UUID,
        message_id: str,
        step_progress: StepProgress,
        interactions_service: InteractionsService,
    ):
        self.actor_id = actor_id
        self.message_id = message_id
        self.step_progress = step_progress
        self.interactions_service = interactions_service

        # Report step creation
        self.step_progress.run_state = RunState.CREATED
        self.step_progress.created = datetime.now(timezone.utc)
        self.interactions_service.report_step_progress(self)

    def start(self):
        """Start a step"""
        self.step_progress.started = datetime.now(timezone.utc)
        self.step_progress.run_state = RunState.RUNNING
        self.interactions_service.report_step_progress(self)

    def finish(
        self, is_success: bool, error_message: Optional[str] = None
    ):
        """Finish a step whether it was successful or not"""
        self.step_progress.finished = datetime.now(timezone.utc)
        self.step_progress.run_state = (
            RunState.SUCCEEDED if is_success else RunState.FAILED
        )
        self.step_progress.error_message = error_message if error_message else None
        self.interactions_service.report_step_progress(self)

    def create_child_step(
        self, short_desc: str, long_desc: Optional[str] = None
    ) -> "StepProgressEvent":
        """Create a child step"""
        child_step_progress_event = StepProgressEvent(
            actor_id=self.actor_id,
            message_id=self.message_id,
            step_progress=StepProgress(
                parent_step_id=self.step_progress.step_id,
                short_desc=short_desc,
                long_desc=long_desc,
            ),
            interactions_service=self.interactions_service,
        )
        self.interactions_service.report_step_progress(self)
        return child_step_progress_event

    def to_event(self) -> Event:
        return Event(
            type=EventType.STEP.value,
            actor_id=self.actor_id,
            timestamp=datetime.now(),
            data=self.step_progress.model_dump(),
            message_id=self.message_id,
        )
