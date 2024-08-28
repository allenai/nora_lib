from typing import Dict, Any, Iterator

import os
import json
import requests

from pydantic import BaseModel


class PubsubService:
    """Client for Nora pubsub backend"""

    def __init__(self, base_url: str, namespace: str):
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
            f"{self.base_url}/subscribe/webhook/{self.namespace}:{topic}", json=body
        )

    def unsubscribe_webhook(self, topic: str, url: str):
        """
        Remove a webhook subscriber from a topic
        """
        body = {"url": url}
        requests.post(
            f"{self.base_url}/unsubscribe/webhook/{self.namespace}:{topic}", json=body
        )

    def subscribe_sse(self, topic: str) -> Iterator[str]:
        """
        Subscribe to a topic using Server-Sent Events
        Returns an iterator that yields message payloads as they are published
        """
        response = requests.get(
            f"{self.base_url}/subscribe/sse/{self.namespace}:{topic}", stream=True
        )
        for line in response.iter_lines():
            if line and line.startswith(b"data:"):
                payload = line[5:].decode("utf-8").strip()
                if payload:
                    yield json.loads(payload)

    def publish(self, topic: str, payload: Dict[str, Any]):
        """
        Publish a message to a topic
        """
        ns_topic = f"{self.namespace}:{topic}"
        event = PublishedEvent(topic=ns_topic, payload=payload)
        requests.post(f"{self.base_url}/publish/{ns_topic}", json=event.model_dump())

    @staticmethod
    def from_env() -> "PubsubService":
        return PubsubService(
            base_url=os.getenv("PUBSUB_URL", "https://http://localhost:8080"),
            namespace=os.getenv("PUBSUB_NAMESPACE", os.getenv("ENV", "prod")),
        )


class PublishedEvent(BaseModel):
    topic: str
    payload: Dict[str, Any]
