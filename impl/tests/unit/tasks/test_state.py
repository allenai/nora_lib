import tempfile
import unittest

from pydantic import BaseModel, Field

from nora_lib.tasks.models import AsyncTaskState, TASK_STATUSES
from nora_lib.tasks.state import NoSuchTaskException, StateManager


class MyTaskResult(BaseModel):
    a: str
    b: int


class MyAsyncTaskState(AsyncTaskState[MyTaskResult]):
    pass


class TestState(unittest.TestCase):
    def test__can_read_and_write_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(MyAsyncTaskState, tmpdir)
            state = MyAsyncTaskState(
                task_id="asdf",
                estimated_time="40 days and 40 nights",
                task_status="STARTED",
                task_result=None,
                extra_state={"foo": "bar"},
            )
            manager.write_state(state)
            fetched_state = manager.read_state("asdf")

            self.assertEqual(state, fetched_state)

    def test__raises_an_error_if_referencing_nonexistent_task(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(MyAsyncTaskState, tmpdir)
            with self.assertRaises(NoSuchTaskException):
                manager.read_state("asdf")

    def test__allows_specific_update_of_status_field(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(MyAsyncTaskState, tmpdir)
            state = MyAsyncTaskState(
                task_id="asdf",
                estimated_time="40 days and 40 nights",
                task_status="STARTED",
                task_result=None,
                extra_state={"foo": "bar"},
            )
            manager.write_state(state)
            manager.update_status(state.task_id, "fail")
            fetched_state = manager.read_state("asdf")
            state.task_status = "fail"

            self.assertEqual(state, fetched_state)

    def test__allows_specific_update_of_result_field(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(MyAsyncTaskState, tmpdir)
            state = MyAsyncTaskState(
                task_id="asdf",
                estimated_time="40 days and 40 nights",
                task_status="STARTED",
                task_result=None,
                extra_state={"foo": "bar"},
            )
            manager.write_state(state)

            result = MyTaskResult(a="asdf", b=123)
            manager.save_result(state.task_id, result)
            fetched_state = manager.read_state("asdf")

            state.task_status = TASK_STATUSES["COMPLETED"]
            state.task_result = result

            self.assertEqual(state, fetched_state)
