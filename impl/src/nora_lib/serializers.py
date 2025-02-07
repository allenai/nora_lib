from datetime import datetime
from uuid import UUID

from pydantic import PlainSerializer
from typing_extensions import Annotated

UuidWithSerializer = Annotated[UUID, PlainSerializer(lambda x: str(x), return_type=str)]
DatetimeWithSerializer = Annotated[
    datetime, PlainSerializer(lambda x: x.isoformat(), return_type=str)
]
