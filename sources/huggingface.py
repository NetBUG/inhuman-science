from __future__ import annotations

import logging

import requests

import config
from sources.base import ContentItem

logger = logging.getLogger(__name__)

HF_API_URL = "https://huggingface.co/api/daily_papers"


def fetch_hf_daily_papers(
    min_upvotes: int = 10,
    limit: int = 50,
) -> list[ContentItem]:
    """Fetch today's papers from Hugging Face Daily Papers, filtered by upvotes."""
    try:
        resp = requests.get(
            HF_API_URL,
            params={"limit": limit},
            timeout=30,
            headers={"User-Agent": "InhumanScience/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.exception("Failed to fetch HF daily papers")
        return []

    items: list[ContentItem] = []
    for entry in data:
        paper = entry.get("paper", {})
        upvotes = paper.get("upvotes", 0)
        if upvotes < min_upvotes:
            continue

        paper_id = paper.get("id", "")
        if not paper_id:
            continue

        authors = [a.get("name", "") for a in paper.get("authors", []) if a.get("name")]
        org = entry.get("organization", {})
        orgs = [org["fullname"]] if org and org.get("fullname") else []

        items.append(
            ContentItem(
                content_id=paper_id,
                source_type="paper",
                source_name="hf_daily",
                title=paper.get("title", ""),
                summary=paper.get("summary", "")[:2000],
                url=f"https://arxiv.org/abs/{paper_id}",
                likes=upvotes,
                authors=authors,
                organizations=orgs,
                pdf_url=f"{config.ARXIV_PDF_BASE}{paper_id}",
            )
        )

    items.sort(key=lambda p: p.likes, reverse=True)
    logger.info("HF Daily Papers: %d papers with >= %d upvotes", len(items), min_upvotes)
    return items
