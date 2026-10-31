import unittest
from datetime import datetime
from uuid import uuid4
from requests import ConnectionError, HTTPError, Response, Timeout
from unittest.mock import call, patch, MagicMock

from nora_lib.impl.interactions.interactions_service import (
    InteractionsService,
    RetryConfig,
)
from nora_lib.impl.interactions.models import Channel, Event, Surface


class TestInteractionsService(unittest.TestCase):
    # some helpers
    @staticmethod
    def _mk_event(event_id):
        return Event(
            event_id=event_id,
            type="step_progress",
            actor_id=uuid4(),
            timestamp=datetime.now(),
            text="testing retries",
        )

    @staticmethod
    def _mk_response(status_code, maybe_event):
        resp = Response()
        resp.status_code = status_code
        if maybe_event is not None:
            resp.json = MagicMock(return_value={"events": [maybe_event]})  # type: ignore
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
        self.assertEqual(
            req_mock.mock_calls,
            TestInteractionsService._mk_expected_calls(event_id_success, num_calls=1),
        )
        req_mock.reset_mock()

        # Suppose the first try is not successful
        event_id_failure = "2"
        for error_status in [500, 501, 400]:
            req_mock.side_effect = [
                TestInteractionsService._mk_response(error_status, None)
            ]
            with self.assertRaises(HTTPError) as exc:
                iservice.get_event(event_id_failure)
            # Make sure the right status code is getting plumbed through
            self.assertIn(str(error_status), str(exc.exception))
            # still just one call
            self.assertEqual(
                req_mock.mock_calls,
                TestInteractionsService._mk_expected_calls(
                    event_id_failure, num_calls=1
                ),
            )
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
            self.assertEqual(
                req_mock.mock_calls,
                TestInteractionsService._mk_expected_calls(
                    event_id_success, num_calls=num_failures + 1
                ),
            )
            req_mock.reset_mock()

        # even if we have a success coming up, if we hit a non-retryable error first,
        # we won't get there
        event_id_non_retryable = "3"
        req_mock.side_effect = [
            TestInteractionsService._mk_response(400, None),
            TestInteractionsService._mk_response(
                200, TestInteractionsService._mk_event(event_id_non_retryable)
            ),
        ]
        with self.assertRaises(HTTPError) as exc3:
            iservice.get_event(event_id_non_retryable)
        self.assertIn("400", str(exc3.exception))
        # just one call
        self.assertEqual(
            req_mock.mock_calls,
            TestInteractionsService._mk_expected_calls(
                event_id_non_retryable, num_calls=1
            ),
        )
        req_mock.reset_mock()

        # if we get to 3 failures, we won't succeed
        event_id_exhaust_failures = "4"
        req_mock.side_effect = [
            TestInteractionsService._mk_response(500, None),
            TestInteractionsService._mk_response(502, None),
            TestInteractionsService._mk_response(500, None),
            TestInteractionsService._mk_response(
                200, TestInteractionsService._mk_event(event_id_exhaust_failures)
            ),
        ]
        with self.assertRaises(HTTPError) as exc4:
            iservice.get_event(event_id_exhaust_failures)
        self.assertIn("500", str(exc4.exception))
        # check we stopped at three calls
        self.assertEqual(
            req_mock.mock_calls,
            TestInteractionsService._mk_expected_calls(
                event_id_exhaust_failures, num_calls=3
            ),
        )
        req_mock.reset_mock()

    @staticmethod
    def _mk_thread_fetch_call(thread_id):
        return call(
            method="post",
            url="somewhere/interaction/v1/search/thread",
            json={
                "id": thread_id,
                "relations": {
                    "messages": {
                        "filter": None,
                        "apply_annotations_from_actors": ["*"],
                    },
                    "events": {},
                },
            },
            auth=None,
            timeout=30,
        )

    @patch("retry.api.time.sleep")
    @patch("requests.request")
    def test_fetch_messages_and_events_for_thread_retries(self, req_mock, _sleep):
        # Retries transient 5xx even though the client defaults to one try
        iservice = InteractionsService("somewhere")
        body = {"thread": {"id": "t1"}}
        req_mock.side_effect = [
            TestInteractionsService._mk_json_response(502),
            TestInteractionsService._mk_json_response(500),
            TestInteractionsService._mk_json_response(200, body),
        ]
        self.assertEqual(body, iservice.fetch_messages_and_events_for_thread("t1"))
        self.assertEqual(
            req_mock.mock_calls,
            [TestInteractionsService._mk_thread_fetch_call("t1")] * 3,
        )
        req_mock.reset_mock()

        # Gives up after 3 tries
        req_mock.side_effect = [
            TestInteractionsService._mk_json_response(502),
            TestInteractionsService._mk_json_response(502),
            TestInteractionsService._mk_json_response(503),
            TestInteractionsService._mk_json_response(200, body),
        ]
        with self.assertRaises(HTTPError) as exc:
            iservice.fetch_messages_and_events_for_thread("t1")
        self.assertIn("503", str(exc.exception))
        self.assertEqual(len(req_mock.mock_calls), 3)
        req_mock.reset_mock()

        # 4xx, including the boundary immediately below 500, is not retried.
        for status_code in (404, 499):
            with self.subTest(status_code=status_code):
                req_mock.side_effect = [
                    TestInteractionsService._mk_json_response(status_code),
                    TestInteractionsService._mk_json_response(200, body),
                ]
                with self.assertRaises(HTTPError):
                    iservice.fetch_messages_and_events_for_thread("t1")
                self.assertEqual(req_mock.call_count, 1)
                req_mock.reset_mock()

    @patch("retry.api.time.sleep")
    @patch("requests.request")
    def test_thread_fetch_retries_server_error_boundaries(self, req_mock, sleep_mock):
        iservice = InteractionsService("somewhere")
        body = {"thread": {"id": "t1"}}
        for status_code in (500, 504, 599):
            with self.subTest(status_code=status_code):
                req_mock.side_effect = [
                    self._mk_json_response(status_code),
                    self._mk_json_response(200, body),
                ]
                self.assertEqual(
                    body, iservice.fetch_messages_and_events_for_thread("t1")
                )
                self.assertEqual(
                    req_mock.mock_calls,
                    [self._mk_thread_fetch_call("t1")] * 2,
                )
                sleep_mock.assert_called_once_with(1)
                req_mock.reset_mock()
                sleep_mock.reset_mock()

    @patch("retry.api.time.sleep")
    @patch("requests.request")
    def test_thread_fetch_retries_do_not_change_other_calls(self, req_mock, _sleep):
        iservice = InteractionsService("somewhere")
        req_mock.side_effect = [
            TestInteractionsService._mk_response(502, None),
            TestInteractionsService._mk_response(
                200, TestInteractionsService._mk_event("1")
            ),
        ]
        with self.assertRaises(HTTPError):
            iservice.get_event("1")
        self.assertEqual(len(req_mock.mock_calls), 1)

    @patch("retry.api.time.sleep")
    @patch("requests.request")
    def test_thread_fetch_preserves_retry_timing(self, req_mock, sleep_mock):
        for configured_tries in (0, 1, 2, 5):
            with self.subTest(tries=configured_tries):
                config = RetryConfig(
                    tries=configured_tries,
                    delay=2,
                    max_delay=7,
                    backoff=3,
                    jitter=(2, 2),
                )
                iservice = InteractionsService("somewhere", retry_config=config)
                expected_tries = max(3, configured_tries)
                body = {"thread": {"id": "t1"}}
                req_mock.side_effect = [
                    self._mk_json_response(502) for _ in range(expected_tries - 1)
                ] + [self._mk_json_response(200, body)]

                self.assertEqual(
                    body, iservice.fetch_messages_and_events_for_thread("t1")
                )
                self.assertEqual(req_mock.call_count, expected_tries)
                # Initial delay, followed by backoff + jitter capped at max_delay.
                self.assertEqual(
                    sleep_mock.call_args_list,
                    [call(2)] + [call(7)] * (expected_tries - 2),
                )
                self.assertEqual(config.tries, configured_tries)
                self.assertIs(iservice.retry_config, config)
                req_mock.reset_mock()
                sleep_mock.reset_mock()

    @patch("retry.api.time.sleep")
    @patch("requests.request")
    def test_thread_fetch_preserves_unlimited_retries(self, req_mock, sleep_mock):
        for configured_tries in (-1, -2):
            with self.subTest(tries=configured_tries):
                config = RetryConfig(
                    tries=configured_tries, delay=2, backoff=1, jitter=0
                )
                iservice = InteractionsService("somewhere", retry_config=config)
                body = {"thread": {"id": "t1"}}
                req_mock.side_effect = [
                    self._mk_json_response(502) for _ in range(4)
                ] + [self._mk_json_response(200, body)]
                self.assertEqual(
                    body, iservice.fetch_messages_and_events_for_thread("t1")
                )
                self.assertEqual(req_mock.call_count, 5)
                self.assertEqual(sleep_mock.call_args_list, [call(2)] * 4)
                self.assertEqual(config.tries, configured_tries)
                self.assertIs(iservice.retry_config, config)
                req_mock.reset_mock()
                sleep_mock.reset_mock()

    @patch("retry.api.time.sleep")
    @patch("requests.request")
    def test_thread_fetch_transport_errors_are_not_retried(self, req_mock, sleep_mock):
        iservice = InteractionsService("somewhere")
        for error in (ConnectionError("connection failed"), Timeout("timed out")):
            with self.subTest(error=type(error).__name__):
                req_mock.side_effect = error
                with self.assertRaises(type(error)) as exc:
                    iservice.fetch_messages_and_events_for_thread("t1")
                self.assertIs(exc.exception, error)
                req_mock.assert_called_once()
                sleep_mock.assert_not_called()
                req_mock.reset_mock()

    @staticmethod
    def _mk_json_response(status_code, body_dict=None):
        resp = Response()
        resp.status_code = status_code
        if body_dict is not None:
            resp.json = MagicMock(return_value=body_dict)  # type: ignore
        return resp

    @patch("requests.request")
    def test_save_channel(self, req_mock):
        iservice = InteractionsService("somewhere")
        channel = Channel(
            channel_id="c-1", surface=Surface.WEB, owning_actor_id="actor-1"
        )

        # Happy path
        req_mock.side_effect = [TestInteractionsService._mk_json_response(200, None)]
        iservice.save_channel(channel)
        self.assertEqual(
            req_mock.mock_calls,
            [
                call(
                    method="post",
                    url="somewhere/interaction/v1/channel",
                    json=channel.model_dump(),
                    auth=None,
                    timeout=30,
                )
            ],
        )
        req_mock.reset_mock()

        # Non-retryable error should propagate
        req_mock.side_effect = [TestInteractionsService._mk_json_response(400, None)]
        with self.assertRaises(HTTPError) as exc:
            iservice.save_channel(channel)
        self.assertIn("400", str(exc.exception))

    @patch("requests.request")
    def test_get_channel(self, req_mock):
        iservice = InteractionsService("somewhere")
        channel_dict = {
            "channel_id": "c-1",
            "surface": Surface.WEB.value,
            "owning_actor_id": "actor-1",
        }

        # get_channel unwraps the response from a {"channel": ...} envelope.
        req_mock.side_effect = [
            TestInteractionsService._mk_json_response(200, {"channel": channel_dict})
        ]
        fetched = iservice.get_channel("c-1")
        self.assertEqual(
            fetched,
            Channel(channel_id="c-1", surface=Surface.WEB, owning_actor_id="actor-1"),
        )
        self.assertEqual(
            req_mock.mock_calls,
            [
                call(
                    method="post",
                    url="somewhere/interaction/v1/search/channel",
                    json={"id": "c-1"},
                    auth=None,
                    timeout=30,
                )
            ],
        )
        req_mock.reset_mock()

        # Error status should propagate
        req_mock.side_effect = [TestInteractionsService._mk_json_response(404, None)]
        with self.assertRaises(HTTPError) as exc:
            iservice.get_channel("missing")
        self.assertIn("404", str(exc.exception))

    @patch("requests.request")
    def test_get_sentences_by_id(self, req_mock):
        iservice = InteractionsService("somewhere")
        sentences = {
            "s-1": {
                "bboxs": [
                    {"page": 18, "top": 598.4, "left": 70.9, "h": 13.1, "w": 218.7}
                ]
            },
            "s-2": {
                "bboxs": [
                    {"page": 18, "top": 611.9, "left": 70.9, "h": 13.1, "w": 218.3}
                ]
            },
        }

        # Happy path: ids are comma-joined into the query string and the JSON
        # body is returned as-is.
        req_mock.side_effect = [
            TestInteractionsService._mk_json_response(200, sentences)
        ]
        fetched = iservice.get_sentences_by_id(["s-1", "s-2"])
        self.assertEqual(fetched, sentences)
        self.assertEqual(
            req_mock.mock_calls,
            [
                call(
                    method="get",
                    url=(
                        "somewhere/corpus/v1/vespa/publicapi/sentence/batch/"
                        "idlookup?sentence_ids=s-1,s-2"
                    ),
                    json=None,
                    auth=None,
                    timeout=30,
                )
            ],
        )
        req_mock.reset_mock()

        # Error status should propagate
        req_mock.side_effect = [TestInteractionsService._mk_json_response(404, None)]
        with self.assertRaises(HTTPError) as exc:
            iservice.get_sentences_by_id(["missing"])
        self.assertIn("404", str(exc.exception))

    @patch("requests.request")
    def test_get_channel_by_context(self, req_mock):
        iservice = InteractionsService("somewhere")
        channel_dict = {
            "channel_id": "c-1",
            "surface": Surface.WEB.value,
            "owning_actor_id": "actor-1",
        }

        # Context id can be any of channel/thread/message/event id; service always
        # GETs the same endpoint shape.
        req_mock.side_effect = [
            TestInteractionsService._mk_json_response(200, {"channel": channel_dict})
        ]
        fetched = iservice.get_channel_by_context("thread-1")
        self.assertEqual(
            fetched,
            Channel(channel_id="c-1", surface=Surface.WEB, owning_actor_id="actor-1"),
        )
        self.assertEqual(
            req_mock.mock_calls,
            [
                call(
                    method="get",
                    url="somewhere/interaction/v1/channel/by-context/thread-1",
                    json=None,
                    auth=None,
                    timeout=30,
                )
            ],
        )
        req_mock.reset_mock()

        # Error status should propagate
        req_mock.side_effect = [TestInteractionsService._mk_json_response(404, None)]
        with self.assertRaises(HTTPError) as exc:
            iservice.get_channel_by_context("missing")
        self.assertIn("404", str(exc.exception))
