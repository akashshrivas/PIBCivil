"""
article.py
==========
Response models. Deliberately NOT identical to the raw Supabase row --
e.g. article_summaries comes back from Supabase as a list (because of
the foreign-key embed) even though in practice there's one summary per
article right now, so we collapse it to a single optional field here.
"""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class ArticleSummary(BaseModel):
    summary: str
    important_facts: List[str] = []
    keywords: List[str] = []
    model: str
    prompt_version: str


class ArticleListItem(BaseModel):
    id: str
    release_id: str
    title: str
    ministry: Optional[str] = None
    published_on: date
    url: Optional[str] = None
    keywords: List[str] = []

    @classmethod
    def from_row(cls, row: dict) -> "ArticleListItem":
        # article_summaries comes back as a list because of the FK embed;
        # take the first summary's keywords, capped to a few for a card chip row.
        summaries = row.get("article_summaries") or []
        keywords = summaries[0]["keywords"] if summaries else []

        return cls(
            id=row["id"],
            release_id=row["release_id"],
            title=row["title"],
            ministry=row.get("ministry"),
            published_on=row["published_on"],
            url=row.get("url"),
            keywords=keywords[:3],
        )


class ArticleDetail(ArticleListItem):
    summary: Optional[ArticleSummary] = None

    @classmethod
    def from_row(cls, row: dict) -> "ArticleDetail":
        # Supabase returns the embedded relation as a list under the
        # table name -- take the first summary if one exists.
        summaries = row.get("article_summaries") or []
        summary = ArticleSummary(**summaries[0]) if summaries else None

        return cls(
            id=row["id"],
            release_id=row["release_id"],
            title=row["title"],
            ministry=row.get("ministry"),
            published_on=row["published_on"],
            url=row.get("url"),
            summary=summary,
        )