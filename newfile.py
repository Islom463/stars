"""
Telegram Stars sotish boti (aiogram 3.x) - Ko'p kanalli obuna versiyasi
"""
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import urllib.request
import time

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

# Serverni alohida oqimda ishga tushiramiz
threading.Thread(target=run_server, daemon=True).start()

# O'zini o'zi ping qilish (Render uxlab qolmasligi uchun)
def self_ping():
    while True:
        time.sleep(300) # Har 5 daqiqada
        try:
            app_url = os.environ.get("RENDER_EXTERNAL_URL")
            if app_url:
                urllib.request.urlopen(app_url)
        except Exception:
            pass

threading.Thread(target=self_ping, daemon=True).start()

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

# ===================== SOZLAMALAR =====================
BOT_TOKEN = "9278626308:AAGIVO-g2F6cz2OnQX4vaWx6jGeDkwO8O44"  # Tokeningiz
ADMIN_IDS = [8099636943]  # Admin Telegram ID(lar)i
ADMIN_USERNAME = "@wezzcs"  # "Yordam" bo'limida ko'rinadi
CARD_NUMBER = "5614681853951071"  # Sizning karta raqamingiz
CARD_OWNER = "Panjiyev Muhammadali"  # Karta egasi
PRICE_PER_STAR = 215  # 1 ta ⭐ narxi (so'm)
REF_BONUS = 50  # Har bir taklif qilingan do'st uchun (so'm)
TOPUP_TIMEOUT = 5 * 60  # To'lovni tasdiqlash vaqti (soniya)
MIN_TOPUP = 1000
MAX_TOPUP = 5_000_000
MIN_STARS = 50
MAX_STARS = 10_000
PACKAGES = [50, 100, 250, 300, 350, 500, 750, 1000, 1500, 2500]

# --- MAJBURIY OBUNA UCHUN KANALLAR (IKKALA KANAL QO'SHILDI) ---
CHANNELS = ["@panjiyev_24", "@apex_server_b0t"]
# =======================================================

logging.basicConfig(level=logging.INFO)

# --- BOT VA DISPATCHERNI E'LON QILISH ---
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ---------------------------- BAZA ----------------------------
db = sqlite3.connect("bot.db", check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript(
    """
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY, name TEXT, balance INTEGER DEFAULT 0,
    referrer INTEGER, ref_count INTEGER DEFAULT 0, ref_earned INTEGER DEFAULT 0,
    joined INTEGER);
CREATE TABLE IF NOT EXISTS topups(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER,
    status TEXT, created INTEGER, expires INTEGER);
CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, stars INTEGER,
    price INTEGER, target TEXT, status TEXT, created INTEGER);
"""
)
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


# --- OBUNANI TEKSHIRISH FUNKSIYASI ---
async def check_user_subscription(user_id: int, bot: Bot) -> bool:
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                return False
        except Exception:
            return False
    return True


# ---------------------------- HOLATLAR ----------------------------
class TopupS(StatesGroup):
    amount = State()


class OrderS(StatesGroup):
    manual = State()
    target = State()


# ---------------------------- TUGMALAR ----------------------------
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


def packages_kb():
    rows = [[InlineKeyboardButton(text="✍️ Qo'lda hisoblash", callback_data="buy:manual")]]
    row = []
    for s in PACKAGES:
        row.append(
            InlineKeyboardButton(
                text=f"{s} ⭐️ ({fmt(s * PRICE_PER_STAR)} so'm)",
                callback_data=f"buy:{s}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_link(u) -> str:
    return f'<a href="tg://user?id={u.id}">{u.full_name}</a> (<code>{u.id}</code>)'


# ---------------------------- START VA OBUNA ----------------------------
@dp.message(CommandStart())
async def start(m: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    
    # Majburiy obunani tekshirish (barcha kanallar uchun)
    is_subscribed = await check_user_subscription(uid, bot)
    if not is_subscribed:
        keyboard_buttons = []
        for ch in CHANNELS:
            clean_ch = ch.lstrip('@')
            keyboard_buttons.append([InlineKeyboardButton(text=f"📢 {ch} kanaliga obuna bo'lish", url=f"https://t.me/{clean_ch}")])
        
        keyboard_buttons.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        return await m.answer(
            "⚠️ Botdan foydalanish uchun quyidagi barcha kanallarimizga obuna bo'ling:",
            reply_markup=keyboard
        )

    if not one("SELECT 1 FROM users WHERE id=?", (uid,)):
        ref = int(command.args) if command.args and command.args.isdigit() else None
        if ref == uid or (ref and not one("SELECT 1 FROM users WHERE id=?", (ref,))):
            ref = None
        run(
            "INSERT INTO users(id,name,referrer,joined) VALUES(?,?,?,?)",
            (uid, m.from_user.full_name, ref, int(time.time())),
        )
        if ref:
            run(
                "UPDATE users SET balance=balance+?, ref_count=ref_count+1, "
                "ref_earned=ref_earned+? WHERE id=?",
                (REF_BONUS, REF_BONUS, ref),
            )
            try:
                await bot.send_message(
                    ref,
                    f"🎉 Do'stingiz qo'shildi! Hisobingizga <b>{fmt(REF_BONUS)} so'm</b> berildi.",
                )
            except Exception:
                pass
    await m.answer(
        "👋 Xush kelibsiz! Telegram ⭐ Stars xarid qilish botiga xush kelibsiz.\n"
        "Kerakli bo'limni tanlang:",
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data == "check_sub")
async def process_check_sub(c: CallbackQuery):
    user_id = c.from_user.id
    is_subscribed = await check_user_subscription(user_id, bot)
    
    if is_subscribed:
        await c.message.edit_text("Rahmat! Obuna tasdiqlandi. Qaytadan /start buyrug'ini bosing.")
    else:
        await c.answer("Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)


# ---------------------------- MENYU ----------------------------
@dp.message(F.text == "🛍 Buyurtma berish")
async def order_menu(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(
        'Tanlang yoki "✍️ Qo\'lda hisoblash" tugmasini bosing:',
        reply_markup=packages_kb(),
    )


@dp.message(F.text == "🛒 Buyurtmalar")
async def my_orders(m: Message, state: FSMContext):
    await state.clear()
    rows = many(
        "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (m.from_user.id,)
    )
    if not rows:
        return await m.answer("Sizda hali buyurtmalar yo'q.")
    icons = {"pending": "⏳ Kutilmoqda", "done": "✅ Bajarildi", "cancelled": "❌ Bekor qilindi"}
    text = "🛒 <b>Oxirgi buyurtmalaringiz:</b>\n\n"
    for r in rows:
        text += (
            f"#{r['id']} — {r['stars']} ⭐ → {r['target']}\n"
            f"{fmt(r['price'])} so'm | {icons.get(r['status'], r['status'])}\n\n"
        )
    await m.answer(text)


@dp.message(F.text == "💵 Pul ishlash")
async def earn(m: Message, state: FSMContext):
    await state.clear()
    me = await bot.get_me()
    u = one("SELECT * FROM users WHERE id=?", (m.from_user.id,))
    ref_count = u['ref_count'] if u and 'ref_count' in u.keys() else 0
    ref_earned = u['ref_earned'] if u and 'ref_earned' in u.keys() else 0
    await m.answer(
        "💵 <b>Pul ishlash</b>\n\n"
        f"Do'stlaringizni taklif qiling va har biri uchun <b>{fmt(REF_BONUS)} so'm</b> oling!\n\n"
        f"🔗 Sizning havolangiz:\n<code>https://t.me/{me.username}?start={m.from_user.id}</code>\n\n"
        f"👥 Taklif qilinganlar: <b>{ref_count}</b> ta\n"
        f"💰 Ishlagan pulingiz: <b>{fmt(ref_earned)} so'm</b>"
    )


@dp.message(F.text == "💳 Hisobim")
async def account(m: Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    u = one("SELECT * FROM users WHERE id=?", (uid,))
    
    if not u:
        run(
            "INSERT INTO users(id,name,joined) VALUES(?,?,?)",
            (uid, m.from_user.full_name, int(time.time())),
        )
        u = one("SELECT * FROM users WHERE id=?", (uid,))

    balance = u['balance'] if 'balance' in u.keys() else 0
    ref_count = u['ref_count'] if 'ref_count' in u.keys() else 0

    cnt_res = one("SELECT COUNT(*) c FROM orders WHERE user_id=? AND status='done'", (uid,))
    cnt = cnt_res["c"] if cnt_res else 0

    await m.answer(
        "💳 <b>Hisobim</b>\n\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"💰 Balans: <b>{fmt(balance)} so'm</b>\n"
        f"🛒 Bajarilgan buyurtmalar: <b>{cnt}</b>\n"
        f"👥 Takliflar: <b>{ref_count}</b>"
    )


@dp.message(F.text == "☎️ Yordam")
async def help_(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(f"☎️ Savol va muammolar bo'yicha admin: {ADMIN_USERNAME}")


@dp.message(F.text == "📄 Qo'llanma")
async def guide(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(
        "📄 <b>Qo'llanma</b>\n\n"
        "1️⃣ «💳 Hisobni to'ldirish» orqali balansni to'ldiring.\n"
        "2️⃣ «🛍 Buyurtma berish» da ⭐ miqdorini tanlang.\n"
        "3️⃣ ⭐ yuboriladigan @username ni kiriting.\n"
        "4️⃣ Admin buyurtmani bajaradi va sizga xabar keladi.\n\n"
        f"💵 Do'st taklif qilib har biri uchun {fmt(REF_BONUS)} so'm ishlang."
    )


# ---------------------------- HISOBNI TO'LDIRISH ----------------------------
@dp.message(F.text == "💳 Hisobni to'ldirish")
async def topup_start(m: Message, state: FSMContext):
    await state.set_state(TopupS.amount)
    await m.answer(
        f"💳 Qancha so'm kiritmoqchisiz?\n"
        f"Minimal: {fmt(MIN_TOPUP)} so'm, maksimal: {fmt(MAX_TOPUP)} so'm.\n\n"
        "Summani raqam bilan yozing:"
    )


@dp.message(TopupS.amount, F.text)
async def topup_amount(m: Message, state: FSMContext):
    digits = re.sub(r"\D", "", m.text)
    if not digits or not (MIN_TOPUP <= int(digits) <= MAX_TOPUP):
        return await m.answer(f"❗ {fmt(MIN_TOPUP)} dan {fmt(MAX_TOPUP)} gacha summa kiriting.")
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
        "💳 <b>To'lov ma'lumotlari</b>\n\n"
        f"Karta: <code>{CARD_NUMBER}</code>\n"
        f"Egasi: <b>{CARD_OWNER}</b>\n"
        f"Summa: <b>{fmt(amount)} so'm</b>\n\n"
        f"⏰ To'lovni qilib, <b>{TOPUP_TIMEOUT // 60} daqiqa</b> ichida "
        "«✅ To'lov qildim» tugmasini bosing.",
        reply_markup=kb.as_markup(),
    )
    asyncio.create_task(expire_later(tid, msg.chat.id, msg.message_id))


async def expire_later(tid: int, chat_id: int, msg_id: int):
    await asyncio.sleep(TOPUP_TIMEOUT + 2)
    row = one("SELECT status FROM topups WHERE id=?", (tid,))
    if row and row["status"] == "new":
        run("UPDATE topups SET status='expired' WHERE id=?", (tid,))
        try:
            await bot.edit_message_text(
                "⌛️ Vaqt tugadi. So'rov bekor qilindi.\nQaytadan «💳 Hisobni to'ldirish» ni bosing.",
                chat_id=chat_id,
                message_id=msg_id,
            )
        except Exception:
            pass


@dp.callback_query(F.data.startswith("tcancel:"))
async def topup_cancel(c: CallbackQuery):
    tid = int(c.data.split(":")[1])
    t = one("SELECT * FROM topups WHERE id=?", (tid,))
    if t and t["user_id"] == c.from_user.id and t["status"] == "new":
        run("UPDATE topups SET status='cancelled' WHERE id=?", (tid,))
        await c.message.edit_text("❌ So'rov bekor qilindi.")
    await c.answer()


@dp.callback_query(F.data.startswith("paid:"))
async def topup_paid(c: CallbackQuery):
    tid = int(c.data.split(":")[1])
    t = one("SELECT * FROM topups WHERE id=?", (tid,))
    if not t or t["user_id"] != c.from_user.id:
        return await c.answer()
    if t["status"] != "new" or time.time() > t["expires"]:
        if t["status"] == "new":
            run("UPDATE topups SET status='expired' WHERE id=?", (tid,))
        await c.message.edit_text("⌛️ Vaqt tugadi. Qaytadan «💳 Hisobni to'ldirish» ni bosing.")
        return await c.answer()
    run("UPDATE topups SET status='checking' WHERE id=?", (tid,))
    await c.message.edit_text(
        f"⏳ <b>{fmt(t['amount'])} so'm</b> to'lovi admin tomonidan tekshirilmoqda.\n"
        "Tasdiqlangach hisobingiz to'ldiriladi."
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash", callback_data=f"tok:{tid}")
    kb.button(text="❌ Rad etish", callback_data=f"tno:{tid}")
    for a in ADMIN_IDS:
        try:
            await bot.send_message(
                a,
                "💰 <b>Yangi to'lov so'rovi</b>\n\n"
                f"Foydalanuvchi: {user_link(c.from_user)}\n"
                f"Summa: <b>{fmt(t['amount'])} so'm</b>\n"
                f"So'rov: #{tid}\n\n"
                "Pul kartaga tushganini tekshirib, tasdiqlang.",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            logging.exception("Adminga yuborib bo'lmadi")
    await c.answer()


@dp.callback_query(F.data.startswith(("tok:", "tno:")))
async def topup_admin(c: CallbackQuery):
    if c.from_user.id not in ADMIN_IDS:
        return await c.answer("Ruxsat yo'q", show_alert=True)
    action, tid = c.data.split(":")
    t = one("SELECT * FROM topups WHERE id=?", (int(tid),))
    if not t or t["status"] != "checking":
        return await c.answer("Bu so'rov allaqachon ko'rib chiqilgan.", show_alert=True)
    if action == "tok":
        run("UPDATE topups SET status='approved' WHERE id=?", (t["id"],))
        run("UPDATE users SET balance=balance+? WHERE id=?", (t["amount"], t["user_id"]))
        await c.message.edit_text(c.message.html_text + "\n\n✅ <b>Tasdiqlandi</b>")
        await bot.send_message(
            t["user_id"],
            f"✅ Hisobingiz <b>{fmt(t['amount'])} so'm</b>ga to'ldirildi!",
        )
    else:
        run("UPDATE topups SET status='rejected' WHERE id=?", (t["id"],))
        await c.message.edit_text(c.message.html_text + "\n\n❌ <b>Rad etildi</b>")
        await bot.send_message(
            t["user_id"],
            f"❌ {fmt(t['amount'])} so'mlik to'lovingiz tasdiqlanmadi. "
            f"Muammo bo'lsa {ADMIN_USERNAME} ga yozing.",
        )
    await c.answer()


# ---------------------------- BUYURTMA ----------------------------
@dp.callback_query(F.data == "back")
async def back(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.delete()
    await c.answer()


@dp.callback_query(F.data.startswith("buy:"))
async def buy(c: CallbackQuery, state: FSMContext):
    val = c.data.split(":")[1]
    if val == "manual":
        await state.set_state(OrderS.manual)
        await c.message.answer(
            f"✍️ Nechta ⭐ kerak? ({MIN_STARS} dan {fmt(MAX_STARS)} gacha raqam yozing)"
        )
        return await c.answer()
    await ask_target(c.message, state, c.from_user.id, int(val))
    await c.answer()


@dp.message(OrderS.manual, F.text)
async def manual(m: Message, state: FSMContext):
    digits = re.sub(r"\D", "", m.text)
    if not digits or not (MIN_STARS <= int(digits) <= MAX_STARS):
        return await m.answer(f"❗ {MIN_STARS} dan {fmt(MAX_STARS)} gacha son kiriting.")
    await ask_target(m, state, m.from_user.id, int(digits))


async def ask_target(msg: Message, state: FSMContext, uid: int, stars: int):
    price = stars * PRICE_PER_STAR
    u = one("SELECT balance FROM users WHERE id=?", (uid,))
    balance = u['balance'] if u and 'balance' in u.keys() else 0
    if balance < price:
        await state.clear()
        return await msg.answer(
            f"❗ Hisobingizda mablag' yetarli emas.\n"
            f"Kerak: <b>{fmt(price)} so'm</b>\nBalans: <b>{fmt(balance)} so'm</b>\n\n"
            "«💳 Hisobni to'ldirish» orqali balansni to'ldiring."
        )
    await state.set_state(OrderS.target)
    await state.update_data(stars=stars)
    await msg.answer(
        f"{stars} ⭐ — <b>{fmt(price)} so'm</b>\n\n"
        "⭐ yuboriladigan akkaunt <b>@username</b> ini yozing:"
    )


@dp.message(OrderS.target, F.text)
async def order_target(m: Message, state: FSMContext):
    target = m.text.strip()
    if not re.fullmatch(r"@?[A-Za-z0-9_]{5,32}", target):
        return await m.answer("❗ To'g'ri @username kiriting. Masalan: @username")
    target = "@" + target.lstrip("@")
    stars = (await state.get_data())["stars"]
    price = stars * PRICE_PER_STAR
    uid = m.from_user.id
    u = one("SELECT balance FROM users WHERE id=?", (uid,))
    await state.clear()
    balance = u['balance'] if u and 'balance' in u.keys() else 0
    if balance < price:
        return await m.answer("❗ Hisobingizda mablag' yetarli emas.")
    run("UPDATE users SET balance=balance-? WHERE id=?", (price, uid))
    oid = run(
        "INSERT INTO orders(user_id,stars,price,target,status,created) VALUES(?,?,?,?,?,?)",
        (uid, stars, price, target, "pending", int(time.time())),
    )
    await m.answer(
        f"✅ Buyurtma #{oid} qabul qilindi!\n"
        f"{stars} ⭐ → {target}\nSumma: <b>{fmt(price)} so'm</b>\n\n"
        "Admin tez orada bajaradi."
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Bajarildi", callback_data=f"ook:{oid}")
    kb.button(text="❌ Bekor qilish", callback_data=f"ono:{oid}")
    for a in ADMIN_IDS:
        try:
            await bot.send_message(
                a,
                f"🛍 <b>Yangi buyurtma #{oid}</b>\n\n"
                f"Foydalanuvchi: {user_link(m.from_user)}\n"
                f"⭐: <b>{stars}</b>\nQabul qiluvchi: {target}\n"
                f"Summa: {fmt(price)} so'm",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            logging.exception("Adminga yuborib bo'lmadi")


@dp.callback_query(F.data.startswith(("ook:", "ono:")))
async def order_admin(c: CallbackQuery):
    if c.from_user.id not in ADMIN_IDS:
        return await c.answer("Ruxsat yo'q", show_alert=True)
    action, oid = c.data.split(":")
    o = one("SELECT * FROM orders WHERE id=?", (int(oid),))
    if not o or o["status"] != "pending":
        return await c.answer("Bu buyurtma allaqachon ko'rib chiqilgan.", show_alert=True)
    if action == "ook":
        run("UPDATE orders SET status='done' WHERE id=?", (o["id"],))
        await c.message.edit_text(c.message.html_text + "\n\n✅ <b>Bajarildi</b>")
        await bot.send_message(
            o["user_id"], f"✅ Buyurtma #{o['id']} bajarildi! {o['stars']} ⭐ → {o['target']}"
        )
    else:
        run("UPDATE orders SET status='cancelled' WHERE id=?", (o["id"],))
        run("UPDATE users SET balance=balance+? WHERE id=?", (o["price"], o["user_id"]))
        await c.message.edit_text(c.message.html_text + "\n\n❌ <b>Bekor qilindi (pul qaytarildi)</b>")
        await bot.send_message(
            o["user_id"],
            f"❌ Buyurtma #{o['id']} bekor qilindi. {fmt(o['price'])} so'm hisobingizga qaytarildi.",
        )
    await c.answer()


# ---------------------------- ADMIN BUYRUQLARI ----------------------------
@dp.message(Command("stats"), F.from_user.id.in_(ADMIN_IDS))
async def stats(m: Message):
    users = one("SELECT COUNT(*) c FROM users")["c"]
    done = one("SELECT COUNT(*) c, COALESCE(SUM(price),0) s FROM orders WHERE status='done'")
    pend = one("SELECT COUNT(*) c FROM orders WHERE status='pending'")["c"]
    await m.answer(
        f"📊 Foydalanuvchilar: {users}\n"
        f"✅ Bajarilgan buyurtmalar: {done['c']} ({fmt(done['s'])} so'm)\n"
        f"⏳ Kutilayotgan: {pend}"
    )


@dp.message(Command("add"), F.from_user.id.in_(ADMIN_IDS))
async def add_balance(m: Message, command: CommandObject):
    try:
        uid, amount = command.args.split()
        run("UPDATE users SET balance=balance+? WHERE id=?", (int(amount), int(uid)))
        await m.answer("✅ Bajarildi.")
    except Exception:
        await m.answer("Foydalanish: /add USER_ID SUMMA")


@dp.message(Command("broadcast"), F.from_user.id.in_(ADMIN_IDS))
async def broadcast(m: Message, command: CommandObject):
    if not command.args:
        return await m.answer("Foydalanish: /broadcast matn")
    ok = 0
    for r in many("SELECT id FROM users"):
        try:
            await bot.send_message(r["id"], command.args)
            ok += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await m.answer(f"📢 {ok} ta foydalanuvchiga yuborildi.")


async def main():
    me = await bot.get_me()
    print("BOT ISHLADI: @" + me.username)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
