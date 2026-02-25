from __future__ import annotations

import sqlite3
import logging
from datetime import datetime

import config

logger = logging.getLogger(__name__)

_conn: sqlite3.Connection | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS posted_papers (
    paper_id   TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    title      TEXT,
    posted_at  TEXT NOT NULL,
    tg_msg_id  TEXT,
    tweet_id   TEXT
);

CREATE TABLE IF NOT EXISTS posted_blogs (
    url        TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    title      TEXT,
    posted_at  TEXT NOT NULL,
    tg_msg_id  TEXT,
    tweet_id   TEXT
);

CREATE TABLE IF NOT EXISTS posted_tweets (
    tweet_url  TEXT PRIMARY KEY,
    author     TEXT NOT NULL,
    posted_at  TEXT NOT NULL,
    tg_msg_id  TEXT,
    our_tweet_id TEXT
);

CREATE TABLE IF NOT EXISTS oracle_decisions (
    content_id TEXT PRIMARY KEY,
    content_type TEXT NOT NULL,
    score      REAL,
    decision   TEXT NOT NULL,
    reason     TEXT,
    checked_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS published_summaries (
    content_id   TEXT PRIMARY KEY,
    content_type TEXT NOT NULL,
    source_name  TEXT NOT NULL,
    title        TEXT NOT NULL DEFAULT '',
    summary      TEXT NOT NULL DEFAULT '',
    score        REAL NOT NULL DEFAULT 0,
    published_at TEXT NOT NULL
);
"""


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(config.DB_PATH)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(_SCHEMA)
    return _conn


def is_paper_posted(paper_id: str) -> bool:
    row = get_conn().execute(
        "SELECT 1 FROM posted_papers WHERE paper_id = ?", (paper_id,)
    ).fetchone()
    return row is not None


def mark_paper_posted(
    paper_id: str,
    source: str,
    title: str = "",
    tg_msg_id: str = "",
    tweet_id: str = "",
) -> None:
    get_conn().execute(
        "INSERT OR REPLACE INTO posted_papers VALUES (?, ?, ?, ?, ?, ?)",
        (paper_id, source, title, datetime.utcnow().isoformat(), tg_msg_id, tweet_id),
    )
    get_conn().commit()


def is_blog_posted(url: str) -> bool:
    row = get_conn().execute(
        "SELECT 1 FROM posted_blogs WHERE url = ?", (url,)
    ).fetchone()
    return row is not None


def mark_blog_posted(
    url: str,
    source: str,
    title: str = "",
    tg_msg_id: str = "",
    tweet_id: str = "",
) -> None:
    get_conn().execute(
        "INSERT OR REPLACE INTO posted_blogs VALUES (?, ?, ?, ?, ?, ?)",
        (url, source, title, datetime.utcnow().isoformat(), tg_msg_id, tweet_id),
    )
    get_conn().commit()


def is_tweet_posted(tweet_url: str) -> bool:
    row = get_conn().execute(
        "SELECT 1 FROM posted_tweets WHERE tweet_url = ?", (tweet_url,)
    ).fetchone()
    return row is not None


def mark_tweet_posted(
    tweet_url: str,
    author: str,
    tg_msg_id: str = "",
    our_tweet_id: str = "",
) -> None:
    get_conn().execute(
        "INSERT OR REPLACE INTO posted_tweets VALUES (?, ?, ?, ?, ?)",
        (tweet_url, author, datetime.utcnow().isoformat(), tg_msg_id, our_tweet_id),
    )
    get_conn().commit()


def get_recent_titles(days: int = 5, limit: int = 50) -> list[str]:
    """Get titles of recently published content across all sources."""
    conn = get_conn()
    cutoff = datetime.utcnow().isoformat()[:10]

    rows = conn.execute(
        "SELECT title, summary FROM published_summaries "
        "WHERE published_at > date(?, '-' || ? || ' days') "
        "ORDER BY published_at DESC LIMIT ?",
        (cutoff, str(days), limit),
    ).fetchall()
    if rows:
        return [r["title"] for r in rows if r["title"]]

    titles: list[str] = []
    for table in ("posted_papers", "posted_blogs"):
        rows = conn.execute(
            f"SELECT title FROM {table} WHERE posted_at > date(?, '-' || ? || ' days') "
            f"ORDER BY posted_at DESC LIMIT ?",
            (cutoff, str(days), limit),
        ).fetchall()
        titles.extend(r["title"] for r in rows if r["title"])
    return titles[:limit]


def get_recent_published(days: int = 5, limit: int = 50) -> list[dict]:
    """Get recently published content with title + summary for dedup."""
    conn = get_conn()
    cutoff = datetime.utcnow().isoformat()[:10]
    rows = conn.execute(
        "SELECT content_id, content_type, source_name, title, summary "
        "FROM published_summaries "
        "WHERE published_at > date(?, '-' || ? || ' days') "
        "ORDER BY published_at DESC LIMIT ?",
        (cutoff, str(days), limit),
    ).fetchall()
    return [dict(r) for r in rows]


def save_published_summary(
    content_id: str,
    content_type: str,
    source_name: str,
    title: str,
    summary: str,
    score: float = 0,
) -> None:
    """Store a summary of published content for future dedup checks."""
    get_conn().execute(
        "INSERT OR REPLACE INTO published_summaries VALUES (?, ?, ?, ?, ?, ?, ?)",
        (content_id, content_type, source_name, title,
         summary[:500], score, datetime.utcnow().isoformat()),
    )
    get_conn().commit()


def save_oracle_decision(
    content_id: str,
    content_type: str,
    score: float,
    decision: str,
    reason: str = "",
) -> None:
    get_conn().execute(
        "INSERT OR REPLACE INTO oracle_decisions VALUES (?, ?, ?, ?, ?, ?)",
        (content_id, content_type, score, decision, reason, datetime.utcnow().isoformat()),
    )
    get_conn().commit()
