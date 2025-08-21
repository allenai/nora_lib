import logging
from typing import Dict, Any, Iterator, Optional
from contextlib import contextmanager

import os
import json
import requests
import signal
from time import sleep

from pydantic import BaseModel


class PubsubService:
    """Client for Nora pubsub backend"""

    def __init__(self, base_url: str, namespace: Optional[str] = None):
        """
        :param base_url: pubsub API URL
        :param namespace: Topic namespace
        """
        self.base_url = base_url
        self.namespace = namespace

    def subscribe_webhook(self, topic: str, url: str):
        """
        Add a webhook subscriber to a topic
        The webhook will receive a POST request whenever any client calls publish() on the topic
        """
        body = {"url": url}
        requests.post(
            f"{self.base_url}/subscribe/webhook/{self._fully_qualified_topic(topic)}",
            json=body,
        )

    def unsubscribe_webhook(self, topic: str, url: str):
        """
        Remove a webhook subscriber from a topic
        """
        body = {"url": url}
        requests.post(
            f"{self.base_url}/unsubscribe/webhook/{self._fully_qualified_topic(topic)}",
            json=body,
        )

    @contextmanager
    def subscribe_sse(self, topic: str) -> Iterator[str]:
        """
        Subscribe to a topic using Server-Sent Events
        Returns an iterator that yields message payloads as they are published
        Will close the underlying HTTP connection when the context manager exits

        Usage:

        # This will run indefinitely
        with pubsub_service.subscribe_sse("my_topic") as messages:
             for message in messages:
                    handle(message)

        # This will run in the background, exiting after one minute
        with pubsub_service.subscribe_sse("my_topic") as messages:
            def run():
                for message in messages:
                    handle(message)
            threading.Thread(target=run).start()

            sleep(60)
        """
        open_connections = []
        running = True

        def msgs():
            delay = 1
            while running:
                try:
                    response = requests.get(
                        f"{self.base_url}/subscribe/sse/{self._fully_qualified_topic(topic)}",
                        stream=True,
                    )
                    open_connections.append(response)
                    delay = 1
                    for line in response.iter_lines():
                        if line and line.startswith(b"data:"):
                            payload = line[5:].decode("utf-8").strip()
                            if payload:
                                yield json.loads(payload)
                except requests.exceptions.ConnectionError:
                    logging.warning(
                        "Unable to establish server connection at %s. Sleeping for %ss",
                        self.base_url,
                        delay,
                    )
                    try:
                        open_connections.pop().close()
                    except Exception:
                        pass
                    # Possible misconfiguration. Back off exponentially
                    sleep(delay)
                    delay = min(delay * 2, 60)
                except requests.exceptions.RequestException:
                    logging.warning("Server at %s closed SSE connection", self.base_url)
                    try:
                        open_connections.pop().close()
                    except Exception:
                        pass
                    # Service may have redeployed. Try to reestablish connection quickly
                    sleep(1)

        try:
            yield msgs()
        finally:
            running = False
            for conn in open_connections:
                try:
                    conn.close()
                except Exception:
                    pass

    def publish(self, topic: str, payload: Dict[str, Any]):
        """
        Publish a message to a topic
        """
        ns_topic = self._fully_qualified_topic(topic)
        event = PublishedEvent(topic=ns_topic, payload=payload)
        requests.post(f"{self.base_url}/publish/{ns_topic}", json=event.model_dump())

    def _fully_qualified_topic(self, topic: str) -> str:
        return f"{self.namespace}:{topic}" if self.namespace else topic

    @staticmethod
    def from_env() -> "PubsubService":
        return PubsubService(
            base_url=os.getenv("PUBSUB_URL", "http://localhost:8080"),
            namespace=os.getenv("PUBSUB_NAMESPACE", os.getenv("ENV", "prod")),
        )


class PublishedEvent(BaseModel):
    topic: str
    payload: Dict[str, Any]
