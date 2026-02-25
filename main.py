"""InhumanScience — automated AI/ML content curation and publishing pipeline."""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

import config
from sources.alphaxiv import fetch_trending_papers
from sources.blogs import fetch_blog_posts, fetch_full_blog_content
from sources.twitter_feed import fetch_ai_leader_tweets
from oracle.oracle import evaluate_content, verify_content, deduplicate_batch
from processors.pdf import download_pdf, extract_text
from processors.images import extract_best_figure
from processors.post_generator import (
    generate_paper_post_ru,
    generate_paper_post_en,
    generate_blog_post_ru,
    generate_blog_post_en,
    generate_tweet_summary_ru,
)
from publishers.telegram import send_post_with_image, send_document, send_error, send_status
from publishers.twitter import post_tweet, retweet
from storage.state import (
    is_paper_posted,
    mark_paper_posted,
    is_blog_posted,
    mark_blog_posted,
    is_tweet_posted,
    mark_tweet_posted,
    save_published_summary,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


def _parse_cron(expr: str) -> dict:
    """Parse '0 10 * * *' into CronTrigger kwargs."""
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {expr}")
    return dict(
        minute=parts[0], hour=parts[1], day=parts[2],
        month=parts[3], day_of_week=parts[4],
    )


# ---------------------------------------------------------------------------
# Pipeline: Papers
# ---------------------------------------------------------------------------

def run_papers_pipeline() -> None:
    logger.info("=== Papers pipeline started ===")
    published = 0
    try:
        papers = fetch_trending_papers(max_papers=config.ORACLE_MAX_PAPERS_PER_RUN * 3)
        logger.info("Fetched %d candidate papers from AlphaRxiv", len(papers))

        candidates: list[tuple] = []
        for item in papers:
            if is_paper_posted(item.content_id):
                logger.debug("Already posted: %s", item.content_id)
                continue
            score, should_publish, reason = evaluate_content(item)
            if not should_publish:
                logger.info("Skipping (score=%.1f): %s", score, item.title[:60])
                continue
            candidates.append((item, score))

        candidates = deduplicate_batch(candidates)
        logger.info("After dedup: %d candidates", len(candidates))

        for item, score in candidates:
            if published >= config.ORACLE_MAX_PAPERS_PER_RUN:
                break
            try:
                pdf_path = download_pdf(item.content_id, item.pdf_url)
                paper_text = extract_text(pdf_path)
                figure_path = extract_best_figure(pdf_path)

                authors_str = ", ".join(item.organizations or item.authors)
                post_ru = generate_paper_post_ru(paper_text, item.title, authors_str)
                post_en = generate_paper_post_en(paper_text, item.title, authors_str)

                tg_msg_id = send_post_with_image(post_ru, figure_path, item.url)
                tweet_id = post_tweet(post_en, figure_path, item.url)

                mark_paper_posted(
                    item.content_id, item.source_name, item.title,
                    tg_msg_id=tg_msg_id or "", tweet_id=tweet_id or "",
                )
                save_published_summary(
                    item.content_id, item.source_type, item.source_name,
                    item.title, item.summary, score,
                )
                published += 1
                logger.info("Published paper: %s", item.title[:60])

            except Exception:
                logger.exception("Failed to process paper %s", item.content_id)
                send_error(f"Paper pipeline error: {item.content_id}")

    except Exception:
        logger.exception("Papers pipeline crashed")
        send_error("Papers pipeline crashed")

    logger.info("=== Papers pipeline done (%d published) ===", published)
    send_status(f"Papers pipeline done: {published} published")


# ---------------------------------------------------------------------------
# Pipeline: Blogs
# ---------------------------------------------------------------------------

def run_blogs_pipeline() -> None:
    logger.info("=== Blogs pipeline started ===")
    published = 0
    try:
        posts = fetch_blog_posts(max_age_days=3)
        logger.info("Fetched %d blog posts", len(posts))

        candidates: list[tuple] = []
        for item in posts:
            if is_blog_posted(item.content_id):
                continue

            full_content = fetch_full_blog_content(item.url)
            if full_content:
                item.full_text = full_content
                item.summary = full_content[:2000]

            score, should_publish, reason = evaluate_content(item)
            if not should_publish:
                logger.info("Skipping blog (score=%.1f): %s", score, item.title[:60])
                continue

            verified, confidence, issues = verify_content(item)
            if not verified and confidence > 0.6:
                logger.warning("Blog fact-check failed: %s — %s", item.title[:60], issues)
                continue

            candidates.append((item, score))

        candidates = deduplicate_batch(candidates)
        logger.info("After dedup: %d blog candidates", len(candidates))

        for item, score in candidates:
            if published >= config.ORACLE_MAX_BLOGS_PER_RUN:
                break
            try:
                source_label = item.source_name.replace("_", " ").title()
                content = item.full_text or item.summary
                post_ru = generate_blog_post_ru(item.title, source_label, content)
                post_en = generate_blog_post_en(item.title, source_label, content)

                tg_msg_id = send_post_with_image(post_ru, link=item.url)
                tweet_id = post_tweet(post_en, link=item.url)

                mark_blog_posted(
                    item.content_id, item.source_name, item.title,
                    tg_msg_id=tg_msg_id or "", tweet_id=tweet_id or "",
                )
                save_published_summary(
                    item.content_id, item.source_type, item.source_name,
                    item.title, item.summary, score,
                )
                published += 1
                logger.info("Published blog: %s", item.title[:60])

            except Exception:
                logger.exception("Failed to process blog %s", item.url)
                send_error(f"Blog pipeline error: {item.url}")

    except Exception:
        logger.exception("Blogs pipeline crashed")
        send_error("Blogs pipeline crashed")

    logger.info("=== Blogs pipeline done (%d published) ===", published)
    send_status(f"Blogs pipeline done: {published} published")


# ---------------------------------------------------------------------------
# Pipeline: Twitter monitoring
# ---------------------------------------------------------------------------

def run_twitter_pipeline() -> None:
    logger.info("=== Twitter monitoring pipeline started ===")
    published = 0
    try:
        tweets = fetch_ai_leader_tweets(max_age_days=2)
        logger.info("Fetched %d tweets from AI leaders", len(tweets))

        candidates: list[tuple] = []
        for item in tweets:
            if is_tweet_posted(item.content_id):
                continue

            score, should_publish, reason = evaluate_content(item)
            if not should_publish:
                continue

            verified, confidence, issues = verify_content(item)
            if not verified and confidence > 0.6:
                logger.warning("Tweet fact-check failed: %s", item.title[:60])
                continue

            candidates.append((item, score))

        candidates = deduplicate_batch(candidates)
        logger.info("After dedup: %d tweet candidates", len(candidates))

        for item, score in candidates:
            try:
                author = item.authors[0] if item.authors else item.source_name
                post_ru = generate_tweet_summary_ru(author, item.summary)

                tg_msg_id = send_post_with_image(post_ru, link=item.url)
                rt_id = retweet(item.url) if item.url else None

                mark_tweet_posted(
                    item.content_id, author,
                    tg_msg_id=tg_msg_id or "",
                    our_tweet_id=rt_id or "",
                )
                save_published_summary(
                    item.content_id, item.source_type, item.source_name,
                    item.title, item.summary, score,
                )
                published += 1
                logger.info("Published tweet summary: %s (rt=%s)", item.title[:60], rt_id)

            except Exception:
                logger.exception("Failed to process tweet %s", item.content_id)
                send_error(f"Tweet pipeline error: {item.content_id}")

    except Exception:
        logger.exception("Twitter pipeline crashed")
        send_error("Twitter pipeline crashed")

    logger.info("=== Twitter pipeline done (%d published) ===", published)
    send_status(f"Twitter pipeline done: {published} published")


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def run_backup() -> None:
    """Copy state.db to backups dir with date suffix, send to Telegram, prune old."""
    import shutil

    logger.info("=== DB backup started ===")
    db = Path(config.DB_PATH)
    if not db.exists():
        logger.warning("No database file to back up")
        return

    backup_dir = Path(config.BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)

    today = time.strftime("%Y%m%d")
    backup_path = backup_dir / f"state_{today}.db"
    shutil.copy2(db, backup_path)
    logger.info("DB backed up to %s", backup_path)

    send_document(backup_path, caption=f"DB backup {today}")

    cutoff = time.time() - config.BACKUP_KEEP_DAYS * 86400
    for old in sorted(backup_dir.glob("state_*.db")):
        if old.stat().st_mtime < cutoff:
            old.unlink()
            logger.info("Deleted old backup: %s", old.name)

    logger.info("=== DB backup done ===")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    os.makedirs(config.PDF_DIR, exist_ok=True)
    os.makedirs(config.IMG_DIR, exist_ok=True)

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "papers":
            run_papers_pipeline()
        elif cmd == "blogs":
            run_blogs_pipeline()
        elif cmd == "twitter":
            run_twitter_pipeline()
        elif cmd == "backup":
            run_backup()
        elif cmd == "all":
            run_papers_pipeline()
            run_blogs_pipeline()
            run_twitter_pipeline()
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python main.py [papers|blogs|twitter|backup|all]")
            sys.exit(1)
        return

    tz = pytz.timezone(config.TIMEZONE)
    scheduler = BackgroundScheduler()

    papers_cron = _parse_cron(config.SCHEDULE_PAPERS_CRON)
    blogs_cron = _parse_cron(config.SCHEDULE_BLOGS_CRON)
    twitter_cron = _parse_cron(config.SCHEDULE_TWITTER_CRON)
    backup_cron = _parse_cron(config.SCHEDULE_BACKUP_CRON)

    scheduler.add_job(run_papers_pipeline, CronTrigger(timezone=tz, **papers_cron), id="papers")
    scheduler.add_job(run_blogs_pipeline, CronTrigger(timezone=tz, **blogs_cron), id="blogs")
    scheduler.add_job(run_twitter_pipeline, CronTrigger(timezone=tz, **twitter_cron), id="twitter")
    scheduler.add_job(run_backup, CronTrigger(timezone=tz, **backup_cron), id="backup")

    scheduler.start()
    logger.info(
        "Scheduler running (papers=%s, blogs=%s, twitter=%s, backup=%s, tz=%s)",
        config.SCHEDULE_PAPERS_CRON, config.SCHEDULE_BLOGS_CRON,
        config.SCHEDULE_TWITTER_CRON, config.SCHEDULE_BACKUP_CRON, config.TIMEZONE,
    )

    def _shutdown(signum, frame):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
