import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

import requests
from nora_lib.pubsub import PubsubService
from pydantic import BaseModel

from nora_lib.interactions.serializers import UuidWithSerializer, DatetimeWithSerializer
from nora_lib.interactions.interactions_service import InteractionsService
from nora_lib.interactions.models import Event, EventType


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
    step_id: UuidWithSerializer = uuid.uuid4()
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


class StepProgressReporter:
    """
    Wrapper around StepProgress to add event metadata and report to interactions service

    Usage:
    # Create/define a step
    find_papers_progress = StepProgressReporter(
        actor_id,
        message_id,
        StepProgress(short_desc="Find papers"),
        interactions_service
    )

    # Do something
    ...

    # Start the step
    find_papers_progress.start()

    # Do more things
    ...
    count_citation_progress = find_papers_progress.create_child_step(short_desc="Count citations")
    ...
    count_citation_progress.start()
    ...
    count_citation_progress.finish(is_success=True)
    ...

    # Finish the step
    find_papers_progress.finish(is_success=False, error_message="Something went wrong")

    # Alternatively, you can use this as a context.

    with StepProgressReporter(...) as spr:
        # Do something
        ...

        # You still need to start the step
        spr.start()

    # This step will be automatically finished when the context exits.
    # If an exception is raised, the step will be marked as failed
    # and the exception message will be recorded in the error_message field
    """

    def __init__(
        self,
        actor_id: UUID,
        message_id: str,
        thread_id: str,
        step_progress: StepProgress,
        interactions_service: InteractionsService,
        pubsub_service: PubsubService,
    ):
        self.actor_id = actor_id
        self.message_id = message_id
        self.thread_id = thread_id
        self.step_progress = step_progress
        self.interactions_service = interactions_service
        self.pubsub_service = pubsub_service

        # Report step creation
        self.step_progress.run_state = RunState.CREATED
        event_id_opt = self._save_progress_to_istore()

        # Use DB timestamp for created_at
        if event_id_opt:
            event = self.interactions_service.get_event(event_id_opt)
            self.step_progress.created_at = event.timestamp

            # Publish to topic
            self._publish_to_topic(event_id_opt, self.step_progress.created_at)

    def __enter__(self):
        return self

    def __exit__(self, error_type, value, traceback):
        is_success = error_type is None
        self.finish(is_success=is_success, error_message=str(value))
        return True

    def start(self) -> Optional[str]:
        """Start a step"""
        if self.step_progress.run_state in [
            RunState.RUNNING,
            RunState.SUCCEEDED,
            RunState.FAILED,
        ]:
            logging.warning(
                f"Trying to start an already started/finished step. "
                f"Doing nothing instead. Step id: {self.step_progress.step_id}. "
                f"Run state: {self.step_progress.run_state}."
            )
            return None
        
        self.step_progress.started_at = datetime.now(timezone.utc)
        self.step_progress.run_state = RunState.RUNNING
        event_id_opt = self._save_progress_to_istore()
        if event_id_opt:
            self._publish_to_topic(event_id_opt, self.step_progress.started_at)
        return event_id_opt

    def finish(
        self, is_success: bool, error_message: Optional[str] = None
    ) -> Optional[str]:
        """Finish a step whether it was successful or not"""
        if self.step_progress.run_state in [RunState.SUCCEEDED, RunState.FAILED]:
            logging.warning(
                f"Trying to finish an already finished step. "
                f"Doing nothing instead. Step id: {self.step_progress.step_id}. "
                f"Run state: {self.step_progress.run_state}."
            )
            return None
        elif self.step_progress.run_state != RunState.RUNNING:
            logging.warning(
                f"Trying to finish a step that has not been started. "
                f"Doing nothing instead. Step id: {self.step_progress.step_id}"
            )
            return None
        else:
            self.step_progress.finished_at = datetime.now(timezone.utc)
            self.step_progress.run_state = (
                RunState.SUCCEEDED if is_success else RunState.FAILED
            )
            self.step_progress.error_message = error_message if error_message else None
            event_id_opt = self._save_progress_to_istore()
            if event_id_opt:
                self._publish_to_topic(event_id_opt, self.step_progress.finished_at)
            return event_id_opt

    def create_child_step(
        self, short_desc: str, long_desc: Optional[str] = None
    ) -> "StepProgressReporter":
        """Create a child step"""
        child_step_progress_event = StepProgressReporter(
            actor_id=self.actor_id,
            message_id=self.message_id,
            thread_id=self.thread_id,
            step_progress=StepProgress(
                parent_step_id=self.step_progress.step_id,
                short_desc=short_desc,
                long_desc=long_desc,
            ),
            interactions_service=self.interactions_service,
            pubsub_service=self.pubsub_service,
        )
        return child_step_progress_event

    def _save_progress_to_istore(self) -> Optional[str]:
        """Save a step progress to the Interactions Store. Returns the event id if successful."""
        try:
            return self.interactions_service.save_event(self._to_event())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logging.warning(
                    f"Cannot find message id {self.message_id} to attach step progress to."
                )
                return None
            else:
                raise e

    def _to_event(self) -> Event:
        return Event(
            type=EventType.STEP_PROGRESS.value,
            actor_id=self.actor_id,
            timestamp=datetime.now(),
            data=self.step_progress.model_dump(),
            message_id=self.message_id,
        )

    def _publish_to_topic(self, event_id: str, timestamp: datetime):
        self.pubsub_service.publish(
            topic=f"step_progress:{self.thread_id}",
            payload={"event_id": event_id, "timestamp": timestamp.isoformat()},
        )
