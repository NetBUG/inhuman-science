from __future__ import annotations

import logging
from pathlib import Path

import re

import requests

import config

logger = logging.getLogger(__name__)


def _sanitize_html(text: str) -> str:
    """Escape HTML special chars in LLM-generated text, preserving nothing."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def send_post_with_image(
    text: str,
    image_path: Path | None = None,
    link: str = "",
) -> str | None:
    """Send a post to the Telegram channel. Returns message_id or None."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHANNEL_ID:
        logger.warning("Telegram not configured, skipping post")
        return None

    caption = text
    if link:
        caption += f"\n\n{link}"

    if image_path and image_path.exists():
        return _send_photo(caption, image_path)
    else:
        return _send_text(caption)


def _send_photo(caption: str, image_path: Path) -> str | None:
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendPhoto"
    with open(image_path, "rb") as f:
        resp = requests.post(
            url,
            data={
                "chat_id": config.TELEGRAM_CHANNEL_ID,
                "caption": caption[:1024],
                "disable_notification": True,
            },
            files={"photo": f},
            timeout=30,
        )

    if resp.ok:
        msg_id = resp.json().get("result", {}).get("message_id", "")
        logger.info("Telegram photo sent, message_id=%s", msg_id)
        return str(msg_id)
    else:
        logger.error("Telegram sendPhoto failed: %s", resp.text)
        _notify_error(f"sendPhoto failed: {resp.status_code}")
        return None


def _send_text(text: str) -> str | None:
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        data={
            "chat_id": config.TELEGRAM_CHANNEL_ID,
            "text": text[:4096],
            "disable_notification": True,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )

    if resp.ok:
        msg_id = resp.json().get("result", {}).get("message_id", "")
        logger.info("Telegram message sent, message_id=%s", msg_id)
        return str(msg_id)
    else:
        logger.error("Telegram sendMessage failed: %s", resp.text)
        _notify_error(f"sendMessage failed: {resp.status_code}")
        return None


def _notify_error(text: str) -> None:
    if not config.TELEGRAM_ERROR_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(
            url,
            data={
                "chat_id": config.TELEGRAM_ERROR_CHAT_ID,
                "text": f"[InhumanScience Error] {text}",
                "parse_mode": "HTML",
            },
            timeout=10,
        )
    except Exception:
        logger.exception("Failed to send error notification")


def send_document(file_path: Path, caption: str = "") -> bool:
    """Send a file to the error chat (e.g. DB backups). Returns True on success."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_ERROR_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendDocument"
        with open(file_path, "rb") as f:
            resp = requests.post(
                url,
                data={
                    "chat_id": config.TELEGRAM_ERROR_CHAT_ID,
                    "caption": caption[:1024] if caption else "",
                },
                files={"document": (file_path.name, f)},
                timeout=60,
            )
        if resp.ok:
            logger.info("Telegram document sent: %s", file_path.name)
            return True
        logger.error("Telegram sendDocument failed: %s", resp.text)
        return False
    except Exception:
        logger.exception("Failed to send document %s", file_path.name)
        return False


def send_error(text: str) -> None:
    """Public helper for sending error notifications."""
    logger.error(text)
    _notify_error(text)


def send_status(text: str) -> None:
    """Send an informational status message to the error chat."""
    logger.info(text)
    if not config.TELEGRAM_ERROR_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(
            url,
            data={
                "chat_id": config.TELEGRAM_ERROR_CHAT_ID,
                "text": f"[InhumanScience] {text}",
            },
            timeout=10,
        )
    except Exception:
        pass
