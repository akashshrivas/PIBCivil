"""
common.py
=========
Shapes shared across endpoints, so every paginated list in this API
looks the same to a client.
"""

from typing import Generic, List, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    limit: int
    offset: int