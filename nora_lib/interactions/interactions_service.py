from datetime import datetime
import requests
from typing import List, Optional

from nora_lib.interactions.models import (
    Event,
    EventType,
    ReturnedMessage,
    ThreadRelationsResponse,
    ThreadForkEventData,
    thread_message_lookup_request,
)


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
            json=event.model_dump(),
            headers=self.headers,
            timeout=int(self.timeout),
        )
        response.raise_for_status()

    def fetch_thread_messages_and_events_for_message(
        self, message_id: str, event_type: str
    ) -> ThreadRelationsResponse:
        """Fetch messages and associated events from the same thread as provided messagev id"""
        message_url = f"{self.base_url}/interaction/v1/search/message"
        request_body = thread_message_lookup_request(message_id, event_type=event_type)
        response = requests.post(
            message_url,
            json=request_body,
            headers=self.headers,
            timeout=int(self.timeout),
        )
        response.raise_for_status()
        json_response = response.json()

        return ThreadRelationsResponse.model_validate(
            json_response.get("message", {}).get("thread", {})
        )

    def fetch_messages_and_events_for_thread(
        self,
        thread_id: str,
        event_type: Optional[str] = None,
        min_timestamp: Optional[str] = None,
    ) -> dict:
        """Fetch messages and events for the thread containing a given message from the Interactions API"""
        THREAD_SEARCH_URL = f"{self.base_url}/interaction/v1/search/thread"
        request_body = {
            "id": thread_id,
            "relations": {
                "messages": (
                    {"filter": {"min_timestamp": min_timestamp}}
                    if min_timestamp
                    else {}
                ),
                "events": {"filter": {"type": event_type}} if event_type else {},
            },
        }

        response = requests.post(
            THREAD_SEARCH_URL,
            json=request_body,
            headers=self.headers,
            timeout=int(self.timeout),
        )
        response.raise_for_status()
        return response.json()

    def fetch_messages_and_events_for_forked_thread(
        self, message_id: str, event_type: str
    ) -> List[ReturnedMessage]:
        """Build a history of messages for a given message including associated events.
        This includes messages from pre-forked threads."""
        returned_messages: List[ReturnedMessage] = []

        messages_for_thread: ThreadRelationsResponse = (
            self.fetch_thread_messages_and_events_for_message(message_id, event_type)
        )
        if messages_for_thread.messages:
            returned_messages.extend(messages_for_thread.messages)

        # Lookup any thread_fork events (conversation across surfaces)
        thread_fork_events = self.fetch_messages_and_events_for_thread(
            messages_for_thread.thread_id, EventType.THREAD_FORK.value
        )
        for forked_thread_event in thread_fork_events.get("thread", {}).get(
            "events", []
        ):
            event_data = ThreadForkEventData.model_validate(
                forked_thread_event.get("data", {})
            )
            forked_thread: ThreadRelationsResponse = (
                self.fetch_thread_messages_and_events_for_message(
                    event_data.previous_message_id, event_type
                )
            )
            if forked_thread.messages:
                returned_messages.extend(forked_thread.messages)

        returned_messages.sort(key=lambda x: datetime.fromisoformat(x.ts))

        return returned_messages
