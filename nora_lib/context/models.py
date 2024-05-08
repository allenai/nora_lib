from typing import Generic, Optional, TypeVar
from pydantic import BaseModel, Field


R = TypeVar("R", bound=BaseModel)


class WrappedTaskObject(BaseModel, Generic[R]):
    """Encloses request or response object with additional metadata"""

    message_id: str = Field(
        description="id of originating message; key for istore retrieval"
    )
    sender_actor_id: str = Field(
        description="string representation of uuid identifying agent sending data"
    )
    virtual_thread_id: Optional[str] = Field(
        description="Tool-defined local thread to associate follow up requests"
    )
    task_id: Optional[str] = Field(description="Reference to a long-running task")
    data: Optional[R] = Field(description="Tool-defined request or response")
