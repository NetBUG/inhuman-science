import os
from dotenv import load_dotenv

load_dotenv()


class LLMModels:
    ORACLE = "deepseek/deepseek-chat-v3-0324"
    POST_RU = "anthropic/claude-sonnet-4.6"
    POST_EN = "anthropic/claude-sonnet-4.6"
    VISION = "google/gemini-2.5-flash"
    FACT_CHECK = "deepseek/deepseek-chat-v3-0324"


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")
TELEGRAM_ERROR_CHAT_ID = os.getenv("TELEGRAM_ERROR_CHAT_ID", "")

TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "placeholder-api-key")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "placeholder-api-secret")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "placeholder-access-token")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "placeholder-access-secret")

TWITTER_MONITOR_USERS = [
    u.strip()
    for u in os.getenv(
        "TWITTER_MONITOR_USERS",
        "sama,ylecun,karpathy,demishassabis,"
        "JeffDean,mustafasuleyman,DarioAmodei,jackclarkSF,"
        "arthurmensch,aidangomez,Yoshua_Bengio,drfeifei,"
        "polynoamial,janleike,Thom_Wolf,ClementDelangue,soumithchintala,"
        "OpenAI,GoogleDeepMind,AnthropicAI,AIatMeta,MistralAI,cohere,ByteDanceOSS",
    ).split(",")
    if u.strip()
]

SCHEDULE_PAPERS_CRON = os.getenv("SCHEDULE_PAPERS_CRON", "0 10 * * *")
SCHEDULE_BLOGS_CRON = os.getenv("SCHEDULE_BLOGS_CRON", "0 12 * * *")
SCHEDULE_TWITTER_CRON = os.getenv("SCHEDULE_TWITTER_CRON", "0 14 * * *")
SCHEDULE_BACKUP_CRON = os.getenv("SCHEDULE_BACKUP_CRON", "0 3 * * *")

BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")
BACKUP_KEEP_DAYS = int(os.getenv("BACKUP_KEEP_DAYS", "7"))

ORACLE_MIN_SCORE = int(os.getenv("ORACLE_MIN_SCORE", "7"))
ORACLE_MAX_PAPERS_PER_RUN = int(os.getenv("ORACLE_MAX_PAPERS_PER_RUN", "3"))
ORACLE_MAX_BLOGS_PER_RUN = int(os.getenv("ORACLE_MAX_BLOGS_PER_RUN", "3"))

TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

ALPHAXIV_HOT_URL = "https://www.alphaxiv.org/?sort=Hot"
ALPHAXIV_LIKES_URL = "https://www.alphaxiv.org/?sort=Likes"
ARXIV_PDF_BASE = "https://arxiv.org/pdf/"

HF_DAILY_MIN_UPVOTES = int(os.getenv("HF_DAILY_MIN_UPVOTES", "10"))

BLOG_FEEDS = {
    "openai": "https://openai.com/news/rss.xml",
    "anthropic": "https://anthropic.com/news/feed_anthropic.xml",
    "google_gemini": "https://blog.google/products/gemini/rss/",
    "google_deepmind": "https://deepmind.google/blog/rss.xml",
    "meta_ai": "https://engineering.fb.com/category/ai-research/feed/",
    "microsoft_research": "https://www.microsoft.com/en-us/research/feed/",
    "nvidia_tech": "https://developer.nvidia.com/blog/feed",
    "amazon_science": "https://www.amazon.science/index.rss",
    "ibm_research": "https://research.ibm.com/rss",
    "apple_ml": "https://machinelearning.apple.com/rss.xml",
    "pytorch": "https://pytorch.org/blog/feed.xml",
}

RSSHUB_BASE = "https://rsshub.app/twitter/user/"

DB_PATH = os.getenv("DB_PATH", "state.db")
PDF_DIR = os.getenv("PDF_DIR", "pdfs")
IMG_DIR = os.getenv("IMG_DIR", "images")
