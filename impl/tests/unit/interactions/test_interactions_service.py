import unittest
from datetime import datetime
from uuid import uuid4
from requests import Response
from unittest.mock import MagicMock
from unittest.mock import patch

from nora_lib.impl.interactions.interactions_service import InteractionsService
from nora_lib.impl.interactions.models import Event


class TestInteractionsService(unittest.TestCase):
    def test_something(self):
        self.assertEqual(0, 0)

    @patch("requests.request")
    def test_something2(self, req_mock):

        event_in = Event(
            type="step_progress",
            actor_id=uuid4(),
            timestamp=datetime.now(),
            text="testing retries"
        )

        def mk_response(status_code):
            # resp = MagicMock()
            # resp.status_code = status_code
            # return resp
            resp = Response()
            resp.status_code = status_code
            resp.json = MagicMock(return_value = {"events": [event_in]})
            return resp

        # to_return_options = 
        # to_return_idx = 0
        # def to_return():
        #     pass
        # req_mock.return_value = "bye"

        # req_mock.side_effect = [mk_response(200)]
        req_mock.side_effect = [mk_response(500), mk_response(200)]
        iservice = InteractionsService("somwhere")
        event_out = iservice.get_event("hi")

        self.assertEqual(event_in, event_out)
