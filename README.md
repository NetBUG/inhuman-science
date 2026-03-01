# Inhuman Science

[Telegram](https://t.me/InhumanScience) | [Twitter/X](https://x.com/inhumanscience)

Automated AI/ML content curation and publishing pipeline. Aggregates papers, blog posts, and tweets from the AI world, evaluates them with LLMs, and publishes the best finds to Telegram and Twitter/X.

## How It Works

The system runs four scheduled jobs (cron-based, timezone-aware):

**Papers (10:00)** — scrapes trending papers from [AlphaXiv](https://www.alphaxiv.org), scores them with an LLM oracle, downloads PDFs, extracts the most representative figure using a vision model, generates bilingual posts (Russian for Telegram, English for Twitter), and publishes.

**Blogs (12:00)** — fetches RSS feeds from 11 sources (OpenAI, Anthropic, Google Gemini, Google DeepMind, Meta AI, Microsoft Research, NVIDIA Tech, Amazon Science, IBM Research, Apple ML, PyTorch), scores and fact-checks each post, generates summaries, and publishes.

**Twitter (14:00)** — monitors 25 accounts: AI lab leaders (Demis Hassabis, Jeff Dean, Dario Amodei, etc.), top researchers (Yoshua Bengio, Fei-Fei Li, Noam Brown, Jan Leike), open-source leads (Thomas Wolf, Clément Delangue, Soumith Chintala), and official accounts (OpenAI, DeepMind, Anthropic, Meta AI, Mistral, Cohere, ByteDance OSS). Scores tweets, generates Russian summaries for Telegram, retweets on Twitter.

**Backup (03:00)** — daily SQLite dump to `backups/` with Telegram delivery. Keeps last 7 days.

### Content Filtering

The oracle is tuned for **pure science and engineering only**. It publishes new models, architectures, agents, benchmarks, open-source releases, and infrastructure breakthroughs. It rejects politics, business deals, gossip, marketing, and think-pieces.

### Cross-Source Deduplication

When the same news goes viral across multiple sources, a batch dedup step groups all scored candidates by topic in a single LLM call and keeps only the highest-scored item per group. This runs against both the current batch and the last 5 days of published content.

## Architecture

```
Sources                 Processing              Publishing
┌─────────────┐        ┌──────────────┐        ┌───────────┐
│  AlphaXiv   │───┐    │  Oracle      │        │ Telegram  │
│  (papers)   │   │    │  (scoring,   │   ┌───▶│ (RU post) │
├─────────────┤   │    │  fact-check, │   │    ├───────────┤
│  RSS Feeds  │───┼───▶│  batch dedup)│───┤    │ Twitter   │
│  (11 blogs) │   │    ├──────────────┤   └───▶│ (EN post) │
├─────────────┤   │    │  Processors  │        └───────────┘
│  Twitter    │───┘    │  (PDF, image,│              │
│  (25 accts) │        │  post gen)   │              ▼
└─────────────┘        └──────────────┘        ┌───────────┐
                                               │  SQLite   │
                                               │  (state)  │
                                               └───────────┘
```

## Project Structure

```
├── main.py                 # Entry point, scheduler, pipeline orchestration
├── config.py               # Configuration and environment variables
├── Makefile                # Convenience commands (deploy, logs, backup, etc.)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
│
├── sources/
│   ├── base.py             # ContentItem dataclass
│   ├── alphaxiv.py         # AlphaXiv trending papers scraper
│   ├── blogs.py            # RSS feed parser
│   └── twitter_feed.py     # Twitter API v2 feed reader
│
├── oracle/
│   └── oracle.py           # LLM scoring, fact-checking, batch deduplication
│
├── processors/
│   ├── pdf.py              # PDF download and text extraction
│   ├── images.py           # Best figure extraction via vision model
│   └── post_generator.py   # Bilingual post generation (RU/EN)
│
├── publishers/
│   ├── telegram.py         # Telegram channel publisher
│   └── twitter.py          # Twitter/X publisher
│
├── storage/
│   └── state.py            # SQLite state tracking
│
└── llm/
    └── client.py           # OpenRouter API client
```

## Setup

### Prerequisites

- Python 3.11+
- API keys: [OpenRouter](https://openrouter.ai/), Telegram Bot, Twitter/X

### Configuration

```bash
cp .env.example .env
# Fill in API keys
```

#### Required variables

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM calls |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_CHANNEL_ID` | Target Telegram channel ID |
| `TELEGRAM_ERROR_CHAT_ID` | Chat ID for error notifications |
| `TWITTER_API_KEY` | Twitter API key |
| `TWITTER_API_SECRET` | Twitter API secret |
| `TWITTER_ACCESS_TOKEN` | Twitter access token |
| `TWITTER_ACCESS_SECRET` | Twitter access secret |

#### Optional variables

| Variable | Default | Description |
|---|---|---|
| `SCHEDULE_PAPERS_CRON` | `0 10 * * *` | Papers pipeline schedule |
| `SCHEDULE_BLOGS_CRON` | `0 12 * * *` | Blogs pipeline schedule |
| `SCHEDULE_TWITTER_CRON` | `0 14 * * *` | Twitter pipeline schedule |
| `SCHEDULE_BACKUP_CRON` | `0 3 * * *` | DB backup schedule |
| `TWITTER_MONITOR_USERS` | 25 accounts | Comma-separated Twitter usernames |
| `ORACLE_MIN_SCORE` | `7` | Minimum LLM score (1-10) to publish |
| `ORACLE_MAX_PAPERS_PER_RUN` | `5` | Max papers published per run |
| `ORACLE_MAX_BLOGS_PER_RUN` | `3` | Max blog posts published per run |
| `BACKUP_DIR` | `backups` | Directory for DB backups |
| `BACKUP_KEEP_DAYS` | `7` | Days to retain backups |
| `TIMEZONE` | `Europe/Moscow` | Timezone for scheduling |

## Usage

### Docker (recommended)

```bash
make deploy     # Build and start
make logs       # Follow logs
make stop       # Stop
make restart    # Restart
make update     # git pull + rebuild
make backup     # Manual DB backup
make status     # Container status
```

### Manual

```bash
pip install -r requirements.txt

python main.py              # Start scheduler (runs forever)
python main.py papers       # Single papers run
python main.py blogs        # Single blogs run
python main.py twitter      # Single twitter run
python main.py backup       # Manual backup
python main.py all          # All pipelines sequentially
```

## LLM Models

All LLM calls go through [OpenRouter](https://openrouter.ai/). Models are configured in `config.py`:

| Task | Model |
|---|---|
| Content scoring | `deepseek/deepseek-chat-v3-0324` |
| Fact-checking | `deepseek/deepseek-chat-v3-0324` |
| Post generation (RU & EN) | `anthropic/claude-sonnet-4.6` |
| Figure extraction (vision) | `google/gemini-2.5-flash` |

## Data Storage

SQLite database (`state.db`) with five tables:

- **posted_papers** — published papers (arxiv ID, title, timestamp)
- **posted_blogs** — published blog posts (URL, title, timestamp)
- **posted_tweets** — published tweets (tweet URL, author, timestamp)
- **oracle_decisions** — all scoring decisions with scores and reasoning
- **published_summaries** — title + summary of all published content for cross-source dedup
