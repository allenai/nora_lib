from datetime import datetime
import logging
import requests
from typing import List, Optional
import json

from nora_lib.interactions.models import (
    AnnotationBatch,
    Event,
    EventType,
    Message,
    ReturnedMessage,
    ThreadRelationsResponse,
    ThreadForkEventData,
)


class InteractionsService:
    """
    Service which saves interactions to the Interactions API
    """

    def __init__(self, base_url: str, timeout: int = 30, token: Optional[str] = None):
        self.base_url = base_url
        self.timeout = timeout
        self.headers = {"Authorization": f"Bearer {token}"} if token else None

    def save_message(self, message: Message) -> None:
        """Save a message to the Interactions API"""
        message_url = f"{self.base_url}/interaction/v1/message"
        response = requests.post(
            message_url,
            json=message.model_dump(),
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()

    def save_event(self, event: Event) -> None:
        """Save an event to the Interactions API"""
        event_url = f"{self.base_url}/interaction/v1/event"
        response = requests.post(
            event_url,
            json=event.model_dump(),
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()

    def save_annotation(self, annotation: AnnotationBatch) -> None:
        """Save an annotation to the Interactions API"""
        annotation_url = f"{self.base_url}/interaction/v1/annotation"
        response = requests.post(
            annotation_url,
            json=annotation.model_dump(),
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()

    def get_message(self, message_id: str) -> ReturnedMessage:
        """Fetch a message from the Interactions API"""
        message_url = f"{self.base_url}/interaction/v1/search/message"
        request_body = {
            "id": message_id,
            "relations": {"thread": {}, "channel": {}, "events": {}, "annotations": {}},
        }
        response = requests.post(
            message_url,
            json=request_body,
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        res_dict = response.json()["message"]
        res = ReturnedMessage.model_validate(res_dict)

        # thread_id and channel_id are for some reason nested in the response
        if not res.thread_id:
            res.thread_id = res_dict.get("thread", {}).get("thread_id")
        if not res.channel_id:
            res.channel_id = res_dict.get("channel", {}).get("channel_id")

        return res

    def fetch_all_threads_by_channel(self, channel_id: str, min_timestamp: str) -> dict:
        """Fetch a message from the Interactions API"""
        message_url = f"{self.base_url}/interaction/v1/search/channel"
        request_body = self._channel_lookup_request(
            channel_id=channel_id, min_timestamp=min_timestamp
        )
        response = requests.post(
            message_url,
            json=request_body,
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def fetch_messages_and_agent_context_events_for_thread(
        self, message_id: str, event_type: str
    ) -> List[ReturnedMessage]:
        """Build a history of messages for a given message including associated events.
        This includes messages from pre-forked threads."""
        messages_with_events: List[ReturnedMessage] = []

        messages_for_thread: ThreadRelationsResponse = (
            self.fetch_thread_messages_and_events_for_message(
                message_id, [event_type, EventType.THREAD_FORK.value]
            )
        )
        messages_with_events.extend(messages_for_thread.messages)

        # Process any thread_fork events
        try:
            for msg in messages_for_thread.messages:
                events = msg.events if msg.events else []
                for event in events:
                    if event.type == EventType.THREAD_FORK.value:
                        event_data = ThreadForkEventData.model_validate(event.data)
                        forked_thread: ThreadRelationsResponse = (
                            self.fetch_thread_messages_and_events_for_message(
                                event_data.previous_message_id, [event_type]
                            )
                        )
                        messages_with_events.extend(forked_thread.messages)
        except Exception as e:  # pylint: disable=broad-except
            logging.exception(
                "Failed to fetch forked thread messages for message %s: %s",
                message_id,
                e,
            )

        messages_with_events.sort(key=lambda x: x.ts)
        return messages_with_events

    def fetch_thread_messages_and_events_for_message(
        self, message_id: str, event_types: list[str]
    ) -> ThreadRelationsResponse:
        """Fetch messages sorted by timestamp and events for agent context"""
        message_url = f"{self.base_url}/interaction/v1/search/message"
        request_body = self._thread_lookup_request(message_id, event_types=event_types)
        response = requests.post(
            message_url,
            json=request_body,
            headers=self.headers,
            timeout=self.timeout,
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
        """Fetch messages and events for the given thread from the Interactions API"""
        thread_search_url = f"{self.base_url}/interaction/v1/search/thread"
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
            thread_search_url,
            json=request_body,
            headers=self.headers,
            timeout=self.timeout,
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
            self.fetch_thread_messages_and_events_for_message(message_id, [event_type])
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
                    event_data.previous_message_id, [event_type]
                )
            )
            if forked_thread.messages:
                returned_messages.extend(forked_thread.messages)

        returned_messages.sort(key=lambda x: x.ts)

        return returned_messages

    def fetch_events_for_message(
        self,
        message_id: str,
        event_type: Optional[str] = None,
    ) -> dict:
        """Fetch messages and events for the thread containing a given message from the Interactions API"""
        message_search_url = f"{self.base_url}/interaction/v1/search/message"
        request_body = {
            "id": message_id,
            "relations": {
                "events": {"filter": {"type": event_type}} if event_type else {},
            },
        }

        response = requests.post(
            message_search_url,
            json=request_body,
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _channel_lookup_request(channel_id: str, min_timestamp: str) -> dict:
        """Interaction service API request to get threads and messages for a channel"""
        return {
            "id": channel_id,
            "relations": {
                "threads": {
                    "relations": {
                        "messages": {
                            "filter": {"min_timestamp": min_timestamp},
                            "apply_annotations_from_actors": ["*"],
                        }
                    }
                }
            },
        }

    @staticmethod
    def _thread_lookup_request(message_id: str, event_types: list[str]) -> dict:
        """will return all messages for the thread containing the given message and events associated with each message"""
        return {
            "id": message_id,
            "relations": {
                "thread": {
                    "relations": {
                        "messages": {
                            "relations": {"events": {"filter": {"type": event_types}}},
                            "apply_annotations_from_actors": ["*"],
                        },
                    }
                }
            },
        }

    @staticmethod
    def prod() -> "InteractionsService":
        return InteractionsService(
            base_url="https://s2ub.prod.s2.allenai.org/service/noraretrieval",
            timeout=30,
            token=InteractionsService._fetch_bearer_token(
                "nora/prod/interaction-bearer-token"
            ),
        )

    @staticmethod
    def dev() -> "InteractionsService":
        return InteractionsService(
            base_url="https://s2ub.dev.s2.allenai.org/service/noraretrieval",
            timeout=30,
            token=InteractionsService._fetch_bearer_token(
                "nora/dev/interaction-bearer-token"
            ),
        )

    @staticmethod
    def _fetch_bearer_token(secret_id: str) -> str:
        import boto3

        secrets_manager = boto3.client("secretsmanager", region_name="us-west-2")
        return json.loads(
            secrets_manager.get_secret_value(SecretId=secret_id)["SecretString"]
        )["token"]
