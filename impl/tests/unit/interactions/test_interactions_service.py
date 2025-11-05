import unittest
from datetime import datetime
from uuid import uuid4
from requests import HTTPError, Response
from unittest.mock import call, patch, MagicMock

from nora_lib.impl.interactions.interactions_service import InteractionsService, RetryConfig
from nora_lib.impl.interactions.models import Event


class TestInteractionsService(unittest.TestCase):
    # some helpers
    @staticmethod
    def _mk_event(event_id):
        return Event(
            event_id=event_id,
            type="step_progress",
            actor_id=uuid4(),
            timestamp=datetime.now(),
            text="testing retries"
        )

    @staticmethod
    def _mk_response(status_code, maybe_event):
        resp = Response()
        resp.status_code = status_code
        if maybe_event is not None:
            resp.json = MagicMock(return_value = {"events": [maybe_event]})  # type: ignore
        return resp

    @staticmethod
    def _mk_expected_calls(event_id, num_calls):
        # we're just going to test with get_event()
        expected_calls = []
        for i in range(num_calls):
            expected_calls.append(
                call(
                    method="post",
                    url="somewhere/interaction/v1/search/event",
                    json={"id": event_id},
                    auth=None,
                    timeout=30,
                )
            )
        return expected_calls

    @patch("requests.request")
    def test_retries_default(self, req_mock):
        # Don't change anything about the retry config
        iservice = InteractionsService("somewhere")

        # Since we haven't changed the retry config, we only have one try.
        # Say it's successful.
        event_id_success = "1"
        event_in = TestInteractionsService._mk_event(event_id_success)
        req_mock.side_effect = [TestInteractionsService._mk_response(200, event_in)]
        event_out = iservice.get_event(event_id_success)
        self.assertEqual(event_in, event_out)
        # just one call
        self.assertEqual(req_mock.mock_calls, TestInteractionsService._mk_expected_calls(event_id_success, num_calls=1))
        req_mock.reset_mock()

        # Suppose the first try is not successful
        event_id_failure = "2"
        for error_status in [500, 501, 400]:
            req_mock.side_effect = [TestInteractionsService._mk_response(error_status, None)]
            with self.assertRaises(HTTPError) as exc:
                iservice.get_event(event_id_failure)
            # Make sure the right status code is getting plumbed through
            self.assertIn(str(error_status), str(exc.exception))
            # still just one call
            self.assertEqual(req_mock.mock_calls, TestInteractionsService._mk_expected_calls(event_id_failure, num_calls=1))
            req_mock.reset_mock()

    @patch("requests.request")
    def test_some_retries(self, req_mock):
        # Here, test with 3 tries (so 2 retries)
        iservice = InteractionsService("somewhere", retry_config=RetryConfig(tries=3))

        # since we have 3 tries in this particular test's retry config,
        # we can tolerate 0, 1 or 2 failures while still having a chance to succeed
        num_failures_before_success = [0, 1, 2]
        for idx, num_failures in enumerate(num_failures_before_success):

            # this will collect the responses we get, in order
            for_side_effect = []

            # first add the failure responses - this test case
            # is for num_failures failures before a success
            for i in range(num_failures):
                for_side_effect.append(TestInteractionsService._mk_response(500, None))

            # next, add a successful response
            event_id_success = str(idx)
            event_in = TestInteractionsService._mk_event(event_id_success)
            for_side_effect.append(TestInteractionsService._mk_response(200, event_in))

            # set the responses
            req_mock.side_effect = for_side_effect

            # see if we get the right thing out
            event_out = iservice.get_event(event_id_success)
            self.assertEqual(event_in, event_out)

            # double check we called request() the expected number of times
            # (all failures plus one success)
            self.assertEqual(req_mock.mock_calls, TestInteractionsService._mk_expected_calls(event_id_success, num_calls=num_failures + 1))
            req_mock.reset_mock()

        # even if we have a success coming up, if we hit a non-retryable error first,
        # we won't get there
        event_id_non_retryable = "3"
        req_mock.side_effect = [
            TestInteractionsService._mk_response(400, None),
            TestInteractionsService._mk_response(200, TestInteractionsService._mk_event(event_id_non_retryable)),
        ]
        with self.assertRaises(HTTPError) as exc3:
            iservice.get_event(event_id_non_retryable)
        self.assertIn("400", str(exc3.exception))
        # just one call
        self.assertEqual(req_mock.mock_calls, TestInteractionsService._mk_expected_calls(event_id_non_retryable, num_calls=1))
        req_mock.reset_mock()

        # if we get to 3 failures, we won't succeed
        event_id_exhaust_failures = "4"
        req_mock.side_effect = [
            TestInteractionsService._mk_response(500, None),
            TestInteractionsService._mk_response(502, None),
            TestInteractionsService._mk_response(500, None),
            TestInteractionsService._mk_response(200, TestInteractionsService._mk_event(event_id_exhaust_failures)),
        ]
        with self.assertRaises(HTTPError) as exc4:
            iservice.get_event(event_id_exhaust_failures)
        self.assertIn("500", str(exc4.exception))
        # check we stopped at three calls
        self.assertEqual(req_mock.mock_calls, TestInteractionsService._mk_expected_calls(event_id_exhaust_failures, num_calls=3))
        req_mock.reset_mock()
