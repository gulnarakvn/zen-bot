import os
import httpx
import json

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

TONE_MAP = {
    "Экспертный": "профессионального эксперта с авторитетным тоном",
    "Простой": "понятным языком для обычного человека без технических знаний",
    "Продающий": "с акцентом на выгоды и призывом к действию",
    "Советующий": "дружелюбного советника, как будто разговариваешь с другом",
}

async def generate_post(niche: str, tone: str) -> dict | None:
    tone_desc = TONE_MAP.get(tone, "экспертного автора")
    prompt = f"""Напиши пост для Яндекс Дзен на тему: {niche}.

Стиль: от лица {tone_desc}.
Длина: строго 500-1000 символов (включая пробелы).
Формат ответа — только JSON без лишнего текста:
{{
  "title": "Заголовок поста (до 80 символов)",
  "body": "Текст поста"
}}

Требования к посту:
- Полезная и конкретная информация
- Живой язык, без канцелярщины
- Можно использовать 1-2 абзаца
- Заканчивать мыслью или советом, не обрывать на полуслове
"""
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
            # strip possible markdown fences
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
    except Exception as e:
        print(f"[generator] error: {e}")
        return None
