from typing import Optional

from nora_lib.impl.interactions.interactions_service import InteractionsService
from nora_lib.impl.interactions.models import ReturnedMessage


class ContextService:
    """
    Save and retrieve task agent context from interaction store
    """

    def __init__(
        self,
        agent_actor_id: str,  # uuid representing this agent in interaction store
        interactions_base_url: str,
        interactions_bearer_token: Optional[str],
        timeout: int = 30,
    ):
        # If no config is provided, load the configuration based on the environment
        self.interactions_service = self._get_interactions_service(
            interactions_base_url, interactions_bearer_token, timeout
        )
        self.agent_actor_id = agent_actor_id

    def _get_interactions_service(self, url, token, timeout) -> InteractionsService:
        return InteractionsService(url, timeout, token)

    def get_message(self, message_id: str) -> str:
        message: ReturnedMessage = self.interactions_service.get_message(message_id)
        if message.annotated_text:
            return message.annotated_text
        else:
            return message.text
