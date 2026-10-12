"""
routers/articles.py
====================
GET /articles              -- paginated list, with optional filters
GET /articles/{article_id} -- one article + its summary, in one query
GET /articles/by-release/{release_id} -- same, looked up by PRID
"""

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from postgrest.exceptions import APIError
from supabase import Client

from ..db import get_client
from ..schemas.article import ArticleDetail, ArticleListItem
from ..schemas.common import Page

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=Page[ArticleListItem])
def list_articles(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ministry: Optional[str] = None,
    published_after: Optional[date] = None,
    published_before: Optional[date] = None,
    search: Optional[str] = Query(None, description="Matches against the title"),
    order: Literal["newest", "oldest"] = "newest",
    client: Client = Depends(get_client),
):
    # count="exact" asks Postgres for the total matching row count
    # alongside the page of data, so the client can build "page X of Y"
    # without a second request. The article_summaries(keywords) embed
    # pulls just the keywords -- not the whole summary -- so the list
    # endpoint stays light while still giving the grid its chip row.
    query = client.table("articles").select(
        "*, article_summaries(keywords)", count="exact"
    )

    if ministry:
        query = query.eq("ministry", ministry)
    if published_after:
        query = query.gte("published_on", published_after.isoformat())
    if published_before:
        query = query.lte("published_on", published_before.isoformat())
    if search:
        # ilike = case-insensitive LIKE; the %...% makes it "contains".
        # Uses the pg_trgm GIN index already on articles.title.
        query = query.ilike("title", f"%{search}%")

    query = query.order("published_on", desc=(order == "newest")).range(
        offset, offset + limit - 1
    )

    result = query.execute()

    return Page(
        items=[ArticleListItem.from_row(row) for row in result.data],
        total=result.count or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/filters/ministries", response_model=list[str])
def list_ministries(client: Client = Depends(get_client)):
    """
    Distinct ministry names currently in use -- powers the Ministry
    filter dropdown with real values instead of a hardcoded list that
    would drift out of sync with the data.
    """
    result = (
        client.table("articles")
        .select("ministry")
        .not_.is_("ministry", "null")
        .execute()
    )
    # Supabase has no SELECT DISTINCT in the client -- dedupe here.
    ministries = sorted({row["ministry"] for row in result.data if row["ministry"]})
    return ministries


@router.get("/by-release/{release_id}", response_model=ArticleDetail)
def get_article_by_release_id(release_id: str, client: Client = Depends(get_client)):
    return _fetch_one(client, "release_id", release_id)


@router.get("/{article_id}", response_model=ArticleDetail)
def get_article(article_id: str, client: Client = Depends(get_client)):
    return _fetch_one(client, "id", article_id)


def _fetch_one(client: Client, column: str, value: str) -> ArticleDetail:
    """
    Shared by both lookup routes. "*, article_summaries(*)" follows the
    foreign key from articles to article_summaries automatically, so
    this is ONE round trip to Postgres instead of two separate queries.
    """
    try:
        result = (
            client.table("articles")
            .select("*, article_summaries(*)")
            .eq(column, value)
            .single()
            .execute()
        )
    except APIError as e:
        # PostgREST raises when .single() finds zero rows (or more than
        # one, which shouldn't happen given the unique constraints).
        raise HTTPException(status_code=404, detail="Article not found") from e

    return ArticleDetail.from_row(result.data)