"""Серверный вызов AllTokens. Не переносите этот код и ключ в браузер."""

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _load_env_file():
    path = Path(__file__).resolve().parent / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


def chat(messages):
    key = os.environ.get("ALLTOKENS_API_KEY")
    if not key:
        raise RuntimeError("Ключ AllTokens не настроен. Обратитесь к наставнику.")

    body = json.dumps({
        "model": os.environ.get("ALLTOKENS_MODEL", "openai/gpt-4.1-mini"),
        "messages": messages,
        "temperature": 0.2,
        "stream": False,
        "max_tokens": 200,
    }).encode("utf-8")
    request = Request(
        "https://api.alltokens.ru/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=25) as response:
            return json.load(response)
    except HTTPError as error:
        # Не выводим тело ответа: оно может содержать лишние детали запроса.
        raise RuntimeError(f"AllTokens вернул код {error.code}. Сообщите наставнику.") from error
    except URLError as error:
        raise RuntimeError("Нет соединения с AllTokens. Проверьте сеть.") from error
