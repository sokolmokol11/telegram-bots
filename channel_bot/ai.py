"""
Обращение к нейросети.

Два вида подключения (AI_PROVIDER в .env):
  gigachat — GigaChat от Сбера. Работает из России, у физлиц бесплатный лимит на год.
             AI_API_KEY — «Ключ авторизации» из личного кабинета GigaChat API.
  openai   — любой OpenAI-совместимый API: DeepSeek, OpenRouter, Groq, OpenAI и др.
             AI_API_KEY — обычный API-ключ сервиса.
Формат запросов и ответов у них одинаковый, отличается только вход (авторизация).
"""
import logging
import ssl
import time
import uuid

import aiohttp

import config

log = logging.getLogger(__name__)

GIGACHAT_OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

_giga_token: dict = {"value": None, "expires": 0.0}


class AIError(Exception):
    pass


def enabled() -> bool:
    return bool(config.AI_API_KEY)


def _connector():
    """Если нейросеть недоступна напрямую — идём через тот же прокси, что и к Telegram."""
    if config.PROXY and config.AI_USE_PROXY:
        from aiohttp_socks import ProxyConnector
        return ProxyConnector.from_url(config.PROXY)
    return None


def _ssl_context():
    """GigaChat использует сертификат НУЦ Минцифры — подгружаем его, если файл лежит рядом с ботом."""
    ctx = ssl.create_default_context()
    if config.AI_CA_FILE and config.AI_CA_FILE.exists():
        ctx.load_verify_locations(cafile=str(config.AI_CA_FILE))
    return ctx


async def _gigachat_token(session: aiohttp.ClientSession) -> str:
    """Временный токен GigaChat живёт 30 минут — получаем новый заранее."""
    if _giga_token["value"] and _giga_token["expires"] > time.time() + 60:
        return _giga_token["value"]
    headers = {
        "Authorization": f"Basic {config.AI_API_KEY}",
        "RqUID": str(uuid.uuid4()),
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    async with session.post(GIGACHAT_OAUTH_URL, data={"scope": config.AI_SCOPE},
                            headers=headers, ssl=_ssl_context()) as resp:
        data = await resp.json(content_type=None)
        if resp.status != 200 or "access_token" not in data:
            raise AIError(f"GigaChat не выдал токен: HTTP {resp.status}: {str(data)[:300]}")
    expires = float(data.get("expires_at", 0))
    if expires > 1e12:  # приходит в миллисекундах
        expires /= 1000
    _giga_token["value"] = data["access_token"]
    _giga_token["expires"] = expires or time.time() + 25 * 60
    return _giga_token["value"]


async def chat(messages: list[dict], max_tokens: int = 500, temperature: float = 0.3) -> str:
    """Отправляет диалог нейросети и возвращает текст ответа."""
    if not enabled():
        raise AIError("Не задан AI_API_KEY")
    giga = config.AI_PROVIDER == "gigachat"
    url = config.AI_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": config.AI_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": max(temperature, 0.01) if giga else temperature,
    }
    timeout = aiohttp.ClientTimeout(total=40)
    try:
        async with aiohttp.ClientSession(connector=_connector(), timeout=timeout) as session:
            for attempt in (1, 2):
                if giga:
                    headers = {"Authorization": f"Bearer {await _gigachat_token(session)}"}
                else:
                    headers = {"Authorization": f"Bearer {config.AI_API_KEY}"}
                async with session.post(url, json=payload, headers=headers,
                                        ssl=_ssl_context() if giga else None) as resp:
                    data = await resp.json(content_type=None)
                    if resp.status == 401 and giga and attempt == 1:
                        _giga_token["value"] = None  # токен протух — получим новый и повторим
                        continue
                    if resp.status != 200:
                        raise AIError(f"HTTP {resp.status}: {str(data)[:300]}")
                    break
    except AIError:
        raise
    except Exception as e:
        raise AIError(f"{type(e).__name__}: {e}") from e
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise AIError(f"Неожиданный ответ: {str(data)[:300]}") from e
