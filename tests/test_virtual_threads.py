import unittest

from nora_lib.interactions.interactions_service import InteractionsService
from nora_lib.interactions.models import *
from uuid import uuid4

ACTOR = uuid4()
THREAD = str(uuid4())
CHANNEL = str(uuid4())


def _msg(text):
    return Message(
        message_id=str(uuid4()),
        actor_id=ACTOR,
        text=text,
        channel_id=CHANNEL,
        thread_id=THREAD,
        surface=Surface.WEB,
        ts=datetime.now(),
    )


def _event(msg: Message, type: str, data: dict):
    return Event(
        type=type,
        actor_id=ACTOR,
        timestamp=datetime.now(),
        text="",
        data=data,
        message_id=msg.message_id,
    )


@unittest.skip("Requires a local instance of the interactions service")
class TestVirtualThreads(unittest.TestCase):
    def setUp(self):
        self.svc = InteractionsService("http://localhost:8080", 30, None)

    def test_placeholder(self):
        virtual_thread_1 = "virtual_thread_1"
        virtual_thread_2 = "virtual_thread_2"
        msg1 = _msg("Hi 1")
        msg2 = _msg("Hi 2")
        self.svc.save_message(msg1)
        self.svc.save_message(msg2, virtual_thread_1)
        event1 = _event(msg2, "event1", {})
        event2 = _event(msg2, "event2", {})
        event3 = _event(msg2, "event3", {})
        self.svc.save_event(event1)
        self.svc.save_event(event2, virtual_thread_1)
        self.svc.save_event(event3, virtual_thread_2)

        content = self.svc.get_virtual_thread_content(msg2.message_id, virtual_thread_1)
        # Should only contain the one message tagged with virtual_thread_1
        self.assertEqual([m.message_id for m in content], [msg2.message_id])
        # Should only contain the events tagged with virtual_thread_1
        self.assertEqual([e.type for e in content[0].events], [event2.type])
