import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

import boto3
import requests
from requests import Response
from requests.auth import AuthBase
from retry import retry

from nora_lib.impl.interactions.models import (
    AnnotationBatch,
    Event,
    EventType,
    Message,
    ReturnedMessage,
    StepCost,
    Thread,
    ThreadRelationsResponse,
    ThreadStatus,
    VirtualThread,
)


class RetryableInteractionStoreException(Exception):
    # We'll use this to indicate which requests can be retried.
    def __init__(self, message: str, response: Response):
        super().__init__(message)
        # Carry this along in case our last try fails.
        self.response = response


@dataclass
class RetryConfig:
    # By default, we won't retry (so 1 try total).
    # All the other defaults are to make it so that
    # if we do retry (changing 'tries'), and don't change
    # anything else, we retry with exponential backoff
    # and some jitter.
    tries: int = 1
    delay: int = 1
    max_delay: Optional[int] = None
    backoff: int = 2
    jitter: Union[int, Tuple[int, int]] = (1, 2)


class InteractionsService:
    """
    Service which saves interactions to the Interactions API
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        token: Optional[str] = None,
        auth: Optional[AuthBase] = None,
        retry_config: RetryConfig = RetryConfig(),
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.auth = auth
        if token:
            self.auth = BearerAuth(token)
        self.retry_config = retry_config

    def _call(
        self, method: str, url: str, json: Optional[Dict[str, Any]] = None
    ) -> Response:

        @retry(
            RetryableInteractionStoreException,
            tries=self.retry_config.tries,
            delay=self.retry_config.delay,
            max_delay=self.retry_config.max_delay,
            backoff=self.retry_config.backoff,
            jitter=self.retry_config.jitter,
        )
        def call_helper():
            response = requests.request(
                method=method,
                url=url,
                json=json,
                auth=self.auth,
                timeout=self.timeout,
            )
            if response.status_code >= 500:
                raise RetryableInteractionStoreException(
                    f"Encountered a retryable exception, status code {response.status_code}",
                    response,
                )
            else:
                return response

        try:
            return call_helper()
        except RetryableInteractionStoreException as exc:
            # If our last try failed, return the response and let the caller decide
            # what to do with it.
            return exc.response

    def save_message(
        self, message: Message, virtual_thread_id: Optional[str] = None
    ) -> None:
        """
        Save a message to the Interaction Store
        :param virtual_thread_id: Optional ID of a virtual thread to associate with the message
        """
        message_url = f"{self.base_url}/interaction/v1/message"
        response = self._call(
            "post",
            message_url,
            message.model_dump(),
        )
        response.raise_for_status()
        if virtual_thread_id:
            # Use an event to tag the message with the virtual thread ID
            event = Event(
                type=VirtualThread.EVENT_TYPE,
                actor_id=message.actor_id,
                message_id=message.message_id,
                data={
                    VirtualThread.ID_FIELD: virtual_thread_id,
                    VirtualThread.EVENT_TYPE_FIELD: VirtualThread.EVENT_TYPE,
                },
                timestamp=message.ts,
            )
            self.save_event(event)

    def save_event(self, event: Event, virtual_thread_id: Optional[str] = None) -> str:
        """
        Save an event to the Interaction Store. Returns an event id.
        :param virtual_thread_id: Optional ID of a virtual thread to associate with the event
        """
        if event.event_id:
            event_url = f"{self.base_url}/interaction/v1/event/{event.event_id}"
            method = "patch"
        else:
            event_url = f"{self.base_url}/interaction/v1/event"
            method = "post"

        response = self._call(
            method,
            event_url,
            event.model_dump(),
        )
        response.raise_for_status()
        if virtual_thread_id:
            # Use an event to tag the event with the virtual thread ID
            # Attach it to the same message as this event, along with the event type
            event = Event(
                type=VirtualThread.EVENT_TYPE,
                actor_id=event.actor_id,
                message_id=event.message_id,
                data={
                    VirtualThread.ID_FIELD: virtual_thread_id,
                    VirtualThread.EVENT_TYPE_FIELD: event.type,
                },
                timestamp=event.timestamp,
            )
            self.save_event(event)
        response_message = response.json()
        if not event.event_id:
            # If this is a new event, then we should have gotten back its ID.
            event.event_id = response_message["event_id"]
        return event.event_id

    def save_thread(self, thread: Thread) -> None:
        """Save a thread to the Interactions API"""
        thread_url = f"{self.base_url}/interaction/v1/thread"
        response = self._call(
            "post",
            thread_url,
            thread.model_dump(),
        )
        response.raise_for_status()

    def delete_thread(self, thread_id: str) -> None:
        """
        Delete a thread and all its associated data from the Interactions API.
        This performs a hard delete with cascade to remove:
        - All messages in the thread
        - All events associated with the thread or its messages
        - All annotations on messages in the thread
        """
        thread_url = f"{self.base_url}/interaction/v1/thread/{thread_id}"
        response = self._call("delete", thread_url)
        response.raise_for_status()

    def save_message_reaction(
        self, message_id: str, reaction: str, actor_id: UUID
    ) -> str:
        """Save reaction as an event on a message, returns event id if successful"""
        if reaction is None:
            event = Event(
                type=EventType.REACTION_REMOVED.value,
                actor_id=actor_id,
                timestamp=datetime.now(timezone.utc),
                message_id=message_id,
            )
        else:
            event = Event(
                type=EventType.REACTION_ADDED.value,
                actor_id=actor_id,
                timestamp=datetime.now(timezone.utc),
                text=reaction,
                message_id=message_id,
            )

        return self.save_event(event)

    def save_message_feedback(
        self, message_id: str, feedback: str, actor_id: UUID
    ) -> str:
        """Save feedback as an event on a message, returns event id if successful"""
        event = Event(
            type=EventType.USER_FEEDBACK.value,
            actor_id=actor_id,
            timestamp=datetime.now(timezone.utc),
            text=feedback,
            message_id=message_id,
        )

        return self.save_event(event)

    def save_thread_feedback(
        self, thread_id: str, feedback: str, actor_id: UUID
    ) -> str:
        """Save feedback as an event on a thread, returns event id if successful"""
        event = Event(
            type=EventType.USER_FEEDBACK_THREAD.value,
            actor_id=actor_id,
            timestamp=datetime.now(timezone.utc),
            text=feedback,
            thread_id=thread_id,
        )

        return self.save_event(event)

    def get_virtual_thread_content(
        self, message_id: str, virtual_thread_id: str
    ) -> List[ReturnedMessage]:
        """Fetch all messages and events in a virtual thread
        Returns all messages and events in the same thread as the given message,
        but filtered to only include those associated with the given virtual thread.
        :param message_id: The ID of a message in the virtual thread
        :param virtual_thread_id: The ID of the virtual thread
        """
        message_search_url = f"{self.base_url}/interaction/v1/search/message"
        # Fetch all events and filter on the client side
        # Need an IStore schema change to do this server-side
        request_body = {
            "id": message_id,
            "relations": {
                "preceding_messages": {
                    "max": 100,
                    "relations": {"events": {}},
                },
                "events": {},
            },
        }

        response = self._call(
            "post",
            message_search_url,
            request_body,
        )
        response.raise_for_status()
        result = ReturnedMessage.model_validate(response.json()["message"])
        all_messages = result.preceding_messages + [result]
        virtual_thread_content = []
        for msg in all_messages:
            event_types_in_virtual_thread = set(
                event.data[VirtualThread.EVENT_TYPE_FIELD]
                for event in msg.events
                if event.type == VirtualThread.EVENT_TYPE
                and event.data.get(VirtualThread.ID_FIELD) == virtual_thread_id
            )
            if not event_types_in_virtual_thread:
                continue
            virtual_thread_content.append(msg)
            msg.events = [
                event
                for event in msg.events
                if event.type != VirtualThread.EVENT_TYPE
                and event.type in event_types_in_virtual_thread
            ]
            if VirtualThread.EVENT_TYPE not in event_types_in_virtual_thread:
                # An event has been tagged with the virtual thread ID
                # but the message itself is not in the virtual thread
                # Somewhat pathological case, probably shouldn't happen
                # Set the message text to empty string
                msg.text = ""
        return virtual_thread_content

    def save_annotation(self, annotation: AnnotationBatch) -> None:
        """Save an annotation to the Interactions API"""
        annotation_url = f"{self.base_url}/interaction/v1/annotation"
        response = self._call(
            "post",
            annotation_url,
            annotation.model_dump(),
        )
        response.raise_for_status()

    def get_message(self, message_id: str) -> ReturnedMessage:
        """Fetch a message from the Interactions API"""
        message_url = f"{self.base_url}/interaction/v1/search/message"
        request_body = {
            "id": message_id,
            "relations": {"thread": {}, "channel": {}, "events": {}, "annotations": {}},
        }
        response = self._call(
            "post",
            message_url,
            request_body,
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

    def get_event(self, event_id: str) -> Event:
        """Fetch an event from the Interactions API"""
        event_url = f"{self.base_url}/interaction/v1/search/event"
        request_body = {
            "id": event_id,
        }
        response = self._call(
            "post",
            event_url,
            request_body,
        )
        response.raise_for_status()
        res_dict = response.json()["events"][0]
        res = Event.model_validate(res_dict)
        return res

    def fetch_all_threads_by_channel(
        self,
        channel_id: str,
        min_timestamp: Optional[str] = None,
        thread_event_types: Optional[list[str]] = None,
        most_recent: Optional[int] = None,
    ) -> dict:
        """Fetch a message from the Interactions API"""
        message_url = f"{self.base_url}/interaction/v1/search/channel"
        request_body = self._channel_lookup_request(
            channel_id=channel_id,
            min_timestamp=min_timestamp,
            thread_event_types=thread_event_types,
            most_recent=most_recent,
        )
        response = self._call(
            "post",
            message_url,
            request_body,
        )
        response.raise_for_status()
        return response.json()

    def fetch_thread_messages_and_events_for_message(
        self,
        message_id: str,
        event_types: List[str],
        min_timestamp: Optional[str] = None,
        most_recent: Optional[int] = None,
    ) -> ThreadRelationsResponse:
        """Fetch messages sorted by timestamp and events for agent context"""
        message_url = f"{self.base_url}/interaction/v1/search/message"
        request_body = self._thread_lookup_request(
            message_id,
            event_types=event_types,
            min_timestamp=min_timestamp,
            most_recent=most_recent,
        )
        response = self._call(
            "post",
            message_url,
            request_body,
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
        message_query = {
            "filter": {"min_timestamp": min_timestamp} if min_timestamp else None,
            "apply_annotations_from_actors": ["*"],
        }
        request_body = {
            "id": thread_id,
            "relations": {
                "messages": message_query,
                "events": {"filter": {"type": event_type}} if event_type else {},
            },
        }

        response = self._call(
            "post",
            thread_search_url,
            request_body,
        )
        response.raise_for_status()
        return response.json()

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

        response = self._call(
            "post",
            message_search_url,
            request_body,
        )
        response.raise_for_status()
        return response.json()

    def fetch_all_by_channel(
        self,
        channel_id: str,
        min_timestamp: Optional[str] = None,
        before_timestamp: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        num_most_recent_threads: Optional[int] = None,
        num_most_recent_messages_per_thread: Optional[int] = None,
        num_oldest_messages_per_thread: Optional[int] = None,
        thread_status: List[ThreadStatus] = [ThreadStatus.ACTIVE],
    ) -> dict:
        """
        Fetch all threads, messages, and events including nested ones for a given channel
        """
        channel_search_url = f"{self.base_url}/interaction/v1/search/channel"
        thread_filter_query = {
            "status": thread_status,
            "min_timestamp": min_timestamp if min_timestamp else None,
            "before_timestamp": before_timestamp if before_timestamp else None,
            "most_recent": num_most_recent_threads if num_most_recent_threads else None,
        }
        event_query = {"filter": None if event_types is None else {"type": event_types}}
        message_filter_query = {
            "min_timestamp": min_timestamp if min_timestamp else None,
            "most_recent": (
                num_most_recent_messages_per_thread
                if num_most_recent_messages_per_thread
                else None
            ),
            "oldest": (
                num_oldest_messages_per_thread
                if num_oldest_messages_per_thread
                else None
            ),
        }
        message_query = {
            "relations": {"events": event_query, "annotations:": {}},
            "filter": message_filter_query,
            "apply_annotations_from_actors": ["*"],
        }
        request_body = {
            "id": channel_id,
            "relations": {
                "threads": {
                    "filter": thread_filter_query,
                    "relations": {
                        "messages": message_query,
                        "events": event_query,
                    },
                },
            },
        }
        response = self._call(
            "post",
            channel_search_url,
            request_body,
        )
        response.raise_for_status()
        return response.json()

    def fetch_all_by_thread(
        self,
        thread_id: str,
        min_timestamp: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        most_recent: Optional[int] = None,
    ) -> dict:
        """
        Fetch all messages and events including nested ones for a given thread
        """
        thread_search_url = f"{self.base_url}/interaction/v1/search/thread"
        event_query = {"filter": None if event_types is None else {"type": event_types}}
        message_filter_query = {
            "min_timestamp": min_timestamp if min_timestamp else None,
            "most_recent": most_recent if most_recent else None,
        }
        message_query = {
            "relations": {"events": event_query, "annotations:": {}},
            "filter": message_filter_query,
            "apply_annotations_from_actors": ["*"],
        }
        request_body = {
            "id": thread_id,
            "relations": {
                "messages": message_query,
                "events": event_query,
            },
        }
        response = self._call(
            "post",
            thread_search_url,
            request_body,
        )
        response.raise_for_status()
        return response.json()

    def report_cost(self, step_cost: StepCost) -> Optional[str]:
        """Save a cost report to the Interactions Store. Returning event id"""
        try:
            return self.save_event(step_cost.to_event())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logging.warning(
                    f"Cannot find message id {step_cost.message_id} to attach cost report to."
                )
                return None
            else:
                raise e

    @staticmethod
    def _channel_lookup_request(
        channel_id: str,
        min_timestamp: Optional[str] = None,
        thread_event_types: Optional[list[str]] = None,
        most_recent: Optional[int] = None,
    ) -> dict:
        """Interaction service API request to get threads and messages for a channel"""
        message_filter_query = {
            "min_timestamp": min_timestamp if min_timestamp else None,
            "most_recent": most_recent if most_recent else None,
        }
        return {
            "id": channel_id,
            "relations": {
                "threads": {
                    "relations": {
                        "messages": {
                            "filter": message_filter_query,
                            "apply_annotations_from_actors": ["*"],
                        },
                        "events": {"filter": {"type": thread_event_types or []}},
                    }
                }
            },
        }

    @staticmethod
    def _thread_lookup_request(
        message_id: str,
        event_types: list[str],
        min_timestamp: Optional[str] = None,
        most_recent: Optional[int] = None,
    ) -> dict:
        """will return all messages for the thread containing the given message and events associated with each message"""
        message_filter_query = {
            "min_timestamp": min_timestamp if min_timestamp else None,
            "most_recent": most_recent if most_recent else None,
        }
        return {
            "id": message_id,
            "relations": {
                "thread": {
                    "relations": {
                        "messages": {
                            "filter": message_filter_query,
                            "relations": {"events": {"filter": {"type": event_types}}},
                            "apply_annotations_from_actors": ["*"],
                        },
                    }
                }
            },
        }

    @staticmethod
    def fetch_bearer_token(secret_id: str) -> str:
        secrets_manager = boto3.client("secretsmanager", region_name="us-west-2")
        return json.loads(
            secrets_manager.get_secret_value(SecretId=secret_id)["SecretString"]
        )["token"]

    @staticmethod
    def from_env() -> "InteractionsService":
        """Load the configuration based on the environment."""
        url = os.getenv(
            "INTERACTION_STORE_URL",
            "http://localhost:8090",
        )
        token = os.getenv(
            "INTERACTION_STORE_TOKEN",
            InteractionsService.fetch_bearer_token(
                "nora/prod/interaction-bearer-token"
            ),
        )

        return InteractionsService(base_url=url, token=token)


class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r
