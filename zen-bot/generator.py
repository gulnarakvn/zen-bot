import os
import httpx
import json
import random

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

TONE_MAP = {
    "Экспертный": "опытного эксперта с 15-летним стажем в этой области",
    "Простой": "понятным языком для обычного человека без технических знаний",
    "Продающий": "с акцентом на выгоды и мягким призывом к действию",
    "Советующий": "дружелюбного советника, как будто разговариваешь с другом",
}

HOOKS = [
    "Начни с неожиданного факта или распространённой ошибки которую совершают люди.",
    "Начни с конкретной ситуации или сценария из реальной жизни.",
    "Начни с провокационного вопроса который заставляет задуматься.",
    "Начни с конкретной цифры или статистики по теме.",
    "Начни с популярного мифа и сразу его развей.",
    "Начни с короткой истории или случая из практики.",
]

async def generate_post(niche: str, tone: str) -> dict | None:
    tone_desc = TONE_MAP.get(tone, "эксперта в своей области")
    hook = random.choice(HOOKS)
    
    prompt = f"""Напиши пост для Яндекс Дзен на тему: {niche}.

Стиль: от лица {tone_desc}.
{hook}

Строгие требования:
- Длина: 600-900 символов включая пробелы
- Каждый пост должен быть УНИКАЛЬНЫМ по структуре и подаче
- Никаких шаблонных фраз типа "В этой статье мы расскажем", "Сегодня поговорим о"
- Никаких очевидных вступлений — сразу к сути
- Конкретика: цифры, факты, примеры из практики
- Живой язык, разговорный стиль, без канцелярщины
- Один чёткий совет или вывод в конце

Формат ответа — только JSON без лишнего текста:
{{
  "title": "Цепляющий заголовок (до 80 символов, без воды)",
  "body": "Текст поста"
}}"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                }
            )
            data = resp.json()
            text = data["content"][0]["text"].strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
    except Exception as e:
        print(f"[generator] error: {e}")
        return None
