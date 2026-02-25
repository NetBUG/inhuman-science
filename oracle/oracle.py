from __future__ import annotations

import json
import logging
import re

import requests

import config
from llm.client import oracle_score, fact_check
from sources.base import ContentItem
from storage.state import save_oracle_decision, get_recent_titles, get_recent_published

logger = logging.getLogger(__name__)

_SCORE_PROMPT = """\
You are an expert AI/ML content curator for a technical science channel. \
The channel ONLY covers hard science and engineering breakthroughs in AI/ML.

== PUBLISH (high score) ==
- New models, architectures, or training methods
- Novel agents, reasoning systems, tool-use approaches
- Significant benchmark results or capability demonstrations
- New open-source releases (models, frameworks, datasets)
- Infrastructure breakthroughs (inference speedups, new hardware capabilities)
- Important research papers with novel ideas

== DO NOT PUBLISH (score 1-3, publish=false) ==
- Politics, regulation, policy debates, government AI initiatives
- Business deals, funding rounds, company valuations, IPOs
- Personal opinions, hot takes, social media drama
- Celebrity/CEO gossip (meetings, coffee chats, lifestyle)
- Job postings, hiring announcements, org reshuffles
- Product marketing without technical substance
- Vague "AI will change the world" think-pieces
- Ethics/safety debates without concrete technical content
- Conference/event announcements without new research

Score from 1 to 10 based on:
- Novelty (genuinely new idea or approach, not incremental)
- Technical depth (concrete methods, results, code — not just announcements)
- Practical impact (changes how people build or use AI)
- Author/org reputation (top lab or well-known researcher)
- Community engagement (likes/upvotes if available)

Content type: {content_type}
Source: {source}
Title: {title}
Likes/engagement: {likes}
Authors/orgs: {authors}

Summary:
{summary}

Respond with ONLY valid JSON:
{{"score": <1-10>, "reason": "<1-2 sentence justification>", "publish": <true/false>}}

Use threshold: publish=true if score >= {threshold}.
"""

_FACT_CHECK_PROMPT = """\
You are a fact-checker for AI/ML news. Verify the following claim or announcement.

Source: {source}
Title: {title}
Content:
{content}

Additional context from the web:
{web_context}

Check:
1. Is this announcement real and from a legitimate source?
2. Are the claimed results or features accurate based on available information?
3. Is this not a duplicate or rehash of old news?

Respond with ONLY valid JSON:
{{"verified": <true/false>, "confidence": <0.0-1.0>, "issues": "<any concerns or empty string>"}}
"""


def evaluate_content(item: ContentItem) -> tuple[float, bool, str]:
    """Score content for interestingness. Returns (score, should_publish, reason)."""
    authors_str = ", ".join(item.authors) if item.authors else ""
    if item.organizations:
        authors_str += " (" + ", ".join(item.organizations) + ")"

    prompt = _SCORE_PROMPT.format(
        content_type=item.source_type,
        source=item.source_name,
        title=item.title,
        likes=item.likes if item.likes else "N/A",
        authors=authors_str or "Unknown",
        summary=item.summary[:2000] or item.title,
        threshold=config.ORACLE_MIN_SCORE,
    )

    try:
        raw = oracle_score(prompt)
        result = _parse_json(raw)
        if result is None:
            return 5.0, False, "Failed to parse oracle response"

        score = float(result.get("score", 5))
        publish = bool(result.get("publish", False))
        reason = result.get("reason", "")

        save_oracle_decision(
            item.content_id,
            item.source_type,
            score,
            "publish" if publish else "skip",
            reason,
        )

        logger.info(
            "Oracle: %s [%s] score=%.1f publish=%s reason=%s",
            item.title[:60], item.source_name, score, publish, reason,
        )
        return score, publish, reason

    except Exception:
        logger.exception("Oracle evaluation failed for %s", item.content_id)
        return 5.0, False, "Oracle error"


def verify_content(item: ContentItem) -> tuple[bool, float, str]:
    """Fact-check a blog post or tweet. Returns (verified, confidence, issues)."""
    web_context = _fetch_web_context(item.url) if item.url else ""

    prompt = _FACT_CHECK_PROMPT.format(
        source=item.source_name,
        title=item.title,
        content=item.summary[:3000],
        web_context=web_context[:5000],
    )

    try:
        raw = fact_check(prompt)
        result = _parse_json(raw)
        if result is None:
            return True, 0.5, "Could not parse fact-check response"

        verified = bool(result.get("verified", True))
        confidence = float(result.get("confidence", 0.5))
        issues = result.get("issues", "")

        logger.info(
            "Fact-check: %s verified=%s confidence=%.2f issues=%s",
            item.title[:60], verified, confidence, issues,
        )
        return verified, confidence, issues

    except Exception:
        logger.exception("Fact-check failed for %s", item.content_id)
        return True, 0.3, "Fact-check error"


_DEDUP_PROMPT = """\
I'm about to publish a new post. Check if it covers the SAME topic/news as any \
of the recently published items listed below.

New post title: {new_title}
New post summary: {new_summary}

Recently published:
{recent_list}

Is the new post about the same specific topic (same paper, same product launch, \
same announcement) as any of the recent items? Minor thematic overlap is OK — \
only flag if it's literally the same news from a different source.

Respond ONLY with JSON: {{"is_duplicate": <true/false>, "duplicate_of": "<which item or empty>"}}
"""


def is_duplicate(item: ContentItem) -> tuple[bool, str]:
    """Check if content is a duplicate of something recently published."""
    recent = get_recent_titles(days=3, limit=20)
    if not recent:
        return False, ""

    recent_list = "\n".join(f"- {t}" for t in recent)
    prompt = _DEDUP_PROMPT.format(
        new_title=item.title,
        new_summary=item.summary[:500],
        recent_list=recent_list,
    )

    try:
        raw = oracle_score(prompt)
        data = _parse_json(raw)
        if data:
            is_dup = bool(data.get("is_duplicate", False))
            dup_of = data.get("duplicate_of", "")
            if is_dup:
                logger.info("Duplicate detected: '%s' ~ '%s'", item.title[:60], dup_of)
            return is_dup, dup_of
    except Exception:
        logger.exception("Dedup check failed for %s", item.content_id)

    return False, ""


_BATCH_DEDUP_PROMPT = """\
You are deduplicating a batch of AI/ML content items before publication.

== RECENTLY PUBLISHED (do NOT republish these topics) ==
{recent_list}

== NEW CANDIDATES ==
{candidates_list}

Instructions:
1. Remove any candidate that covers the SAME specific news/announcement/paper \
as a recently published item. Minor thematic overlap is fine — only remove if \
it's literally the same news from a different source.
2. Among the remaining candidates, group any that cover the same specific topic.
3. From each group, keep ONLY the one with the highest score.
4. Return the numbers of candidates to KEEP.

Respond ONLY with valid JSON: {{"keep": [<list of candidate numbers to keep>]}}
"""


def deduplicate_batch(
    candidates: list[tuple[ContentItem, float]],
) -> list[tuple[ContentItem, float]]:
    """Deduplicate candidates against history and each other in one LLM call.

    Returns the filtered list of (item, score) tuples to publish.
    """
    if len(candidates) <= 1:
        if not candidates:
            return []
        item, score = candidates[0]
        dup, _ = is_duplicate(item)
        return [] if dup else candidates

    recent = get_recent_published(days=5, limit=50)
    if recent:
        recent_list = "\n".join(
            f"- [{r['source_name']}] {r['title']}"
            for r in recent if r.get("title")
        )
    else:
        recent_titles = get_recent_titles(days=5, limit=50)
        recent_list = "\n".join(f"- {t}" for t in recent_titles) if recent_titles else "(none)"

    candidates_list = "\n".join(
        f"{i+1}. [score={score:.1f}, source={item.source_name}] "
        f"{item.title}\n   Summary: {item.summary[:200]}"
        for i, (item, score) in enumerate(candidates)
    )

    prompt = _BATCH_DEDUP_PROMPT.format(
        recent_list=recent_list or "(none)",
        candidates_list=candidates_list,
    )

    try:
        raw = oracle_score(prompt)
        data = _parse_json(raw)
        if data and "keep" in data:
            keep_indices = set(int(x) - 1 for x in data["keep"])
            result = [
                candidates[i]
                for i in sorted(keep_indices)
                if 0 <= i < len(candidates)
            ]
            removed = len(candidates) - len(result)
            if removed:
                logger.info(
                    "Batch dedup: %d candidates -> %d kept (%d removed)",
                    len(candidates), len(result), removed,
                )
            return result
    except Exception:
        logger.exception("Batch dedup failed, keeping all candidates")

    return candidates


def _fetch_web_context(url: str) -> str:
    """Fetch page content for fact-checking context."""
    try:
        resp = requests.get(
            url, timeout=15,
            headers={"User-Agent": "InhumanScience/1.0"},
        )
        resp.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:5000]
    except Exception:
        logger.debug("Could not fetch web context from %s", url)
        return ""


def _parse_json(raw: str) -> dict | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None
