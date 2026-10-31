"""
Telegram Stars, Gif va Avtomatik SMM Nakrutka boti (aiogram 3.x) - Havola tekshiruvi bilan
"""
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import urllib.request
import time
import aiohttp
import asyncio
import logging
import re
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

def self_ping():
    while True:
        time.sleep(300)
        try:
            app_url = os.environ.get("RENDER_EXTERNAL_URL")
            if app_url:
                urllib.request.urlopen(app_url)
        except Exception:
            pass

threading.Thread(target=self_ping, daemon=True).start()

# ===================== SOZLAMALAR =====================
BOT_TOKEN = "9278626308:AAGIVO-g2F6cz2OnQX4vaWx6jGeDkwO8O44"
ADMIN_IDS = [8099636943]
ADMIN_USERNAME = "wezzcs"  # @ belgisiz yozilsa tugma uchun qulay
CARD_NUMBER = "5614681853951071"
CARD_OWNER = "Panjiyev Muhammadali"
REF_BONUS = 50
TOPUP_TIMEOUT = 5 * 60
MIN_TOPUP = 1000
MAX_TOPUP = 5_000_000

# 🔴 BU YERGA O'Z GURUHINGIZ HAVOLASINI YOZING (MASALAN: https://t.me/sizning_guruh_username)
GROUP_LINK = "https://t.me/apex_server_b0t"  

# UzSMM Panel API Sozlamalari
SMM_API_URL = "https://uzsmmpanel.pp.ua/api/v2"
SMM_API_KEY = "4abab7a5f4119fb078df3f971e6bb765"

# SMM Xizmatlari va Service ID lari
SMM_SERVICES = {
    "smm_ig_likes": {"name": "❤️ IG Layk (Kamayishlar 0%)", "price_per_1000": 3000, "min": 10, "service_id": 4217},
    "smm_ig_views": {"name": "🎬 IG Reels ko'rish", "price_per_1000": 200, "min": 100, "service_id": 4},
    "smm_ig_subs": {"name": "👥 IG Obunachilar", "price_per_1000": 15000, "min": 50, "service_id": 5},
    "smm_tg_views": {"name": "👁 TG Post ko'rish", "price_per_1000": 500, "min": 100, "service_id": 1},
    "smm_tg_reactions": {"name": "🔥 TG Reaksiyalar", "price_per_1000": 1000, "min": 50, "service_id": 2},
    "smm_tg_subs": {"name": "👤 TG Obunachilar", "price_per_1000": 12000, "min": 100, "service_id": 3},
}

STARS_PACKAGES = [
    (50, 11000), (100, 22000), (250, 54000), (300, 65000), (350, 75500),
    (500, 108000), (750, 161500), (1000, 215500), (1500, 323000), (2500, 538000),
]
MIN_STARS = 50
MAX_STARS = 10_000

GIF_PACKAGES = [
    ("🐻", 5000), ("💝", 5000), ("🎁", 7000), ("🌹", 7000), ("🎂", 10000),
    ("💐", 10000), ("🚀", 10000), ("🏆", 22000), ("💍", 22000), ("💎", 22000), ("🍾", 10000),
]

CHANNELS = ["@panjiyev_24", "@apex_server_b0t"]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

db = sqlite3.connect("bot.db", check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY, name TEXT, balance INTEGER DEFAULT 0,
    referrer INTEGER, ref_count INTEGER DEFAULT 0, ref_earned INTEGER DEFAULT 0,
    joined INTEGER);
CREATE TABLE IF NOT EXISTS topups(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER,
    status TEXT, created INTEGER, expires INTEGER);
CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_type TEXT, item_name TEXT,
    price INTEGER, target TEXT, status TEXT, created INTEGER);
""")
db.commit()

def run(sql, args=()):
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid

def one(sql, args=()):
    return db.execute(sql, args).fetchone()

def many(sql, args=()):
    return db.execute(sql, args).fetchall()

def fmt(n: int) -> str:
    return f"{n:,}"

async def check_user_
