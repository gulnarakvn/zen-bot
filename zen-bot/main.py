import os
import json
import uuid
import httpx
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from generator import generate_post
from rss_builder import build_rss

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL", "")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")

async def get_image_url(query: str) -> str | None:
    if not UNSPLASH_ACCESS_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.unsplash.com/photos/random",
                params={"query": query, "orientation": "landscape"},
                headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
            )
            data = resp.json()
            return data.get("urls", {}).get("regular")
    except Exception as e:
        print(f"[unsplash] error: {e}")
        return None

async def send_telegram(text: str, channel: str = None, image_url: str = None):
    token = TELEGRAM_BOT_TOKEN
    chat_id = channel or TELEGRAM_CHANNEL
    if not token or not chat_id:
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            if image_url:
                await client.post(
                    f"https://api.telegram.org/bot{token}/sendPhoto",
                    json={"chat_id": chat_id, "photo": image_url, "caption": text, "parse_mode": "HTML"}
                )
            else:
                await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
                )
    except Exception as e:
        print(f"[telegram] error: {e}")

app = FastAPI()
scheduler = AsyncIOScheduler()

CHANNELS_FILE = "channels.json"
RSS_DIR = Path("rss")
RSS_DIR.mkdir(exist_ok=True)

def load_channels():
    if not Path(CHANNELS_FILE).exists():
        return []
    with open(CHANNELS_FILE) as f:
        return json.load(f)

def save_channels(channels):
    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False, indent=2)

class ChannelCreate(BaseModel):
    name: str
    niche: str
    posts_per_day: int = 6
    tone: str = "Экспертный"
    active: bool = True

class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    niche: Optional[str] = None
    posts_per_day: Optional[int] = None
    tone: Optional[str] = None
    active: Optional[bool] = None

@app.get("/api/channels")
def get_channels():
    return load_channels()

@app.post("/api/channels")
def create_channel(data: ChannelCreate):
    channels = load_channels()
    slug = data.name.lower().replace(" ", "-").replace("/", "-")[:30]
    slug = f"{slug}-{uuid.uuid4().hex[:6]}"
    channel = {
        "id": uuid.uuid4().hex,
        "slug": slug,
        "name": data.name,
        "niche": data.niche,
        "posts_per_day": data.posts_per_day,
        "tone": data.tone,
        "active": data.active,
        "created_at": datetime.utcnow().isoformat(),
        "posts_today": 0,
        "total_posts": 0,
        "last_post_at": None,
        "rss_url": f"/rss/{slug}.xml"
    }
    channels.append(channel)
    save_channels(channels)
    build_rss(channel, [])
    return channel

@app.put("/api/channels/{channel_id}")
def update_channel(channel_id: str, data: ChannelUpdate):
    channels = load_channels()
    for ch in channels:
        if ch["id"] == channel_id:
            for k, v in data.dict(exclude_none=True).items():
                ch[k] = v
            save_channels(channels)
            return ch
    raise HTTPException(404, "Channel not found")

@app.delete("/api/channels/{channel_id}")
def delete_channel(channel_id: str):
    channels = load_channels()
    channels = [ch for ch in channels if ch["id"] != channel_id]
    save_channels(channels)
    return {"ok": True}

@app.post("/api/channels/{channel_id}/generate")
async def manual_generate(channel_id: str):
    channels = load_channels()
    ch = next((c for c in channels if c["id"] == channel_id), None)
    if not ch:
        raise HTTPException(404, "Channel not found")
    await run_channel(ch, channels)
    return {"ok": True, "message": "Пост сгенерирован"}

@app.get("/rss/{slug}.xml")
def get_rss(slug: str):
    path = RSS_DIR / f"{slug}.xml"
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="application/rss+xml")

async def run_channel(ch: dict, channels: list):
    if not ch.get("active"):
        return
    post = await generate_post(ch["niche"], ch["tone"])
    if not post:
        return

    rss_path = RSS_DIR / f"{ch['slug']}.xml"
    existing = []
    if rss_path.exists():
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(rss_path)
            root = tree.getroot()
            channel_el = root.find("channel")
            for item in channel_el.findall("item"):
                existing.append({
                    "title": item.findtext("title", ""),
                    "description": item.findtext("description", ""),
                    "pubDate": item.findtext("pubDate", ""),
                    "guid": item.findtext("guid", "")
                })
        except:
            pass

    new_item = {
        "title": post["title"],
        "description": post["body"],
        "pubDate": datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000"),
        "guid": uuid.uuid4().hex
    }
    items = [new_item] + existing[:29]
    build_rss(ch, items)

    tg_channel = ch.get("telegram_channel") or TELEGRAM_CHANNEL
    if tg_channel:
        tg_text = f"<b>{post['title']}</b>\n\n{post['body']}"
        image_url = await get_image_url(ch["niche"])
        await send_telegram(tg_text, tg_channel, image_url)

    for c in channels:
        if c["id"] == ch["id"]:
            c["total_posts"] = c.get("total_posts", 0) + 1
            c["posts_today"] = c.get("posts_today", 0) + 1
            c["last_post_at"] = datetime.utcnow().isoformat()
    save_channels(channels)

async def scheduled_job():
    channels = load_channels()
    now = datetime.utcnow()
    if now.hour == 0 and now.minute < 30:
        for ch in channels:
            ch["posts_today"] = 0
        save_channels(channels)
    for ch in channels:
        if not ch.get("active"):
            continue
        posts_per_day = ch.get("posts_per_day", 6)
        posts_today = ch.get("posts_today", 0)
        if posts_today < posts_per_day:
            await run_channel(ch, channels)
            channels = load_channels()

@app.on_event("startup")
async def startup():
    scheduler.add_job(scheduled_job, "interval", hours=4, id="main_job")
    scheduler.start()

@app.get("/", response_class=HTMLResponse)
def panel():
    with open("templates/index.html", encoding="utf-8") as f:
        return f.read()
