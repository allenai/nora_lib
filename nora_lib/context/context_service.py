from typing import Optional

from nora_lib.interactions.interactions_service import InteractionsService
from nora_lib.interactions.models import ReturnedMessage
from nora_lib.interactions.config import Config


class ContextService:
    """
    Save and retrieve task agent context from interaction store
    """

    def __init__(
        self,
        agent_actor_id: str,  # uuid representing this agent in interaction store
        config: Optional[Config] = None,
    ):
        # If no config is provided, load the configuration based on the environment
        self.config = config if config else Config.from_env()

        self.interactions_service = self._get_interactions_service()
        self.agent_actor_id = agent_actor_id

    def _get_interactions_service(self) -> InteractionsService:
        return InteractionsService(self.config)

    def get_message(self, message_id: str) -> str:
        message: ReturnedMessage = self.interactions_service.get_message(message_id)
        if message.annotated_text:
            return message.annotated_text
        else:
            return message.text
