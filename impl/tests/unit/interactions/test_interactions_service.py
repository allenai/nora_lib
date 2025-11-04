import unittest
from datetime import datetime
from uuid import uuid4
from requests import HTTPError, Response
from unittest.mock import MagicMock
from unittest.mock import patch

from nora_lib.impl.interactions.interactions_service import InteractionsService, RetryConfig
from nora_lib.impl.interactions.models import Event


class TestInteractionsService(unittest.TestCase):
    @patch("requests.request")
    def test_retries_default(self, req_mock):
        # Don't change anything about the retry config
        iservice = InteractionsService("somwhere")

        event_in = Event(
            type="step_progress",
            actor_id=uuid4(),
            timestamp=datetime.now(),
            text="testing retries"
        )

        def mk_response(status_code):
            resp = Response()
            resp.status_code = status_code
            resp.json = MagicMock(return_value = {"events": [event_in]})  # type: ignore
            return resp

        # Since we haven't changed the retry config, we only have one try.
        # Say it's successful.
        req_mock.side_effect = [mk_response(200)]
        event_out = iservice.get_event("hi")
        self.assertEqual(event_in, event_out)

        # Suppose the first try is not successful
        for error_status in [500, 501, 400]:
            req_mock.side_effect = [mk_response(error_status)]
            with self.assertRaises(HTTPError) as exc:
                iservice.get_event("hi2")
            # Make sure the right status code is getting plumbed through
            self.assertIn(str(error_status), str(exc.exception))

    @patch("requests.request")
    def test_some_retries(self, req_mock):
        # Here, test with 3 tries (so 2 retries)
        iservice = InteractionsService("somwhere", retry_config=RetryConfig(tries=3))

        def mk_event(event_id):
            return Event(
                event_id=event_id,
                type="step_progress",
                actor_id=uuid4(),
                timestamp=datetime.now(),
                text="testing retries"
            )

        def mk_response(status_code, event):
            resp = Response()
            resp.status_code = status_code
            if event is not None:
                resp.json = MagicMock(return_value = {"events": [event]})  # type: ignore
            return resp

        # since we have 3 tries in this particular test's retry config,
        # we can tolerate 0, 1 or 2 failures while still having a chance to succeed
        num_failures_before_success = [0, 1, 2]
        for idx, num_failures in enumerate(num_failures_before_success):

            # this will collect the responses we get, in order
            for_side_effect = []

            # first add the failure responses - this test case
            # is for num_failures failures before a success
            for i in range(num_failures):
                for_side_effect.append(mk_response(500, None))

            # next, add a successful response
            event_in = mk_event(str(idx))
            for_side_effect.append(mk_response(200, event_in))

            # set the responses
            req_mock.side_effect = for_side_effect

            # see if we get the right thing out
            event_out = iservice.get_event("hi")
            self.assertEqual(event_in, event_out)

        # even if we have a success coming up, if we hit a non-retryable error first,
        # we won't get there
        req_mock.side_effect = [mk_response(400, None), mk_response(200, mk_event("3"))]
        with self.assertRaises(HTTPError) as exc3:
            iservice.get_event("hi")
        self.assertIn("400", str(exc3.exception))

        # if we get to 3 failures, we won't succeed
        req_mock.side_effect = [mk_response(500, None), mk_response(502, None), mk_response(500, None), mk_response(200, mk_event("4"))]
        with self.assertRaises(HTTPError) as exc4:
            iservice.get_event("hi")
        self.assertIn("500", str(exc4.exception))
