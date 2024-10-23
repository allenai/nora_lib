import os
import unittest

from nora_lib.interactions.interactions_service import InteractionsService
from nora_lib.interactions.models import *
from uuid import uuid4

ACTOR = uuid4()
THREAD = str(uuid4())
CHANNEL = str(uuid4())


def _msg(text: str):
    return Message(
        message_id=str(uuid4()),
        actor_id=ACTOR,
        text=text,
        channel_id=CHANNEL,
        thread_id=THREAD,
        surface=Surface.WEB,
        ts=datetime.now(),
    )


def _event(msg: Message, event_type: str, data: dict):
    return Event(
        type=event_type,
        actor_id=ACTOR,
        timestamp=datetime.now(),
        text="",
        data=data,
        message_id=msg.message_id,
    )


class TestInteractionsService(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.iservice = InteractionsService(
            os.getenv("INTERACTION_STORE_URL", "http://interaction_service:9080"),
            token="test",
        )

    def test_save_message(self):
        message = _msg("Hi")
        self.iservice.save_message(message)
        returned_message = self.iservice.get_message(message.message_id)
        self.assertEqual(returned_message.text, message.text)

    def test_virtual_thread(self):
        virtual_thread_1 = "virtual_thread_1"
        virtual_thread_2 = "virtual_thread_2"
        msg1 = _msg("Hi 1")
        msg2 = _msg("Hi 2")
        self.iservice.save_message(msg1)
        self.iservice.save_message(msg2, virtual_thread_1)
        event1 = _event(msg2, "event1", {})
        event2 = _event(msg2, "event2", {})
        event3 = _event(msg2, "event3", {})
        e_id = self.iservice.save_event(event1)
        self.iservice.save_event(event2, virtual_thread_1)
        self.iservice.save_event(event3, virtual_thread_2)
        returned_event = self.iservice.get_event(e_id)

        content = self.iservice.get_virtual_thread_content(
            msg2.message_id, virtual_thread_1
        )
        self.assertIsNotNone(returned_event)
        # Should only contain the one message tagged with virtual_thread_1
        self.assertEqual([m.message_id for m in content], [msg2.message_id])
        # Should only contain the events tagged with virtual_thread_1
        self.assertEqual([e.type for e in content[0].events], [event2.type])

    def test_save_event(self):
        message = _msg("Hi")
        self.iservice.save_message(message)
        event = _event(message, "event", {"key": "value"})
        event_id = self.iservice.save_event(event)
        returned_event = self.iservice.get_event(event_id)
        self.assertEqual(returned_event.data, event.data)
        self.assertEqual(returned_event.type, event.type)
