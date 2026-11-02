"""
Telegram Stars, Gif va SMM Nakrutka boti - Google Gemini AI versiya
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


def get_env(exact_names, prefix):
    for n in exact_names:
        v = os.environ.get(n)
        if v and v.strip():
            return v.strip().strip('"').strip("'")
    for k, v in os.environ.items():
        if k.upper().startswith(prefix) and v and v.strip():
            return v.strip().strip('"').strip("'")
    return ""


BOT_TOKEN = get_env(["BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "TOKEN"], "BOT_")
# Endi Gemini yoki OpenAI kalitini o'qiydi
GEMINI_API_KEY = get_env(["GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"], "GEMINI")
SMM_API_KEY = get_env(["SMM_API_KEY"], "SMM")

logging.info(
    "Kalitlar: BOT=%s GEMINI=%s SMM=%s",
    bool(BOT_TOKEN), bool(GEMINI_API_KEY), bool(SMM_API_KEY),
)


def stop_with_error(msg: str):
    while True:
        logging.error(msg)
        time.sleep(30)


if not BOT_TOKEN or ":" not in BOT_TOKEN:
    stop_with_error("BOT_TOKEN topilmadi yoki noto'g'ri!")

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
    if one("SELECT 1 FROM users WHERE id=?", (uid,)):
        return False
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
        except Exception:
            pass


async def check_user_subscription(user_id: int) -> bool:
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
                return False
        except Exception:
            pass
    return True


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


@dp.message(CommandStart())
async def start(m: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    if not await check_user_subscription(uid):
        return await m.answer("⚠️ Botdan foydalanish uchun kanallarga obuna bo'ling:", reply_markup=sub_kb())
    ensure_user(uid, m.from_user.full_name)
    await m.answer("👋 Xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=main_menu())


@dp.callback_query(F.data == "check_sub")
async def process_check_sub(c: CallbackQuery):
    if await check_user_subscription(c.from_user.id):
        ensure_user(c.from_user.id, c.from_user.full_name)
        try:
            await c.message.edit_text("✅ Obuna tasdiqlandi!")
        except Exception:
            pass
        await c.message.answer("👋 Xush kelibsiz!", reply_markup=main_menu())
        await c.answer()
    else:
        await c.answer("Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)


@dp.message(Command("help"))
async def help_cmd(m: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👨‍💻 Admin bilan bog'lanish", url=f"https://t.me/{ADMIN_USERNAME}")]])
    await m.answer("🤖 <b>Yordam bo'limi</b>", reply_markup=kb)


@dp.message(Command("cancel"))
async def cancel_cmd(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("❌ Bekor qilindi.", reply_markup=main_menu())


@dp.message(F.text == "🛍 Buyurtma berish")
async def order_menu(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("🎁 Nima sotib olmoqchisiz?", reply_markup=order_type_kb())


@dp.callback_query(F.data == "order_back")
async def order_back_cb(c: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await c.message.edit_text("🎁 Nima sotib olmoqchisiz?", reply_markup=order_type_kb())
    except Exception:
        pass
    await c.answer()


@dp.callback_query(F.data == "order:stars")
async def order_stars_cb(c: CallbackQuery):
    await c.message.edit_text("⭐ Stars miqdorini tanlang:", reply_markup=stars_packages_kb())
    await c.answer()


@dp.callback_query(F.data == "order:gifs")
async def order_gifs_cb(c: CallbackQuery):
    await c.message.edit_text("🎁 Kerakli gifni tanlang:", reply_markup=gifs_packages_kb())
    await c.answer()


@dp.callback_query(F.data == "order:smm")
async def order_smm_cb(c: CallbackQuery):
    await c.message.edit_text("🚀 SMM xizmatini tanlang:", reply_markup=smm_services_kb())
    await c.answer()


@dp.message(F.text == "🛒 Buyurtmalar")
async def my_orders(m: Message, state: FSMContext):
    await state.clear()
    rows = many("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (m.from_user.id,))
    if not rows:
        return await m.answer("Sizda hali buyurtmalar yo'q.")
    text = "🛒 <b>Oxirgi buyurtmalaringiz:</b>\n\n"
    for r in rows:
        text += f"#{r['id']} — {esc(r['item_name'])} | {fmt(r['price'])} so'm\n"
    await m.answer(text)


@dp.message(F.text == "💵 Pul ishlash")
async def earn(m: Message, state: FSMContext):
    await state.clear()
    me = await bot.get_me()
    u = one("SELECT * FROM users WHERE id=?", (m.from_user.id,))
    await m.answer(f"💵 <b>Pul ishlash</b>\n🔗 Havolangiz: https://t.me/{me.username}?start={m.from_user.id}")


@dp.message(F.text == "💳 Hisobim")
async def account(m: Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    await m.answer(f"💳 <b>Hisobim</b>\n💰 Balans: {fmt(get_balance(uid))} so'm")


@dp.message(F.text == "☎️ Yordam")
async def help_text_btn(m: Message, state: FSMContext):
    await help_cmd(m, state)


@dp.message(F.text == "📄 Qo'llanma")
async def guide(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("📄 Botdan foydalanish qo'llanmasi.")


class TopupS(StatesGroup):
    amount = State()


class OrderS(StatesGroup):
    manual = State()
    target = State()


class SmmOrderS(StatesGroup):
    target = State()
    quantity = State()


@dp.message(F.text == "💳 Hisobni to'ldirish")
async def topup_start(m: Message, state: FSMContext):
    await state.set_state(TopupS.amount)
    await m.answer(f"💳 Qancha so'm kiritmoqchisiz? ({fmt(MIN_TOPUP)} - {fmt(MAX_TOPUP)}):")


@dp.message(TopupS.amount, F.text)
async def topup_amount(m: Message, state: FSMContext):
    digits = re.sub(r"\D", "", m.text)
    if not digits or not (MIN_TOPUP <= int(digits) <= MAX_TOPUP):
        return await m.answer("❗ Xato summa.")
    amount = int(digits)
    await state.clear()
    run("INSERT INTO topups(user_id,amount,status,created,expires) VALUES(?,?,?,?,?)", (m.from_user.id, amount, "new", int(time.time()), int(time.time()) + 300))
    await m.answer(f"Karta: <code>{CARD_NUMBER}</code>\nSumma: {fmt(amount)} so'm")


# --- Google Gemini AI Chat ---
ai_hist = {}


@dp.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def chat_with_gemini(message: Message):
    wait_msg = await message.answer("⏳ O'ylayapman...")
    if not GEMINI_API_KEY:
        return await wait_msg.edit_text("❌ Gemini API kaliti topilmadi!", parse_mode=None)

    uid = message.from_user.id
    hist = ai_hist.setdefault(uid, [])
    hist.append({"role": "user", "parts": [{"text": message.text}]})
    del hist[:-8]

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": hist}
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            async with session.post(url, json=payload) as resp:
                res_json = await resp.json(content_type=None)
                if resp.status == 200 and "candidates" in res_json:
                    answer = res_json["candidates"][0]["content"]["parts"][0]["text"][:4000]
                    hist.append({"role": "model", "parts": [{"text": answer}]})
                    del hist[:-8]
                    await wait_msg.edit_text(answer, parse_mode=None)
                else:
                    hist.pop()
                    err_msg = res_json.get("error", {}).get("message", "Noma'lum xatolik")
                    await wait_msg.edit_text(f"❌ AI xatosi: {err_msg}", parse_mode=None)
    except Exception as e:
        if hist:
            hist.pop()
        await wait_msg.edit_text("❌ Sun'iy intellekt bilan bog'lanishda xatolik.", parse_mode=None)


async def main():
    me = await bot.get_me()
    print("AI Bot ishga tushdi: @" + me.username, flush=True)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
