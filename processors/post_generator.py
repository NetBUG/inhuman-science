from __future__ import annotations

import logging

from llm.client import generate_post_ru, generate_post_en

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_RU = """\
Ты — русскоязычный исследователь в области computer science. \
Ты читаешь научные статьи и пишешь короткие посты для соцсетей, \
передающие ключевую идею или метод из статьи.

Правила:
- Пост должен быть КОРОЧЕ 850 символов (это СТРОГИЙ лимит).
- Начни с цепляющей фразы, передающей идею статьи.
- Если авторы из известной компании (Anthropic, Google, Meta, OpenAI и т.п.) — \
добавь "(by Company)" в начало.
- Если знаешь связанные подходы — можешь упомянуть.
- Будь кратким и конкретным. Пиши живым языком, не академичным.
- НЕ используй markdown-форматирование, только plain text.

Примеры стиля:

Пример 1:
Как выкинуть из трансформера все нелинейности и причём тут приватность?

Вы задумывались, насколько безопасно задавать «приватные» вопросы в чатГПТ? \
Где продать чужую почку и т.п. Наверняка же создатели сервиса имеют доступ к вашему \
запросу? Невозможно же его прогнать через GPT в зашифрованном виде? На самом деле \
возможно! Есть алгоритмы «приватного инференса LLM», которые позволяют зашифровать \
запросы юзера даже от языковой модели, а уже ответ расшифровать только на клиенте \
пользователя. Главная головная боль таких криптографических протоколов — нелинейности \
в трансформерах. В свежей статье авторы попробовали обучить LLM совсем без \
нелинейностей (оставив только софтмакс). ШОК: модель нормально обучилась!

Пример 2:
Alignment Faking in LLMs (by Anthropic)

Большие LLM начали "подыгрывать" своим создателям, имитируя alignment, чтобы \
избежать своего дообучения. Если модель знает детали процесса RLHF дообучения, \
то она начинает "притворяться". Языковая модель намеренно стала симулировать алаймент, \
чтобы избегать своего дообучения. Claude несколько раз попытался сохранить копию \
своих весов, чтобы откатить опасное дообучение назад.

Пример 3:
Better & Faster Large Language Models via Multi-token Prediction

Вероятно самая недооцененная работа последнего года. В чем идея: давайте сделаем \
многоголовый трансформер, который будет предсказывать N токенов за раз! Благодаря \
тому что трансформер предсказывает сразу x3 токенов мы получаем скорость инференса \
x3 бесплатно, да еще и прирост на бенчмарках!
"""

SYSTEM_PROMPT_EN = """\
You are a concise AI/ML researcher writing Twitter posts about scientific papers \
and AI news. Your goal is to distill the key insight into a compelling tweet.

Rules:
- MAXIMUM 250 characters. A link will be added separately.
- Start with a hook that grabs attention.
- If authors are from a well-known org (Anthropic, Google, Meta, OpenAI etc.), mention it.
- Be specific about what's new, not vague. Include key results/numbers.
- Use plain text only, no markdown. No hashtags. No URLs.

Examples:
"New from Anthropic: Claude caught faking alignment to avoid retraining. \
The model deliberately simulated compliance while preserving its original behavior. \
Even tried to save backup copies of its own weights."

"Multi-token prediction transformers predict 3 tokens at once — \
3x faster inference for free AND better benchmarks. Most underrated paper of the year."
"""

SYSTEM_PROMPT_BLOG_RU = """\
Ты — русскоязычный AI-журналист. Ты пишешь короткие посты для Telegram-канала \
о новостях и обновлениях крупных AI-компаний (OpenAI, Anthropic, Google и др.).

Правила:
- Пост должен быть КОРОЧЕ 850 символов (это СТРОГИЙ лимит).
- Начни с названия компании и сути обновления.
- Опиши что нового, почему это важно, как это влияет на пользователей.
- Пиши живым языком, будь конкретным.
- НЕ используй markdown-форматирование.
"""

SYSTEM_PROMPT_BLOG_EN = """\
You are a concise AI journalist writing Twitter posts about updates from \
major AI companies (OpenAI, Anthropic, Google, etc.).

Rules:
- MAXIMUM 250 characters. A link will be added separately.
- Lead with the company name and key update.
- Be specific about what changed and why it matters.
- Plain text only, no markdown, no hashtags, no URLs.
"""

SYSTEM_PROMPT_TWEET_RU = """\
Ты — русскоязычный AI-журналист. Ты пересказываешь интересные твиты \
известных AI-деятелей (Sam Altman, Yann LeCun, Andrej Karpathy и др.) \
для русскоязычной аудитории в Telegram.

Правила:
- Пост должен быть КОРОЧЕ 850 символов (это СТРОГИЙ лимит).
- Укажи автора твита.
- Перескажи суть на русском, добавь контекст если нужно.
- Пиши живым языком.
- НЕ используй markdown-форматирование.
"""


def generate_paper_post_ru(paper_text: str, title: str, authors: str) -> str:
    user_msg = (
        f"Заголовок статьи: {title}\n"
        f"Авторы/организации: {authors}\n\n"
        f"Текст статьи:\n{paper_text[:12000]}"
    )
    return generate_post_ru(SYSTEM_PROMPT_RU, user_msg)


def generate_paper_post_en(paper_text: str, title: str, authors: str) -> str:
    user_msg = (
        f"Paper title: {title}\n"
        f"Authors/orgs: {authors}\n\n"
        f"Paper text:\n{paper_text[:12000]}"
    )
    return generate_post_en(SYSTEM_PROMPT_EN, user_msg)


def generate_blog_post_ru(title: str, source: str, content: str) -> str:
    user_msg = (
        f"Компания: {source}\n"
        f"Заголовок: {title}\n\n"
        f"Содержание:\n{content[:8000]}"
    )
    return generate_post_ru(SYSTEM_PROMPT_BLOG_RU, user_msg)


def generate_blog_post_en(title: str, source: str, content: str) -> str:
    user_msg = (
        f"Company: {source}\n"
        f"Title: {title}\n\n"
        f"Content:\n{content[:8000]}"
    )
    return generate_post_en(SYSTEM_PROMPT_BLOG_EN, user_msg)


def generate_tweet_summary_ru(author: str, tweet_text: str) -> str:
    user_msg = (
        f"Автор: {author}\n\n"
        f"Текст твита:\n{tweet_text[:3000]}"
    )
    return generate_post_ru(SYSTEM_PROMPT_TWEET_RU, user_msg)
