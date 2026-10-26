"""
Обращение к нейросети через OpenAI-совместимый API.

Подходит для Groq (бесплатно), DeepSeek, OpenRouter, OpenAI и многих других:
меняются только три строки в .env — AI_BASE_URL, AI_API_KEY, AI_MODEL.
"""
import logging

import aiohttp

import config

log = logging.getLogger(__name__)


class AIError(Exception):
    pass


def _connector():
    """Если нейросеть недоступна напрямую (сервер в России) — идём через тот же прокси."""
    if config.PROXY and config.AI_USE_PROXY:
        from aiohttp_socks import ProxyConnector
        return ProxyConnector.from_url(config.PROXY)
    return None


def enabled() -> bool:
    return bool(config.AI_API_KEY)


async def chat(messages: list[dict], max_tokens: int = 500, temperature: float = 0.3) -> str:
    """Отправляет диалог нейросети и возвращает текст ответа."""
    if not enabled():
        raise AIError("Не задан AI_API_KEY")
    url = config.AI_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": config.AI_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {config.AI_API_KEY}"}
    timeout = aiohttp.ClientTimeout(total=40)
    try:
        async with aiohttp.ClientSession(connector=_connector(), timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200:
                    raise AIError(f"HTTP {resp.status}: {str(data)[:300]}")
    except AIError:
        raise
    except Exception as e:
        raise AIError(f"{type(e).__name__}: {e}") from e
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise AIError(f"Неожиданный ответ: {str(data)[:300]}") from e
