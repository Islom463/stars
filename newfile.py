"""
APEX SERVIS boti: Stars, Gif, SMM Nakrutka + BEPUL AI yordamchi
AI zanjiri: Google Gemini -> Groq -> OpenRouter (qaysi kalit bo'lsa, shu ishlatiladi).
Model nomlari avtomatik topiladi, biri ishlamasa keyingisiga o'tadi.
Kalitlar Render Environment'dan o'qiladi (o'zgaruvchi nomi muhim emas, kalit turi bo'yicha topiladi).
"""
import os
import html
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
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
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

logging.basicConfig(level=logging.INFO)


# ---------------- Render uchun mini veb-server ----------------
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, *args):
        pass


def run_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), SimpleHandler).serve_forever()


threading.Thread(target=run_server, daemon=True).start()


def self_ping():
    while True:
        time.sleep(300)
        try:
            app_url = os.environ.get("RENDER_EXTERNAL_URL")
            if app_url:
                urllib.request.urlopen(app_url, timeout=20)
        except Exception:
            pass


threading.Thread(target=self_ping, daemon=True).start()


# ---------------- Kalitlarni topish (nomiga emas, turiga qarab) ----------------
def _clean(v):
    return (v or "").strip().strip('"').strip("'").strip()


def detect_keys():
    env = {k: _clean(v) for k, v in os.environ.items()}
    tok_re = r"\d{6,}:[A-Za-z0-9_-]{30,}"
    bot_token = ""
    for k in ("BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "TOKEN"):
        if re.fullmatch(tok_re, env.get(k, "")):
            bot_token = env[k]
            break
    if not bot_token:
        for v in env.values():
            if re.fullmatch(tok_re, v):
                bot_token = v
                break
    smm = env.get("SMM_API_KEY") or next((v for k, v in env.items() if k.upper().startswith("SMM") and v), "")
    gem = groq = orr = ""
    for v in env.values():
        if v.startswith("gsk_") and not groq:
            groq = v
        elif v.startswith("sk-or-") and not orr:
            orr = v
        elif (v.startswith("AIza") or v.startswith("AQ.")) and not gem:
            gem = v
    if not gem:
        for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
            v = env.get(k, "")
            if v and not v.startswith(("gsk_", "sk-or-")):
                gem = v
                break
    return bot_token, smm, gem, groq, orr


BOT_TOKEN, SMM_API_KEY, KEY_GEMINI, KEY_GROQ, KEY_OPENROUTER = detect_keys()
logging.info(
    "Kalitlar: BOT=%s SMM=%s GEMINI=%s GROQ=%s OPENROUTER=%s",
    bool(BOT_TOKEN), bool(SMM_API_KEY), bool(KEY_GEMINI), bool(KEY_GROQ), bool(KEY_OPENROUTER),
)


def stop_with_error(msg: str):
    """Xato bo'lsa ham servis yiqilmasin, logda sabab ko'rinib tursin."""
    while True:
        logging.error(msg)
        time.sleep(30)


if not BOT_TOKEN:
    stop_with_error("BOT_TOKEN topilmadi! Render Environment'ga bot tokenini qo'shing (BOT_TOKEN).")

# ---------------- Sozlamalar ----------------
ADMIN_IDS = [8099636943]
ADMIN_USERNAME = "wezzcs"
CARD_NUMBER = "5614681853951071"
CARD_OWNER = "Panjiyev Muhammadali"
REF_BONUS = 50
TOPUP_TIMEOUT = 5 * 60
MIN_TOPUP = 1000
MAX_TOPUP = 5_000_000

GROUP_LINK = "https://t.me/apex_serv1ce"
SMM_API_URL = "https://justanotherpanel.com/api/v2"

AI_DAILY_LIMIT = 40      # bitta foydalanuvchi uchun kuniga AI savollar soni (bepul limitni tejash uchun)
AI_COOLDOWN = 3          # savollar orasidagi minimal soniya

SMM_SERVICES = {
    "smm_ig_likes": {"name": "❤️ IG Layk (Kamayishlar 0%)", "price_per_1000": 3500, "min": 10, "service_id": 4217},
    "smm_ig_views": {"name": "🎬 IG Reels ko'rish", "price_per_1000": 700, "min": 100, "service_id": 4},
    "smm_ig_subs": {"name": "👥 IG Obunachilar", "price_per_1000": 15500, "min": 50, "service_id": 5},
    "smm_tg_views": {"name": "👁 TG Post ko'rish", "price_per_1000": 1000, "min": 100, "service_id": 1},
    "smm_tg_reactions": {"name": "🔥 TG Reaksiyalar", "price_per_1000": 1500, "min": 50, "service_id": 2},
    "smm_tg_subs": {"name": "👤 TG Obunachilar", "price_per_1000": 12500, "min": 100, "service_id": 3},
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

try:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
except Exception as e:
    stop_with_error(f"BOT_TOKEN yaroqsiz: {e}")
dp = Dispatcher(storage=MemoryStorage())

# ---------------- Baza ----------------
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


def esc(s) -> str:
    return html.escape(str(s))


def ensure_user(uid: int, name: str, ref=None):
    """Yangi foydalanuvchi qo'shadi. Taklif qilgan odam ID sini qaytaradi (bo'lsa)."""
    if one("SELECT 1 FROM users WHERE id=?", (uid,)):
        return None
    if ref == uid or (ref and not one("SELECT 1 FROM users WHERE id=?", (ref,))):
        ref = None
    run("INSERT INTO users(id,name,balance,referrer,joined) VALUES(?,?,?,?,?)", (uid, name, 0, ref, int(time.time())))
    return ref


def get_balance(uid: int) -> int:
    u = one("SELECT balance FROM users WHERE id=?", (uid,))
    return u["balance"] if u else 0


async def notify_admins(text: str, kb=None):
    for a in ADMIN_IDS:
        try:
            await bot.send_message(a, text, reply_markup=kb)
        except Exception as e:
            logging.error(f"Adminga yuborib bo'lmadi: {e}")


async def check_user_subscription(user_id: int) -> bool:
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
                return False
        except Exception as e:
            # Bot kanalda admin bo'lmasa shu xato chiqadi. Foydalanuvchini to'smaymiz.
            logging.warning(f"{channel} tekshirib bo'lmadi (bot kanalga admin qilinmagan bo'lishi mumkin): {e}")
    return True


# ===================== AI START =====================
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
GROQ_BASE = "https://api.groq.com/openai/v1"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
AI_TIMEOUT = aiohttp.ClientTimeout(total=40)

# Afzal ko'rilgan modellar (haqiqiy ro'yxat API'dan olinadi, bu faqat tartib uchun)
GEMINI_PREFERRED = [
    "gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.7-flash", "gemini-3.6-flash",
    "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-flash-latest", "gemini-flash-lite-latest",
]
GROQ_PREFERRED = [
    "openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b", "qwen/qwen3.6-27b",
]
GEMINI_SKIP = ("tts", "image", "live", "audio", "embedding", "robotics", "computer", "omni",
               "imagen", "veo", "lyria", "gemma", "learnlm", "aqa")
GROQ_SKIP = ("whisper", "guard", "safeguard", "tts", "orpheus", "playai", "compound",
             "distil", "embed", "vision")
OPENROUTER_PREFER = ("gpt-oss", "llama-3.3", "qwen", "gemma", "mistral", "deepseek")

_model_cache = {}   # provayder -> (muddat, [modellar])
_bad_until = {}     # (provayder, model) -> vaqt
_provider_off = {}  # provayder -> vaqt (kalit xato bo'lsa)


class AIError(Exception):
    def __init__(self, status, msg):
        super().__init__(f"{status}: {msg}")
        self.status = status
        self.msg = str(msg or "")


def _err_msg(data):
    try:
        e = data.get("error", data)
        if isinstance(e, dict):
            return str(e.get("message") or e)[:300]
        return str(e)[:300]
    except Exception:
        return "noma'lum xato"


def classify_error(e: AIError):
    """-> ('provider'|'model', soniya)"""
    m = e.msg.lower()
    flat = m.replace(" ", "").replace("_", "")
    s = e.status
    if s == 401 or "apikey" in flat or "leaked" in m:
        return "provider", 900
    if s == 404 or any(w in m for w in ("not found", "no longer", "does not exist", "decommission",
                                         "deprecat", "no access", "do not have access")):
        return "model", 6 * 3600
    if s == 429 or "quota" in m or "ratelimit" in flat:
        daily = any(w in flat for w in ("perday", "daily", "tpd", "rpd"))
        return "model", (3600 if daily else 30)
    if s in (500, 502, 503, 504) or "high demand" in m or "overloaded" in m:
        return "model", 60
    return "model", 300


def _mark(provider, model, e: AIError):
    scope, sec = classify_error(e)
    if scope == "provider":
        _provider_off[provider] = time.time() + sec
    else:
        _bad_until[(provider, model)] = time.time() + sec


def build_system_prompt():
    min_star = STARS_PACKAGES[0]
    min_gif = min(p for _, p in GIF_PACKAGES)
    return (
        "Sen «APEX SERVIS» Telegram botining aqlli AI yordamchisisan. "
        "Foydalanuvchi bilan o'zbek tilida (lotin yozuvida), do'stona, qisqa va aniq gaplash. "
        "Foydalanuvchi boshqa tilda yozsa, o'sha tilda javob ber.\n"
        f"Bot xizmatlari: Telegram Stars ({min_star[0]} ⭐ = {fmt(min_star[1])} so'mdan), "
        f"sovg'a Gif'lar ({fmt(min_gif)} so'mdan), SMM nakrutka (Instagram va Telegram: layk, ko'rish, obunachi, reaksiya). "
        "Buyurtma berish uchun pastdagi menyudan «🛍 Buyurtma berish» tugmasini bosish, "
        "balansni «💳 Hisobni to'ldirish» orqali to'ldirish kerak. "
        "Aniq narx, balans yoki buyurtma holatini o'zing to'qima, menyudagi tugmalarga yo'naltir. "
        f"Muammo bo'lsa admin: @{ADMIN_USERNAME}.\n"
        "Umumiy savollarga (maslahat, tarjima, o'qish, kod, ma'lumot) ham yordam ber. "
        "Javobing 1500 belgidan oshmasin."
    )


def _order(preferred, available, extra_sorted=True):
    first = [p for p in preferred if p in available]
    rest = sorted([a for a in available if a not in preferred], reverse=True) if extra_sorted else []
    return first + rest


async def list_models(session, provider):
    c = _model_cache.get(provider)
    if c and c[0] > time.time():
        return c[1]
    models = []
    try:
        if provider == "gemini":
            async with session.get(f"{GEMINI_BASE}/models", params={"pageSize": 200},
                                   headers={"x-goog-api-key": KEY_GEMINI}) as r:
                status, data = r.status, await r.json(content_type=None)
            if status != 200:
                raise AIError(status, _err_msg(data))
            names = []
            for m in data.get("models", []):
                n = str(m.get("name", "")).replace("models/", "")
                if "generateContent" in (m.get("supportedGenerationMethods") or []) \
                        and "flash" in n and not any(w in n for w in GEMINI_SKIP):
                    names.append(n)
            models = _order(GEMINI_PREFERRED, names)
        elif provider == "groq":
            async with session.get(f"{GROQ_BASE}/models", headers={"Authorization": f"Bearer {KEY_GROQ}"}) as r:
                status, data = r.status, await r.json(content_type=None)
            if status != 200:
                raise AIError(status, _err_msg(data))
            names = [m["id"] for m in data.get("data", [])
                     if m.get("active", True) and not any(w in m["id"].lower() for w in GROQ_SKIP)]
            models = _order(GROQ_PREFERRED, names)
        else:  # openrouter
            async with session.get(f"{OPENROUTER_BASE}/models") as r:
                status, data = r.status, await r.json(content_type=None)
            if status != 200:
                raise AIError(status, _err_msg(data))
            free = [m["id"] for m in data.get("data", [])
                    if str(m.get("id", "")).endswith(":free")]
            models = []
            for kw in OPENROUTER_PREFER:
                models += [f for f in free if kw in f.lower() and f not in models]
            models += [f for f in free if f not in models]
            models = models[:8]
    except AIError as e:
        if classify_error(e)[0] == "provider":
            raise
        logging.warning(f"{provider} model ro'yxatini olib bo'lmadi: {e}")
    except Exception as e:
        logging.warning(f"{provider} model ro'yxatini olib bo'lmadi: {e}")
    if not models:   # ro'yxat olinmasa, zaxira nomlar
        models = {"gemini": GEMINI_PREFERRED, "groq": GROQ_PREFERRED, "openrouter": []}[provider][:]
    _model_cache[provider] = (time.time() + 1800, models)
    return models


async def call_gemini(session, model, messages, system):
    contents = [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
                for m in messages]
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 2048, "temperature": 0.7},
    }
    async with session.post(f"{GEMINI_BASE}/models/{model}:generateContent", json=body,
                            headers={"x-goog-api-key": KEY_GEMINI}) as r:
        status, data = r.status, await r.json(content_type=None)
    if status != 200:
        raise AIError(status, _err_msg(data))
    cand = (data.get("candidates") or [{}])[0]
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if not text:
        raise AIError(0, f"bo'sh javob ({cand.get('finishReason', '?')})")
    return text


async def call_openai_compat(session, base, key, model, messages, system, token_param, extra=None):
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
        "temperature": 0.7,
        token_param: 1500,
    }
    if extra:
        payload.update(extra)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with session.post(f"{base}/chat/completions", json=payload, headers=headers) as r:
        status, data = r.status, await r.json(content_type=None)
    if status != 200:
        raise AIError(status, _err_msg(data))
    text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    if not text:
        raise AIError(0, "bo'sh javob")
    return text


async def call_provider(session, provider, model, messages, system):
    if provider == "gemini":
        return await call_gemini(session, model, messages, system)
    if provider == "groq":
        extra = {"reasoning_effort": "low"} if model.startswith("openai/gpt-oss") else None
        return await call_openai_compat(session, GROQ_BASE, KEY_GROQ, model, messages, system,
                                        "max_completion_tokens", extra)
    return await call_openai_compat(session, OPENROUTER_BASE, KEY_OPENROUTER, model, messages, system, "max_tokens")


def _provider_keys():
    return {"gemini": KEY_GEMINI, "groq": KEY_GROQ, "openrouter": KEY_OPENROUTER}


async def ask_ai(messages):
    """-> (javob_matni yoki None, ishlatilgan 'provayder/model', xatolar_ro'yxati)"""
    errors = []
    system = build_system_prompt()
    keys = _provider_keys()
    try:
        async with aiohttp.ClientSession(timeout=AI_TIMEOUT) as session:
            for provider in ("gemini", "groq", "openrouter"):
                if not keys[provider]:
                    continue
                if _provider_off.get(provider, 0) > time.time():
                    errors.append(f"{provider}: kalit ishlamayapti (vaqtincha o'tkazib yuborildi)")
                    continue
                try:
                    models = await list_models(session, provider)
                except AIError as e:
                    errors.append(f"{provider}: {e}")
                    _mark(provider, "-", e)
                    continue
                tried = 0
                for model in models:
                    if _bad_until.get((provider, model), 0) > time.time():
                        continue
                    if tried >= 4:
                        break
                    tried += 1
                    try:
                        text = await call_provider(session, provider, model, messages, system)
                        return text, f"{provider}/{model}", errors
                    except AIError as e:
                        errors.append(f"{provider}/{model}: {e}")
                        _mark(provider, model, e)
                        if classify_error(e)[0] == "provider":
                            break
                    except asyncio.TimeoutError:
                        errors.append(f"{provider}/{model}: vaqt tugadi")
                        _bad_until[(provider, model)] = time.time() + 30
                    except Exception as e:
                        errors.append(f"{provider}/{model}: {type(e).__name__}")
                        _bad_until[(provider, model)] = time.time() + 60
    except Exception as e:
        errors.append(f"tarmoq: {type(e).__name__}")
    # xatolardan kalitlarni tozalash
    safe = []
    for line in errors:
        for k in keys.values():
            if k:
                line = line.replace(k, "***")
        safe.append(line)
    return None, None, safe
# ===================== AI END =====================


# ---------------- Holatlar ----------------
class TopupS(StatesGroup):
    amount = State()


class OrderS(StatesGroup):
    manual = State()
    target = State()


class SmmOrderS(StatesGroup):
    target = State()
    quantity = State()


# ---------------- Klaviaturalar ----------------
def main_menu() -> ReplyKeyboardMarkup:
    rows = [
        ["🛍 Buyurtma berish"],
        ["🛒 Buyurtmalar", "💵 Pul ishlash"],
        ["💳 Hisobim", "💳 Hisobni to'ldirish"],
        ["☎️ Yordam", "📄 Qo'llanma"],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t) for t in r] for r in rows],
        resize_keyboard=True,
    )


def order_type_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Stars olish", callback_data="order:stars")],
            [InlineKeyboardButton(text="🎁 Gif olish", callback_data="order:gifs")],
            [InlineKeyboardButton(text="🚀 SMM Nakrutka", callback_data="order:smm")],
        ]
    )


def stars_packages_kb():
    rows = [[InlineKeyboardButton(text="✍️ Qo'lda hisoblash", callback_data="buy:manual")]]
    row = []
    for stars, price in STARS_PACKAGES:
        row.append(InlineKeyboardButton(text=f"{stars} ⭐️ ({fmt(price)} so'm)", callback_data=f"star:{stars}:{price}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="order_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def gifs_packages_kb():
    rows, row = [], []
    for g_icon, g_price in GIF_PACKAGES:
        row.append(InlineKeyboardButton(text=f"{g_icon} ({fmt(g_price)} so'm)", callback_data=f"gif:{g_icon}:{g_price}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="order_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def smm_services_kb():
    rows = [[InlineKeyboardButton(text=i["name"], callback_data=f"smm_svc:{k}")] for k, i in SMM_SERVICES.items()]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="order_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def sub_kb():
    kb = [[InlineKeyboardButton(text=f"📢 {ch} kanaliga obuna bo'lish", url=f"https://t.me/{ch.lstrip('@')}")] for ch in CHANNELS]
    kb.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def order_admin_kb(oid: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Bajarildi", callback_data=f"od:{oid}"),
        InlineKeyboardButton(text="❌ Bekor (pul qaytadi)", callback_data=f"oc:{oid}"),
    ]])


# ---------------- Start, yordam, obuna ----------------
@dp.message(CommandStart())
async def start(m: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    uid = m.from_user.id

    if not await check_user_subscription(uid):
        return await m.answer("⚠️ Botdan foydalanish uchun kanallarga obuna bo'ling:", reply_markup=sub_kb())

    ref = int(command.args) if command.args and command.args.isdigit() else None
    existed = one("SELECT 1 FROM users WHERE id=?", (uid,))
    inviter = ensure_user(uid, m.from_user.full_name, ref)
    if not existed and inviter:
        run("UPDATE users SET balance=balance+?, ref_count=ref_count+1, ref_earned=ref_earned+? WHERE id=?",
            (REF_BONUS, REF_BONUS, inviter))
        try:
            await bot.send_message(inviter, f"🎉 Do'stingiz qo'shildi! Hisobingizga <b>{fmt(REF_BONUS)} so'm</b> berildi.")
        except Exception:
            pass
    await m.answer("👋 Xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=main_menu())


@dp.callback_query(F.data == "check_sub")
async def process_check_sub(c: CallbackQuery):
    if await check_user_subscription(c.from_user.id):
        ensure_user(c.from_user.id, c.from_user.full_name)
        try:
            await c.message.edit_text("✅ Obuna tasdiqlandi!")
        except Exception:
            pass
        await c.message.answer("👋 Xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=main_menu())
        await c.answer()
    else:
        await c.answer("Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)


@dp.message(Command("help"))
async def help_cmd(m: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="👨‍💻 Admin bilan bog'lanish", url=f"https://t.me/{ADMIN_USERNAME}")]]
    )
    await m.answer(
        "🤖 <b>Yordam bo'limi</b>\n\n"
        "Muammo yoki savolingiz bo'lsa, quyidagi tugma orqali admin bilan bog'laning.\n"
        "Oddiy savollaringizni shu yerga yozsangiz, AI yordamchi javob beradi.",
        reply_markup=kb,
    )


@dp.message(Command("join"))
async def join_cmd(m: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 Rasmiy kanalga o'tish", url=GROUP_LINK)]])
    await m.answer("📢 <b>Asosiy kanalimizga qo'shiling:</b>", reply_markup=kb)


@dp.message(Command("cancel"))
async def cancel_cmd(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("❌ Bekor qilindi.", reply_markup=main_menu())


# ---------------- Asosiy menyu tugmalari ----------------
@dp.message(F.text == "🛍 Buyurtma berish")
async def order_menu(m: Message, state: FSMContext):
    await state.clear()
    ensure_user(m.from_user.id, m.from_user.full_name)
    await m.answer("🎁 Nima sotib olmoqchisiz? Quyidagilardan birini tanlang:", reply_markup=order_type_kb())


@dp.callback_query(F.data == "order_back")
async def order_back_cb(c: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await c.message.edit_text("🎁 Nima sotib olmoqchisiz? Quyidagilardan birini tanlang:", reply_markup=order_type_kb())
    except Exception:
        await c.message.answer("🎁 Nima sotib olmoqchisiz? Quyidagilardan birini tanlang:", reply_markup=order_type_kb())
    await c.answer()


async def _edit_or_send(c: CallbackQuery, text: str, kb):
    try:
        await c.message.edit_text(text, reply_markup=kb)
    except Exception:
        await c.message.answer(text, reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data == "order:stars")
async def order_stars_cb(c: CallbackQuery):
    await _edit_or_send(c, "⭐ Stars miqdorini tanlang:", stars_packages_kb())


@dp.callback_query(F.data == "order:gifs")
async def order_gifs_cb(c: CallbackQuery):
    await _edit_or_send(c, "🎁 Kerakli gifni tanlang:", gifs_packages_kb())


@dp.callback_query(F.data == "order:smm")
async def order_smm_cb(c: CallbackQuery):
    await _edit_or_send(c, "🚀 SMM xizmatini tanlang:", smm_services_kb())


@dp.message(F.text == "🛒 Buyurtmalar")
async def my_orders(m: Message, state: FSMContext):
    await state.clear()
    rows = many("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (m.from_user.id,))
    if not rows:
        return await m.answer("Sizda hali buyurtmalar yo'q.")
    icons = {"pending": "⏳ Kutilmoqda", "processing": "🚀 Bajarilmoqda", "done": "✅ Bajarildi", "cancelled": "❌ Bekor qilindi"}
    text = "🛒 <b>Oxirgi buyurtmalaringiz:</b>\n\n"
    for r in rows:
        text += f"#{r['id']} — {esc(r['item_name'])} → {esc(r['target'])}\n{fmt(r['price'])} so'm | {icons.get(r['status'], r['status'])}\n\n"
    await m.answer(text)


@dp.message(F.text == "💵 Pul ishlash")
async def earn(m: Message, state: FSMContext):
    await state.clear()
    ensure_user(m.from_user.id, m.from_user.full_name)
    me = await bot.get_me()
    u = one("SELECT * FROM users WHERE id=?", (m.from_user.id,))
    await m.answer(
        "💵 <b>Pul ishlash</b>\n\n"
        f"Do'stlaringizni taklif qiling va har biri uchun <b>{fmt(REF_BONUS)} so'm</b> oling!\n\n"
        f"🔗 Havolangiz:\n<code>https://t.me/{me.username}?start={m.from_user.id}</code>\n\n"
        f"👥 Takliflar: <b>{u['ref_count']}</b> ta\n💰 Ishlaganingiz: <b>{fmt(u['ref_earned'])} so'm</b>"
    )


@dp.message(F.text == "💳 Hisobim")
async def account(m: Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    ensure_user(uid, m.from_user.full_name)
    cnt = one("SELECT COUNT(*) c FROM orders WHERE user_id=? AND status='done'", (uid,))["c"]
    await m.answer(f"💳 <b>Hisobim</b>\n\n🆔 ID: <code>{uid}</code>\n💰 Balans: <b>{fmt(get_balance(uid))} so'm</b>\n🛒 Bajarilgan: {cnt}")


@dp.message(F.text == "☎️ Yordam")
async def help_text_btn(m: Message, state: FSMContext):
    await help_cmd(m, state)


@dp.message(F.text == "📄 Qo'llanma")
async def guide(m: Message, state: FSMContext):
    await state.clear()
    guide_text = (
        "📄 <b>Botdan foydalanish qo'llanmasi:</b>\n\n"
        "1️⃣ <b>Hisobni to'ldirish:</b> «💳 Hisobni to'ldirish» tugmasini bosib, summani kiriting va ko'rsatilgan kartaga o'tkazma qiling.\n"
        "2️⃣ <b>Buyurtma berish:</b> «🛍 Buyurtma berish» bo'limidan Telegram Stars, Sovg'a Giflar yoki SMM xizmatlarini tanlang.\n"
        "3️⃣ <b>Pul ishlash:</b> «💵 Pul ishlash» orqali taklif havolangizni do'stlaringizga ulashib bonus oling!\n"
        "4️⃣ <b>AI yordamchi:</b> istalgan savolingizni oddiy yozing, AI javob beradi.\n\n"
        "Bekor qilish uchun /cancel yozing."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 Asosiy kanal", url=GROUP_LINK)]])
    await m.answer(guide_text, reply_markup=kb)


# ---------------- Hisobni to'ldirish ----------------
@dp.message(F.text == "💳 Hisobni to'ldirish")
async def topup_start(m: Message, state: FSMContext):
    ensure_user(m.from_user.id, m.from_user.full_name)
    await state.set_state(TopupS.amount)
    await m.answer(f"💳 Qancha so'm kiritmoqchisiz? ({fmt(MIN_TOPUP)} - {fmt(MAX_TOPUP)}):")


@dp.message(TopupS.amount, F.text)
async def topup_amount(m: Message, state: FSMContext):
    digits = re.sub(r"\D", "", m.text)
    if not digits or not (MIN_TOPUP <= int(digits) <= MAX_TOPUP):
        return await m.answer(f"❗ Xato summa. {fmt(MIN_TOPUP)} dan {fmt(MAX_TOPUP)} gacha kiriting.")
    amount = int(digits)
    await state.clear()
    now = int(time.time())
    tid = run(
        "INSERT INTO topups(user_id,amount,status,created,expires) VALUES(?,?,?,?,?)",
        (m.from_user.id, amount, "new", now, now + TOPUP_TIMEOUT),
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ To'lov qildim", callback_data=f"paid:{tid}")
    kb.button(text="❌ Bekor qilish", callback_data=f"tcancel:{tid}")
    kb.adjust(1)
    msg = await m.answer(
        f"💳 <b>To'lov ma'lumotlari</b>\n\nKarta: <code>{CARD_NUMBER}</code>\nEgasi: <b>{CARD_OWNER}</b>\n"
        f"Summa: <b>{fmt(amount)} so'm</b>\n\n⏳ 5 daqiqa ichida to'lab, «To'lov qildim» ni bosing.",
        reply_markup=kb.as_markup(),
    )
    asyncio.create_task(expire_later(tid, msg.chat.id, msg.message_id))


async def expire_later(tid: int, chat_id: int, msg_id: int):
    await asyncio.sleep(TOPUP_TIMEOUT + 2)
    row = one("SELECT status FROM topups WHERE id=?", (tid,))
    if row and row["status"] == "new":
        run("UPDATE topups SET status='expired' WHERE id=?", (tid,))
        try:
            await bot.edit_message_text("⌛️ Vaqt tugadi.", chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass


@dp.callback_query(F.data.startswith("tcancel:"))
async def topup_cancel(c: CallbackQuery):
    tid = int(c.data.split(":")[1])
    t = one("SELECT * FROM topups WHERE id=?", (tid,))
    if t and t["user_id"] == c.from_user.id and t["status"] == "new":
        run("UPDATE topups SET status='cancelled' WHERE id=?", (tid,))
        try:
            await c.message.edit_text("❌ Bekor qilindi.")
        except Exception:
            pass
    await c.answer()


@dp.callback_query(F.data.startswith("paid:"))
async def topup_paid(c: CallbackQuery):
    tid = int(c.data.split(":")[1])
    t = one("SELECT * FROM topups WHERE id=?", (tid,))
    if not t or t["user_id"] != c.from_user.id or t["status"] != "new":
        return await c.answer("Bu so'rov faol emas.", show_alert=True)
    run("UPDATE topups SET status='checking' WHERE id=?", (tid,))
    try:
        await c.message.edit_text("⏳ Admin tekshirmoqda. Tez orada balansingiz to'ldiriladi.")
    except Exception:
        pass
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash", callback_data=f"tok:{tid}")
    kb.button(text="❌ Rad etish", callback_data=f"tno:{tid}")
    kb.adjust(2)
    await notify_admins(
        f"💰 To'lov so'rovi #{tid}: <b>{fmt(t['amount'])} so'm</b>\n"
        f"Foydalanuvchi: {esc(c.from_user.full_name)} (<code>{t['user_id']}</code>)",
        kb.as_markup(),
    )
    await c.answer()


@dp.callback_query(F.data.startswith(("tok:", "tno:")))
async def topup_admin(c: CallbackQuery):
    if c.from_user.id not in ADMIN_IDS:
        return await c.answer("Ruxsat yo'q", show_alert=True)
    action, tid = c.data.split(":")
    t = one("SELECT * FROM topups WHERE id=?", (int(tid),))
    if not t:
        return await c.answer("Topilmadi", show_alert=True)
    if t["status"] != "checking":
        return await c.answer("Bu so'rov allaqachon ko'rib chiqilgan.", show_alert=True)
    if action == "tok":
        run("UPDATE topups SET status='approved' WHERE id=?", (t["id"],))
        run("UPDATE users SET balance=balance+? WHERE id=?", (t["amount"], t["user_id"]))
        try:
            await c.message.edit_text(f"✅ Tasdiqlandi (#{t['id']}, {fmt(t['amount'])} so'm)")
        except Exception:
            pass
        try:
            await bot.send_message(t["user_id"], f"✅ Balansingiz {fmt(t['amount'])} so'mga to'ldirildi!")
        except Exception:
            pass
    else:
        run("UPDATE topups SET status='rejected' WHERE id=?", (t["id"],))
        try:
            await c.message.edit_text(f"❌ Rad etildi (#{t['id']})")
        except Exception:
            pass
        try:
            await bot.send_message(t["user_id"], "❌ To'lovingiz rad etildi. Muammo bo'lsa, admin bilan bog'laning.")
        except Exception:
            pass
    await c.answer()


# ---------------- Stars / Gif buyurtma ----------------
@dp.callback_query(F.data == "buy:manual")
async def buy_manual(c: CallbackQuery, state: FSMContext):
    await state.set_state(OrderS.manual)
    await c.message.answer(f"✍️ Nechta ⭐ kerak? ({MIN_STARS} - {MAX_STARS})")
    await c.answer()


@dp.callback_query(F.data.startswith("star:"))
async def buy_star_package(c: CallbackQuery, state: FSMContext):
    _, stars_str, price_str = c.data.split(":")
    await ask_target_for_item(c.message, state, c.from_user.id, "star", f"{stars_str} ⭐️", int(price_str))
    await c.answer()


@dp.callback_query(F.data.startswith("gif:"))
async def buy_gif_package(c: CallbackQuery, state: FSMContext):
    _, g_icon, price_str = c.data.split(":")
    await ask_target_for_item(c.message, state, c.from_user.id, "gif", f"Gif {g_icon}", int(price_str))
    await c.answer()


@dp.message(OrderS.manual, F.text)
async def manual_stars(m: Message, state: FSMContext):
    digits = re.sub(r"\D", "", m.text)
    if not digits or not (MIN_STARS <= int(digits) <= MAX_STARS):
        return await m.answer(f"❗ Xato miqdor. {MIN_STARS} dan {MAX_STARS} gacha kiriting.")
    stars = int(digits)
    await ask_target_for_item(m, state, m.from_user.id, "star", f"{stars} ⭐️", stars * 215)


async def ask_target_for_item(msg: Message, state: FSMContext, uid: int, item_type: str, item_name: str, price: int):
    if get_balance(uid) < price:
        await state.clear()
        return await msg.answer(
            f"❗ Balans yetarli emas.\nKerak: <b>{fmt(price)} so'm</b>\nBalansingiz: <b>{fmt(get_balance(uid))} so'm</b>\n\n"
            "«💳 Hisobni to'ldirish» orqali balansni to'ldiring."
        )
    await state.set_state(OrderS.target)
    await state.update_data(item_type=item_type, item_name=item_name, price=price)
    await msg.answer(
        f"📦 Tanlandi: <b>{esc(item_name)}</b>\n💰 Narxi: <b>{fmt(price)} so'm</b>\n\n"
        "Qabul qiluvchi <b>@username</b> yoki <b>ID</b> ni kiriting:\n(Bekor qilish: /cancel)"
    )


@dp.message(OrderS.target, F.text)
async def order_target(m: Message, state: FSMContext):
    target = m.text.strip()
    data = await state.get_data()
    price = data.get("price", 0)
    uid = m.from_user.id
    await state.clear()

    if not data or price <= 0:
        return await m.answer("❗ Xatolik, qaytadan urinib ko'ring.")
    if get_balance(uid) < price:
        return await m.answer("❗ Balans yetarli emas.")

    run("UPDATE users SET balance=balance-? WHERE id=?", (price, uid))
    oid = run(
        "INSERT INTO orders(user_id,item_type,item_name,price,target,status,created) VALUES(?,?,?,?,?,?,?)",
        (uid, data["item_type"], data["item_name"], price, target, "pending", int(time.time())),
    )
    await m.answer(
        f"✅ <b>Buyurtmangiz qabul qilindi! (#{oid})</b>\n\n📦 {esc(data['item_name'])}\n"
        f"🎯 {esc(target)}\n💵 {fmt(price)} so'm\n\nTez orada bajariladi!",
        reply_markup=main_menu(),
    )
    await notify_admins(
        f"🛍 <b>Buyurtma #{oid}</b>\nBuyurtmachi: {esc(m.from_user.full_name)} (<code>{uid}</code>)\n"
        f"Kimga: {esc(target)}\nMahsulot: {esc(data['item_name'])}\nSumma: {fmt(price)} so'm",
        order_admin_kb(oid),
    )


@dp.callback_query(F.data.startswith(("od:", "oc:")))
async def order_admin(c: CallbackQuery):
    if c.from_user.id not in ADMIN_IDS:
        return await c.answer("Ruxsat yo'q", show_alert=True)
    action, oid = c.data.split(":")
    o = one("SELECT * FROM orders WHERE id=?", (int(oid),))
    if not o:
        return await c.answer("Topilmadi", show_alert=True)
    if o["status"] in ("done", "cancelled"):
        return await c.answer("Bu buyurtma allaqachon yopilgan.", show_alert=True)
    if action == "od":
        run("UPDATE orders SET status='done' WHERE id=?", (o["id"],))
        note, user_msg = "✅ Bajarildi", f"✅ Buyurtma #{o['id']} bajarildi! Rahmat."
    else:
        run("UPDATE orders SET status='cancelled' WHERE id=?", (o["id"],))
        run("UPDATE users SET balance=balance+? WHERE id=?", (o["price"], o["user_id"]))
        note = "❌ Bekor qilindi, pul qaytarildi"
        user_msg = f"❌ Buyurtma #{o['id']} bekor qilindi. {fmt(o['price'])} so'm balansingizga qaytarildi."
    try:
        await c.message.edit_text(f"{c.message.html_text}\n\n<b>{note}</b>")
    except Exception:
        pass
    try:
        await bot.send_message(o["user_id"], user_msg)
    except Exception:
        pass
    await c.answer()


# ---------------- SMM Nakrutka ----------------
async def send_smm_order(service_id: int, link: str, quantity: int):
    payload = {"key": SMM_API_KEY, "action": "add", "service": service_id, "link": link, "quantity": quantity}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(SMM_API_URL, data=payload) as resp:
                return await resp.json(content_type=None)
    except Exception as e:
        logging.error(f"SMM API Error: {e}")
        return None


@dp.callback_query(F.data.startswith("smm_svc:"))
async def smm_service_selected(c: CallbackQuery, state: FSMContext):
    svc_key = c.data.replace("smm_svc:", "")
    svc_info = SMM_SERVICES.get(svc_key)
    if not svc_info:
        return await c.answer("Xizmat topilmadi", show_alert=True)
    await state.update_data(
        smm_key=svc_key, smm_name=svc_info["name"], price_1k=svc_info["price_per_1000"],
        min_qty=svc_info["min"], service_id=svc_info["service_id"],
    )
    await state.set_state(SmmOrderS.target)
    text = (
        f"🚀 <b>{esc(svc_info['name'])}</b>\n"
        f"💰 Narx: 1000 ta = {fmt(svc_info['price_per_1000'])} so'm\n\n"
        "🔗 Havolani (link) yuboring:\n(Bekor qilish: /cancel)"
    )
    try:
        await c.message.edit_text(text)
    except Exception:
        await c.message.answer(text)
    await c.answer()


@dp.message(SmmOrderS.target, F.text)
async def smm_target_received(m: Message, state: FSMContext):
    link = m.text.strip()
    data = await state.get_data()
    svc_key = data.get("smm_key", "")

    is_instagram = "instagram.com" in link or "instagr.am" in link
    is_telegram = "t.me/" in link or link.startswith("@")

    if "_tg_" in svc_key and not is_telegram:
        return await m.answer("❌ Telegram havolasi noto'g'ri kiritildi. Masalan: https://t.me/kanal/123")
    if "_ig_" in svc_key and not is_instagram:
        return await m.answer("❌ Instagram havolasi noto'g'ri kiritildi. Masalan: https://instagram.com/...")
    if link.startswith("@"):
        link = "https://t.me/" + link[1:]

    await state.update_data(target=link)
    await state.set_state(SmmOrderS.quantity)
    await m.answer(f"🔢 Soni qancha bo'lsin? (Minimal: {data['min_qty']} ta)")


@dp.message(SmmOrderS.quantity, F.text)
async def smm_quantity_received(m: Message, state: FSMContext):
    if not m.text.strip().isdigit():
        return await m.answer("❗ Faqat raqam kiriting!")
    qty = int(m.text.strip())
    data = await state.get_data()

    if qty < data["min_qty"]:
        return await m.answer(f"❗ Minimal miqdor {data['min_qty']} tadan kam bo'lmasligi kerak.")

    total_price = int((qty / 1000) * data["price_1k"])
    if total_price <= 0:
        return await m.answer("❗ Miqdor juda kichik.")
    uid = m.from_user.id

    if get_balance(uid) < total_price:
        await state.clear()
        return await m.answer(
            f"❗ Balans yetarli emas.\nKerak: <b>{fmt(total_price)} so'm</b>\nBalansingiz: <b>{fmt(get_balance(uid))} so'm</b>"
        )

    run("UPDATE users SET balance=balance-? WHERE id=?", (total_price, uid))
    api_res = await send_smm_order(data["service_id"], data["target"], qty)

    ok = isinstance(api_res, dict) and "order" in api_res
    if ok:
        status, panel_text = "processing", "🚀 Avtomatik yuborildi"
    else:
        status, panel_text = "pending", "⚠️ Panelga yuborishda xatolik (Admin tekshiradi)"
        logging.error(f"SMM panel javobi: {api_res}")

    item_name = f"{data['smm_name']} ({qty} ta)"
    oid = run(
        "INSERT INTO orders(user_id,item_type,item_name,price,target,status,created) VALUES(?,?,?,?,?,?,?)",
        (uid, "smm", item_name, total_price, data["target"], status, int(time.time())),
    )
    await state.clear()
    await m.answer(f"✅ <b>SMM Buyurtma #{oid} qabul qilindi!</b>\nHolati: {panel_text}\nSumma: {fmt(total_price)} so'm")

    if not ok:
        err = esc(api_res.get("error", "")) if isinstance(api_res, dict) else "javob yo'q"
        await notify_admins(
            f"⚠️ <b>SMM buyurtma #{oid} panelga ketmadi!</b>\nSabab: {err}\n"
            f"Foydalanuvchi: {esc(m.from_user.full_name)} (<code>{uid}</code>)\n"
            f"{esc(item_name)}\nLink: {esc(data['target'])}\nSumma: {fmt(total_price)} so'm",
            order_admin_kb(oid),
        )


# ---------------- Admin buyruqlari ----------------
def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


@dp.message(Command("admin"))
async def admin_help(m: Message):
    if not is_admin(m.from_user.id):
        return
    await m.answer(
        "🛠 <b>Admin buyruqlari</b>\n\n"
        "/stats — statistika\n"
        "/aitest — AI ishlayotganini tekshirish\n"
        "/addbalance <code>ID SUMMA</code> — balans qo'shish\n"
        "/broadcast <code>MATN</code> — hammaga xabar yuborish"
    )


@dp.message(Command("stats"))
async def admin_stats(m: Message):
    if not is_admin(m.from_user.id):
        return
    users = one("SELECT COUNT(*) c FROM users")["c"]
    orders = one("SELECT COUNT(*) c FROM orders")["c"]
    pend = one("SELECT COUNT(*) c FROM orders WHERE status='pending'")["c"]
    top = one("SELECT COALESCE(SUM(amount),0) s FROM topups WHERE status='approved'")["s"]
    await m.answer(
        f"📊 <b>Statistika</b>\n\n👥 Foydalanuvchilar: {users}\n🛒 Buyurtmalar: {orders}\n"
        f"⏳ Kutilayotgan: {pend}\n💰 Jami to'ldirilgan: {fmt(top)} so'm"
    )


@dp.message(Command("addbalance"))
async def admin_addbalance(m: Message, command: CommandObject):
    if not is_admin(m.from_user.id):
        return
    parts = (command.args or "").split()
    if len(parts) != 2 or not parts[0].isdigit() or not re.fullmatch(r"-?\d+", parts[1]):
        return await m.answer("Format: /addbalance ID SUMMA")
    uid, amount = int(parts[0]), int(parts[1])
    if not one("SELECT 1 FROM users WHERE id=?", (uid,)):
        return await m.answer("❗ Bunday foydalanuvchi topilmadi.")
    run("UPDATE users SET balance=balance+? WHERE id=?", (amount, uid))
    await m.answer(f"✅ {uid} balansi {fmt(amount)} so'mga o'zgardi. Yangi balans: {fmt(get_balance(uid))} so'm")
    try:
        await bot.send_message(uid, f"💰 Balansingiz {fmt(amount)} so'mga o'zgartirildi.")
    except Exception:
        pass


@dp.message(Command("broadcast"))
async def admin_broadcast(m: Message, command: CommandObject):
    if not is_admin(m.from_user.id):
        return
    text = command.args
    if not text:
        return await m.answer("Format: /broadcast MATN")
    sent = failed = 0
    for u in many("SELECT id FROM users"):
        try:
            await bot.send_message(u["id"], text, parse_mode=None)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await m.answer(f"📣 Yuborildi: {sent}, yetmadi: {failed}")


@dp.message(Command("aitest"))
async def ai_test(m: Message):
    if not is_admin(m.from_user.id):
        return
    info = (
        f"🔑 Gemini kaliti: {'✅' if KEY_GEMINI else '❌ yo`q'}\n"
        f"🔑 Groq kaliti: {'✅' if KEY_GROQ else '❌ yo`q'}\n"
        f"🔑 OpenRouter kaliti: {'✅' if KEY_OPENROUTER else '— (ixtiyoriy)'}"
    )
    wait = await m.answer(info + "\n\n⏳ Sinab ko'rilmoqda...", parse_mode=None)
    text, used, errors = await ask_ai([{"role": "user", "content": "Salom! Bir jumlada o'zingni tanishtir."}])
    out = info + "\n\n"
    if text:
        out += f"✅ Ishladi: {used}\n\n{text[:500]}"
    else:
        out += "❌ Hech biri ishlamadi."
    if errors:
        out += "\n\nXatolar:\n" + "\n".join(errors[:8])
    try:
        await wait.edit_text(out[:4000], parse_mode=None)
    except Exception:
        await m.answer(out[:4000], parse_mode=None)


# ---------------- AI yordamchi (menyu tugmalari va holatlardan keyin ishlaydi) ----------------
ai_hist = {}
ai_last = {}
ai_count = {}
ai_alert_ts = 0


def trim_hist(hist):
    del hist[:-8]
    while hist and hist[0]["role"] != "user":
        hist.pop(0)


@dp.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def chat_with_ai(message: Message):
    global ai_alert_ts
    uid = message.from_user.id
    now = time.time()
    day = time.strftime("%Y-%m-%d")
    used_today = 0
    if not is_admin(uid):
        if now - ai_last.get(uid, 0) < AI_COOLDOWN:
            return await message.answer("⏳ Iltimos, biroz kuting...")
        d, used_today = ai_count.get(uid, (day, 0))
        if d != day:
            used_today = 0
        if used_today >= AI_DAILY_LIMIT:
            return await message.answer(f"❗ Bugungi AI limitingiz ({AI_DAILY_LIMIT} ta savol) tugadi. Ertaga qayta urinib ko'ring.")
    ai_last[uid] = now

    wait_msg = await message.answer("⏳ O'ylayapman...")
    hist = ai_hist.setdefault(uid, [])
    hist.append({"role": "user", "content": message.text[:3000]})
    trim_hist(hist)

    text, used, errors = await ask_ai(hist)
    if text:
        ai_count[uid] = (day, used_today + 1)
        hist.append({"role": "assistant", "content": text})
        trim_hist(hist)
        logging.info(f"AI javob berdi: {used}")
        chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)] or ["..."]
        try:
            await wait_msg.edit_text(chunks[0], parse_mode=None)
        except Exception:
            await message.answer(chunks[0], parse_mode=None)
        for ch in chunks[1:]:
            await message.answer(ch, parse_mode=None)
    else:
        if hist:
            hist.pop()
        logging.error("AI hech qaysi manbadan javob ololmadi: " + " | ".join(errors))
        try:
            await wait_msg.edit_text("🤖 Hozir AI band yoki bepul limit tugagan. Birozdan keyin qayta urinib ko'ring.", parse_mode=None)
        except Exception:
            pass
        if now - ai_alert_ts > 600:   # adminga 10 daqiqada 1 marta xabar
            ai_alert_ts = now
            await notify_admins("⚠️ AI ishlamayapti.\n" + "\n".join(errors[:6]) + "\n\nBatafsil: /aitest", None)


async def main():
    me = await bot.get_me()
    print("AI Bot ishga tushdi: @" + me.username, flush=True)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
