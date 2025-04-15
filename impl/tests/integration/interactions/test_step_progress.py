import unittest
from unittest.mock import ANY, MagicMock
from uuid import uuid4

from nora_lib.progress.models import StepProgress
from nora_lib.progress.reporter import RunState

from nora_lib.impl.interactions.interactions_service import InteractionsService
from nora_lib.impl.interactions.models import *
from nora_lib.impl.interactions.step_progress import StepProgressReporter
from nora_lib.impl.pubsub import PubsubService

ACTOR = uuid4()
THREAD = str(uuid4())
CHANNEL = str(uuid4())


def _msg(text: str) -> Message:
    return Message(
        message_id=str(uuid4()),
        actor_id=ACTOR,
        text=text,
        channel_id=CHANNEL,
        thread_id=THREAD,
        surface=Surface.WEB,
        ts=datetime.now(),
    )


def _spr(
    iservice: InteractionsService, pubsub_service: PubsubService
) -> StepProgressReporter:
    message = _msg("Hi")
    iservice.save_message(message)
    return StepProgressReporter(
        actor_id=ACTOR,
        message_id=message.message_id,
        thread_id=message.thread_id,
        step_progress=StepProgress(
            short_desc="short step",
            task_id=str(uuid4()),
        ),
        interactions_service=iservice,
        pubsub_service=pubsub_service,
    )


class TestStepProgressReporter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.iservice = InteractionsService(
            "http://interaction_service:9080", token="test"
        )

    def test_create_start_finish_success(self):
        mock_pubsub_service = MagicMock()
        spr = _spr(self.iservice, mock_pubsub_service)
        spr.create()
        self.assertEqual(spr.step_progress.run_state, RunState.CREATED)
        self.assertIsNotNone(spr.step_progress.created_at)
        mock_pubsub_service.publish.assert_called_once_with(
            topic=f"step_progress:{spr.writer.thread_id}", payload=ANY
        )

        spr.start()
        self.assertEqual(spr.step_progress.run_state, RunState.RUNNING)
        start_event_id = mock_pubsub_service.publish.call_args[1]["payload"]["event_id"]
        assert start_event_id is not None

        self.assertIsNone(spr.step_progress.finished_at)
        spr.finish(is_success=True)
        self.assertEqual(spr.step_progress.run_state, RunState.SUCCEEDED)
        self.assertIsNotNone(spr.step_progress.finished_at)
        finish_event_id = (
            mock_pubsub_service.publish.call_args[1]["payload"]["event_id"],
        )
        assert finish_event_id is not None

    def test_finish_after_finish(self):
        mock_pubsub_service = MagicMock()
        spr = _spr(self.iservice, mock_pubsub_service)
        spr.create()
        spr.start()
        spr.finish(is_success=False, error_message="error")
        failed_at = spr.step_progress.finished_at
        self.assertEqual(spr.step_progress.run_state, RunState.FAILED)
        publish_call_count = mock_pubsub_service.publish.call_count

        # Finish again, should do nothing
        spr.finish(is_success=True)
        self.assertEqual(spr.step_progress.run_state, RunState.FAILED)
        self.assertEqual(spr.step_progress.finished_at, failed_at)
        # Don't publish to Pubsub. Call count remains the same
        self.assertEqual(mock_pubsub_service.publish.call_count, publish_call_count)

    def test_finish_before_start(self):
        mock_pubsub_service = MagicMock()
        spr = _spr(self.iservice, mock_pubsub_service)
        publish_call_count = mock_pubsub_service.publish.call_count

        spr.finish(is_success=True)
        self.assertEqual(spr.step_progress.run_state, RunState.CREATED)
        self.assertIsNone(spr.step_progress.finished_at)
        # Don't publish to Pubsub. Call count remains the same
        self.assertEqual(mock_pubsub_service.publish.call_count, publish_call_count)

    def test_start_after_start(self):
        mock_pubsub_service = MagicMock()
        spr = _spr(self.iservice, mock_pubsub_service)
        spr.create()
        spr.start()
        started_at = spr.step_progress.started_at
        self.assertIsNotNone(started_at)
        publish_call_count = mock_pubsub_service.publish.call_count

        # Start again, should do nothing
        spr.start()
        self.assertEqual(spr.step_progress.run_state, RunState.RUNNING)
        self.assertEqual(spr.step_progress.started_at, started_at)
        # Don't publish to Pubsub. Call count remains the same
        self.assertEqual(mock_pubsub_service.publish.call_count, publish_call_count)

    def test_start_after_finish(self):
        mock_pubsub_service = MagicMock()
        spr = _spr(self.iservice, mock_pubsub_service)
        spr.create()
        spr.start()
        spr.finish(is_success=True)
        finished_at = spr.step_progress.finished_at
        self.assertEqual(spr.step_progress.run_state, RunState.SUCCEEDED)
        publish_call_count = mock_pubsub_service.publish.call_count

        # Start again, should do nothing
        spr.start()
        self.assertEqual(spr.step_progress.run_state, RunState.SUCCEEDED)
        self.assertEqual(spr.step_progress.finished_at, finished_at)
        # Don't publish to Pubsub. Call count remains the same
        self.assertEqual(mock_pubsub_service.publish.call_count, publish_call_count)

    def test_create_child_step(self):
        mock_pubsub_service = MagicMock()
        spr = _spr(self.iservice, mock_pubsub_service)
        child_spr = spr.create_child_step(short_desc="child step")
        self.assertNotEqual(child_spr.step_progress.step_id, spr.step_progress.step_id)
        self.assertEqual(
            child_spr.step_progress.parent_step_id, spr.step_progress.step_id
        )
        self.assertEqual(child_spr.step_progress.task_id, spr.step_progress.task_id)

    def test_with_context_management_success(self):
        mock_pubsub_service = MagicMock()
        with _spr(self.iservice, mock_pubsub_service) as spr:
            pass

        # Should finish on its own
        self.assertEqual(spr.step_progress.run_state, RunState.SUCCEEDED)
        # Should automatically go through all state transitions: CREATED -> RUNNING -> SUCCEEDED
        self.assertIsNotNone(spr.step_progress.created_at)
        self.assertIsNotNone(spr.step_progress.started_at)
        self.assertIsNotNone(spr.step_progress.finished_at)
        self.assertEqual(mock_pubsub_service.publish.call_count, 3)
