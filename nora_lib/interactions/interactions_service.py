import json
import requests
from models import (
    Event,
    ReturnedMessage
   
)

# pylint: disable=too-few-public-methods
class InteractionsService:
    """
    Service which saves interactions to the Interactions API
    """

    def __init__(self, base_url, timeout, token):
        self.base_url = base_url
        self.timeout = timeout
        self.headers = {"Authorization": f"Bearer {token}"}


    def save_event(self, event: Event) -> None:
        """Save an event to the Interactions API"""
        event_url = f"{self.base_url}/interaction/v1/event"
        response = requests.post(
            event_url,
            # json=json.loads(event.model_dump_json()), # sends dict with UUID/timestamp as strings
            json=event.model_dump(),
            headers=self.headers,
            timeout=int(self.timeout),
        )
        response.raise_for_status()

    def get_message(self, message_id: str) -> ReturnedMessage:
        """Fetch a message from the Interactions API"""
        message_url = f"{self.base_url}/interaction/v1/search/message"
        request_body = {"id": message_id}
        response = requests.post(
            message_url,
            json=request_body,
            headers=self.headers,
            timeout=int(self.timeout),
        )
        response.raise_for_status()
        return ReturnedMessage.model_validate(response.json().get("message"))