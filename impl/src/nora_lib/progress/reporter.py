from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime, timezone

from nora_lib.progress.models import StepProgress, RunState


class StepProgressWriter(ABC):
    """Writes step progress to a store or service"""

    def write(self, step_progress: StepProgress):
        """Default no-op implementation"""
        pass


class StepProgressReporter:
    """
    Tracks the lifecycle of a task and records incremental progress to some external store

    Usage:
    # Create/define a step
    find_papers_progress = StepProgressReporter(...)
    find_papers_progress.create()

    # Do something
    ...

    # Start the step
    find_papers_progress.start()

    # Describe a part of the work of that outer step as a child step.
    ...
    count_citation_progress = find_papers_progress.create_child_step(short_desc="Count citations")
    count_citation_progress.create()
    ...
    count_citation_progress.start()
    ...
    count_citation_progress.finish(is_success=True)
    ...

    # Finish the outer step
    find_papers_progress.finish(is_success=False, error_message="Something went wrong")

    # Alternatively, you can use this as a context. Step state transitions are managed for you,
    # so you should NOT call any of the create/start/finish methods.

    with StepProgressReporter(...) as spr:
        # Do something
        ...

    # This step will be automatically created, started, and finished when the context exits.
    # If an exception is raised, the step will be marked as failed
    # and the exception message will be recorded in the error_message field
    """

    def __init__(self, step_progress: StepProgress, writer: StepProgressWriter):
        self.step_progress = step_progress
        self.writer = writer

    def __enter__(self):
        if self.step_progress.created_at is None:
            self.create()
        self.start()
        return self

    def __exit__(self, error_type, value, traceback):
        is_success = error_type is None
        self.finish(is_success=is_success, error_message=str(value))
        return True

    def create(self):
        """Create a step, but don't start it yet. This is useful for defining plans."""
        if self.step_progress.run_state in [
            RunState.RUNNING,
            RunState.SUCCEEDED,
            RunState.FAILED,
        ]:
            return

        self.step_progress.run_state = RunState.CREATED
        self.step_progress.created_at = datetime.now(timezone.utc)
        self.writer.write(self.step_progress)

    def start(self):
        """Start a step"""
        if self.step_progress.run_state in [
            RunState.RUNNING,
            RunState.SUCCEEDED,
            RunState.FAILED,
        ]:
            return

        self.step_progress.started_at = datetime.now(timezone.utc)
        self.step_progress.run_state = RunState.RUNNING
        self.writer.write(self.step_progress)

    def finish(self, is_success: bool, error_message: Optional[str] = None):
        """Finish a step whether it was successful or not"""
        if self.step_progress.run_state != RunState.RUNNING:
            return
        else:
            self.step_progress.finished_at = datetime.now(timezone.utc)
            self.step_progress.run_state = (
                RunState.SUCCEEDED if is_success else RunState.FAILED
            )
            self.step_progress.error_message = error_message if error_message else None
            self.writer.write(self.step_progress)

    def create_child_step(
        self, short_desc: str, **step_progress_kwargs
    ) -> "StepProgressReporter":
        """Create a child step"""
        child_step_progress = StepProgress(
            short_desc=short_desc,
            parent_step_id=self.step_progress.step_id,
            task_id=self.step_progress.task_id,
            **step_progress_kwargs,
        )
        child_reporter = StepProgressReporter(
            step_progress=child_step_progress, writer=self.writer
        )
        return child_reporter
