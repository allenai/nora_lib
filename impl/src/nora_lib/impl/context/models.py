from typing import Optional
from pydantic import BaseModel, Field


class WrappedTaskObject(BaseModel):
    """Encloses request or response object with additional metadata"""

    message_id: str = Field(
        description="id of originating message; key for istore retrieval"
    )
    data: dict = Field(description="Tool-defined request or response")
