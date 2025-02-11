from typing import Optional

from pydantic import BaseModel


class SuccessResponse(BaseModel):
    success: bool
    extra: Optional[dict] = None
