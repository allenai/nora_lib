import unittest
from uuid import uuid4

from nora_lib.pubsub import PubsubService

from nora_lib.interactions.step_progress import (
    StepProgressReporter,
    StepProgress,
    RunState,
)
from nora_lib.interactions.models import *

from nora_lib.interactions.interactions_service import InteractionsService

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
        step_progress=StepProgress(short_desc="short step"),
        interactions_service=iservice,
        pubsub_service=pubsub_service,
    )


class TestStepProgressReporter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.iservice = InteractionsService(
            "http://interaction_service:9080", token="test"
        )
        cls.pubsub_service = PubsubService("test", "test")

    def test_create_start_finish_success(self):
        spr = _spr(self.iservice, self.pubsub_service)
        self.assertEqual(spr.step_progress.run_state, RunState.CREATED)
        self.assertIsNotNone(spr.step_progress.created_at)

        spr.start()
        self.assertEqual(spr.step_progress.run_state, RunState.RUNNING)

        self.assertIsNone(spr.step_progress.finished_at)
        spr.finish(is_success=True)
        self.assertEqual(spr.step_progress.run_state, RunState.SUCCEEDED)
        self.assertIsNotNone(spr.step_progress.finished_at)

    def test_finish_after_finish(self):
        spr = _spr(self.iservice, self.pubsub_service)
        spr.start()
        spr.finish(is_success=False, error_message="error")
        failed_at = spr.step_progress.finished_at
        self.assertEqual(spr.step_progress.run_state, RunState.FAILED)

        # Finish again, should do nothing
        spr.finish(is_success=True)
        self.assertEqual(spr.step_progress.run_state, RunState.FAILED)
        self.assertEqual(spr.step_progress.finished_at, failed_at)

    def test_finish_before_start(self):
        spr = _spr(self.iservice, self.pubsub_service)
        spr.finish(is_success=True)
        self.assertEqual(spr.step_progress.run_state, RunState.CREATED)
        self.assertIsNone(spr.step_progress.finished_at)

    def test_start_after_start(self):
        spr = _spr(self.iservice, self.pubsub_service)
        spr.start()
        started_at = spr.step_progress.started_at
        self.assertIsNotNone(started_at)

        # Start again, should do nothing
        spr.start()
        self.assertEqual(spr.step_progress.run_state, RunState.RUNNING)
        self.assertEqual(spr.step_progress.started_at, started_at)

    def test_start_after_finish(self):
        spr = _spr(self.iservice, self.pubsub_service)
        spr.start()
        spr.finish(is_success=True)
        finished_at = spr.step_progress.finished_at
        self.assertEqual(spr.step_progress.run_state, RunState.SUCCEEDED)

        # Start again, should do nothing
        spr.start()
        self.assertEqual(spr.step_progress.run_state, RunState.SUCCEEDED)
        self.assertEqual(spr.step_progress.finished_at, finished_at)

    def test_create_child_step(self):
        spr = _spr(self.iservice, self.pubsub_service)
        child_spr = spr.create_child_step(short_desc="child step")
        self.assertEqual(
            child_spr.step_progress.parent_step_id, spr.step_progress.step_id
        )

    def test_with_context_management_success(self):
        with _spr(self.iservice, self.pubsub_service) as spr:
            spr.start()

        # Should finish on its own
        self.assertEqual(spr.step_progress.run_state, RunState.SUCCEEDED)

    def test_with_context_management_catch_exception(self):
        error_message = "whoops"
        with _spr(self.iservice, self.pubsub_service) as spr:
            spr.start()
            raise RuntimeError(error_message)

        self.assertEqual(spr.step_progress.run_state, RunState.FAILED)
        self.assertEqual(spr.step_progress.error_message, error_message)
