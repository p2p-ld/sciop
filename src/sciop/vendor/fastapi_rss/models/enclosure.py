from typing import Optional
from pydantic import BaseModel


class EnclosureAttrs(BaseModel):
    url: str
    length: Optional[int] = None
    type: str


class Enclosure(BaseModel):
    attrs: EnclosureAttrs
