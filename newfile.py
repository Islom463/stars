"""
Telegram Stars, Gif va SMM Nakrutka boti - Groq (Llama 3.1) AI versiya
Kalitlar Render Environment'dan o'qiladi (nomi BOT_..., GROQ_..., SMM_... bilan boshlansa ham topadi).
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


# ---------------- Kalitlarni Environment'dan olish ----------------
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
GROQ_API_KEY = get_env(["GROQ_API_KEY", "OPENAI_API_KEY"], "GROQ")
SMM_API_KEY = get_env(["SMM_API_KEY"], "SMM")

logging.info(
    "Kalitlar: BOT=%s GROQ=%s SMM=%s",
    bool(BOT_TOKEN), bool(GROQ_API_KEY), bool(SMM_API_KEY),
)
if GROQ_API_KEY and not GROQ_API_KEY.startswith("gsk_"):
    logging.warning("GROQ kalit 'gsk_' bilan boshlanmayapti, noto'g'ri kalit bo'lishi mumkin!")


def stop_with_error(msg: str):
    """Xato bo'lsa ham servis yiqilmasin, logda sabab ko'rinib tursin."""
    while True:
        logging.error(msg)
        time.sleep(30)


if not BOT_TOKEN or ":" not in BOT_TOKEN:
    stop_with_error("BOT_TOKEN topilmadi yoki noto'g'ri! Render Environment'da BOT_TOKEN ni tekshiring.")

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
GROQ_MODEL = "llama-3.1-8b-instant"

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
    ref_ok = ensure_user(uid, m.from_user.full_name, ref)
    if not existed and ref_ok:
        run("UPDATE users SET balance=balance+?, ref_count=ref_count+1, ref_earned=ref_earned+? WHERE id=?", (REF_BONUS, REF_BONUS, ref_ok))
        try:
            await bot.send_message(ref_ok, f"🎉 Do'stingiz qo'shildi! Hisobingizga <b>{fmt(REF_BONUS)} so'm</b> berildi.")
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
        "Botdan foydalanishda muammo yuzaga kelsa yoki savollaringiz bo'lsa, quyidagi tugma orqali admin bilan bog'lanishingiz mumkin:",
        reply_markup=kb,
    )


@dp.message(Command("join"))
async def join_cmd(m: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👥 Guruhga qo'shilish 🚀", url=GROUP_LINK)]])
    await m.answer("💬 Bizning rasmiy guruhimizga qo'shiling va boshqalar bilan muloqot qiling:", reply_markup=kb)


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
    await m.answer(
        "📄 <b>Qo'llanma</b>\n\n"
        "1️⃣ «💳 Hisobni to'ldirish» orqali balansni to'ldiring.\n"
        "2️⃣ «🛍 Buyurtma berish» da Stars, Gif yoki SMM xizmatini tanlang.\n"
        "3️⃣ Ma'lumotlarni kiriting, buyurtma qabul qilinadi.\n"
        "4️⃣ «🛒 Buyurtmalar» da holatini kuzating.\n\n"
        "Bekor qilish uchun /cancel yozing."
    )


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
    await m.answer(f"✅ Buyurtma #{oid} qabul qilindi! Tez orada bajariladi.")
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


# ---------------- Groq (Llama) AI ----------------
ai_hist = {}


@dp.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def chat_with_ai(message: Message):
    wait_msg = await message.answer("⏳ O'ylayapman...")
    if not GROQ_API_KEY:
        logging.error("GROQ kalit topilmadi (Render Environment'da yo'q)")
        return await wait_msg.edit_text("❌ AI sozlanmagan (GROQ kalit yo'q).", parse_mode=None)

    uid = message.from_user.id
    hist = ai_hist.setdefault(uid, [])
    hist.append({"role": "user", "content": message.text})
    del hist[:-8]
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": "Siz foydalanuvchilarga yordam beradigan aqlli va muloyim Telegram yordamchisiz. O'zbek tilida javob bering."},
                *hist,
            ],
        }
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            async with session.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers) as resp:
                res_json = await resp.json(content_type=None)
                if resp.status == 200 and "choices" in res_json:
                    answer = res_json["choices"][0]["message"]["content"][:4000]
                    hist.append({"role": "assistant", "content": answer})
                    del hist[:-8]
                    await wait_msg.edit_text(answer, parse_mode=None)
                else:
                    hist.pop()
                    err_msg = res_json.get("error", {}).get("message", "Noma'lum xatolik")
                    logging.error(f"Groq API error: {err_msg}")
                    await wait_msg.edit_text(f"❌ AI xatosi: {err_msg}", parse_mode=None)
    except Exception as e:
        if hist:
            hist.pop()
        logging.error(f"AI Connection Error: {e}")
        await wait_msg.edit_text("❌ Sun'iy intellekt bilan bog'lanishda xatolik yuz berdi.", parse_mode=None)


# ---------------- Ishga tushirish ----------------
async def main():
    me = await bot.get_me()
    print("AI Bot ishga tushdi: @" + me.username, flush=True)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
