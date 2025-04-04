import datetime
from typing import Optional

from sciop.vendor.fastapi_rss.models.category import Category
from sciop.vendor.fastapi_rss.models.enclosure import Enclosure
from sciop.vendor.fastapi_rss.models.guid import GUID
from sciop.vendor.fastapi_rss.models.itunes import Itunes
from sciop.vendor.fastapi_rss.models.source import Source
from pydantic import BaseModel


class Item(BaseModel):
    title: str
    link: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    category: Optional[Category] = None
    comments: Optional[str] = None
    enclosure: Optional[Enclosure] = None
    guid: Optional[GUID] = None
    pub_date: Optional[datetime.datetime] = None
    source: Optional[Source] = None
    itunes: Optional[Itunes] = None
