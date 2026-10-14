"""Кластеризация одинаковых проблем, сформулированных по-разному."""

import json
import os
import re

from alltokens import chat

MAX_TEXTS = 100
MAX_TEXT_LEN = 500

# Локальный фолбэк: грубая группировка по ключевым словам.
FALLBACK_RULES = [
    ("Wi-Fi и интернет", r"wi-?fi|вай-?фай|интернет|сет[ьи]|роутер|канал[а-я]* связи|не открывается|портал|логин|вход|парол"),
    ("Проекторы и экран", r"проектор|экран|слайд|презентац|видео на экране|не показывает"),
    ("Компьютеры и ноутбуки", r"компьютер|ноутбук|пк\b|монитор|мышь|клавиатур|не включается|завис|тормозит"),
    ("Принтеры и оргтехника", r"принтер|печат|сканер|картридж|полос"),
    ("Звук и микрофоны", r"звук|динамик|микрофон|колонк|не слышно|тихо"),
    ("Свет и электрика", r"свет|ламп|лампоч|розетк|выключател|тёмно|мига"),
    ("Мебель и двери", r"стул|стол|парта|дверь|замок|шкаф|мебель|шатает|сломан стул"),
    ("Температура и окна", r"холодно|жарко|отоплен|кондицион|окн|сквозняк|батаре"),
    ("Уборка и помещение", r"мусор|уборк|протек|потолок|краска|табличк|кабинет"),
]

CLUSTER_SYSTEM_PROMPT = """Ты группируешь обращения в школьную службу помощи.
Разные формулировки одной и той же проблемы — один кластер.

Верни СТРОГО JSON:
{"clusters":[{"title":"короткое имя проблемы","items":[0,3,7]}]}

Правила:
- title по-русски, 2–5 слов, без кавычек.
- items — индексы обращений (0-based), которые относятся к этой проблеме.
- Каждый индекс ровно в одном кластере.
- Одинаковые симптомы (например «нет Wi-Fi», «пропал интернет», «не грузится сеть») — один кластер.
- Не выдумывай детали, которых нет в текстах.
- Ответ — только JSON.

JSON:"""


def _prepare_texts(texts):
    prepared = []
    for item in texts:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text:
            continue
        prepared.append(text[:MAX_TEXT_LEN])
        if len(prepared) >= MAX_TEXTS:
            break
    return prepared


def _fallback_clusters(texts):
    buckets = {}
    other = []
    for index, text in enumerate(texts):
        lower = text.lower()
        matched = None
        for title, pattern in FALLBACK_RULES:
            if re.search(pattern, lower, re.IGNORECASE):
                matched = title
                break
        if matched:
            buckets.setdefault(matched, []).append(index)
        else:
            other.append(index)

    clusters = []
    for title, items in buckets.items():
        clusters.append({
            "title": title,
            "items": items,
            "count": len(items),
            "examples": [texts[i] for i in items[:3]],
        })
    if other:
        clusters.append({
            "title": "Другое",
            "items": other,
            "count": len(other),
            "examples": [texts[i] for i in other[:3]],
        })
    clusters.sort(key=lambda c: c["count"], reverse=True)
    return clusters


def _parse_ai_clusters(content, texts):
    text = (content or "").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("Модель вернула не JSON")
        data = json.loads(match.group(0))
    if not isinstance(data, dict) or "clusters" not in data:
        raise ValueError("Модель вернула не JSON с полем clusters")
    raw = data["clusters"]
    if not isinstance(raw, list):
        raise ValueError("clusters должен быть списком")

    used = set()
    clusters = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "").strip()
        items_raw = entry.get("items")
        if not title or not isinstance(items_raw, list):
            continue
        items = []
        for value in items_raw:
            try:
                index = int(value)
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(texts) and index not in used:
                used.add(index)
                items.append(index)
        if items:
            clusters.append({
                "title": title[:80],
                "items": items,
                "count": len(items),
                "examples": [texts[i] for i in items[:3]],
            })

    leftover = [i for i in range(len(texts)) if i not in used]
    if leftover:
        clusters.append({
            "title": "Прочее",
            "items": leftover,
            "count": len(leftover),
            "examples": [texts[i] for i in leftover[:3]],
        })

    clusters.sort(key=lambda c: c["count"], reverse=True)
    return clusters


def cluster_texts(texts):
    """Группирует тексты обращений в кластеры одинаковых проблем."""
    prepared = _prepare_texts(texts)
    total = len(prepared)
    if total == 0:
        return {"clusters": [], "total": 0, "source": "empty"}

    # Пробуем AI, если ключ есть; при сбое — локальный словарь ключевых слов.
    if os.environ.get("ALLTOKENS_API_KEY"):
        try:
            numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(prepared))
            messages = [
                {"role": "system", "content": CLUSTER_SYSTEM_PROMPT},
                {"role": "user", "content": numbered},
            ]
            response = chat(messages)
            content = response["choices"][0]["message"]["content"]
            clusters = _parse_ai_clusters(content, prepared)
            return {"clusters": clusters, "total": total, "source": "ai"}
        except Exception:
            pass

    return {"clusters": _fallback_clusters(prepared), "total": total, "source": "fallback"}
