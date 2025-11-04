import unittest
from datetime import datetime
from uuid import uuid4
from requests import HTTPError, Response
from unittest.mock import MagicMock
from unittest.mock import patch

from nora_lib.impl.interactions.interactions_service import InteractionsService
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
            resp.json = MagicMock(return_value = {"events": [event_in]})
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
                event_out = iservice.get_event("hi2")
            # Make sure the right status code is getting plumbed through
            self.assertIn(str(error_status), str(exc.exception))
