from datetime import datetime, timezone
from uuid import UUID

from nora_lib.progress.models import StepProgress, RunState
from nora_lib.progress.reporter import (
    StepProgressWriter,
    StepProgressReporter as IStepProgressReporter,
)

from nora_lib.impl.pubsub import PubsubService
from nora_lib.impl.interactions.interactions_service import InteractionsService
from nora_lib.impl.interactions.models import Event, EventType


class StepProgressIStoreWriter(StepProgressWriter):
    def __init__(
        self,
        actor_id: UUID,
        message_id: str,
        thread_id: str,
        interactions_service: InteractionsService,
        pubsub_service: PubsubService,
    ):
        self.actor_id = actor_id
        self.message_id = message_id
        self.thread_id = thread_id
        self.interactions_service = interactions_service
        self.pubsub_service = pubsub_service

    def write(self, step_progress: StepProgress) -> None:
        timestamp = datetime.now(timezone.utc)
        event_id = self.interactions_service.save_event(
            Event(
                type=EventType.STEP_PROGRESS.value,
                actor_id=self.actor_id,
                timestamp=timestamp,
                data=step_progress.model_dump(exclude_none=True),
                message_id=self.message_id,
            )
        )
        if step_progress.run_state == RunState.CREATED:
            # Overwrite the created_at timestamp with the event timestamp from the DB
            event = self.interactions_service.get_event(event_id)
            step_progress.created_at = event.timestamp

        self.pubsub_service.publish(
            topic=f"step_progress:{self.thread_id}",
            payload={"event_id": event_id, "timestamp": timestamp.isoformat()},
        )


class StepProgressReporter(IStepProgressReporter):
    def __init__(
        self,
        actor_id: UUID,
        message_id: str,
        thread_id: str,
        step_progress: StepProgress,
        interactions_service: InteractionsService,
        pubsub_service: PubsubService,
    ):
        writer = StepProgressIStoreWriter(
            actor_id=actor_id,
            message_id=message_id,
            thread_id=thread_id,
            interactions_service=interactions_service,
            pubsub_service=pubsub_service,
        )
        super().__init__(step_progress, writer)
