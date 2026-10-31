"""
Telegram Stars, Gif va Avtomatik SMM Nakrutka boti (aiogram 3.x)
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
ADMIN_USERNAME = "@wezzcs"
CARD_NUMBER = "5614681853951071"
CARD_OWNER = "Panjiyev Muhammadali"
REF_BONUS = 50
TOPUP_TIMEOUT = 5 * 60
MIN_TOPUP = 1000
MAX_TOPUP = 5_000_000

# UzSMM Panel API Sozlamalari
SMM_API_URL = "https://uzsmmpanel.pp.ua/api/v2"
SMM_API_KEY = "4abab7a5f4119fb078df3f971e6bb765"

# SMM Xizmatlari va Service ID lari (Saytdagi ID larga moslangan)
SMM_SERVICES = {
    "smm_ig_likes": {"name": "❤️ IG Layk (Kamayishlar 0%)", "price_per_1000": 3000, "min": 10, "service_id": 4217},
    "smm_ig_views": {"name": "🎬 IG Reels ko'rish", "price_per_1000": 200, "min": 100, "service_id": 4}, # O'zingizga mos ID bilan o'zgartirishingiz mumkin
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

async def check_user_subscription(user_id: int, bot: Bot) -> bool:
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                return False
        except Exception:
            return False
    return True

class TopupS(StatesGroup):
    amount = State()

class OrderS(StatesGroup):
    manual = State()
    target = State()

class SmmOrderS(StatesGroup):
    target = State()
    quantity = State()

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
    rows = []
    row = []
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
    rows = []
    for key, info in SMM_SERVICES.items():
        rows.append([InlineKeyboardButton(text=info["name"], callback_data=f"smm_svc:{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="order_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def user_link(u) -> str:
    return f'<a href="tg://user?id={u.id}">{u.full_name}</a> (<code>{u.id}</code>)'

@dp.message(CommandStart())
async def start(m: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    
    if not await check_user_subscription(uid, bot):
        kb_buttons = [[InlineKeyboardButton(text=f"📢 {ch} kanaliga obuna bo'lish", url=f"https://t.me/{ch.lstrip('@')}")] for ch in CHANNELS]
        kb_buttons.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")])
        return await m.answer("⚠️ Botdan foydalanish uchun kanallarga obuna bo'ling:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons))

    if not one("SELECT 1 FROM users WHERE id=?", (uid,)):
        ref = int(command.args) if command.args and command.args.isdigit() else None
        if ref == uid or (ref and not one("SELECT 1 FROM users WHERE id=?", (ref,))):
            ref = None
        run("INSERT INTO users(id,name,balance,referrer,joined) VALUES(?,?,?,?,?)", (uid, m.from_user.full_name, 0, ref, int(time.time())))
        if ref:
            run("UPDATE users SET balance=balance+?, ref_count=ref_count+1, ref_earned=ref_earned+? WHERE id=?", (REF_BONUS, REF_BONUS, ref))
            try:
                await bot.send_message(ref, f"🎉 Do'stingiz qo'shildi! Hisobingizga <b>{fmt(REF_BONUS)} so'm</b> berildi.")
            except Exception:
                pass
    await m.answer("👋 Xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=main_menu())

@dp.callback_query(F.data == "check_sub")
async def process_check_sub(c: CallbackQuery):
    if await check_user_subscription(c.from_user.id, bot):
        await c.message.edit_text("Rahmat! Obuna tasdiqlandi. Qaytadan /start buyrug'ini bosing.")
    else:
        await c.answer("Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)

@dp.message(F.text == "🛍 Buyurtma berish")
async def order_menu(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("🎁 Nima sotib olmoqchisiz? Quyidagilardan birini tanlang:", reply_markup=order_type_kb())

@dp.callback_query(F.data == "order_back")
async def order_back_cb(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text("🎁 Nima sotib olmoqchisiz? Quyidagilardan birini tanlang:", reply_markup=order_type_kb())
    await c.answer()

@dp.callback_query(F.data == "order:stars")
async def order_stars_cb(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text('Stars miqdorini tanlang:', reply_markup=stars_packages_kb())
    await c.answer()

@dp.callback_query(F.data == "order:gifs")
async def order_gifs_cb(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("🎁 Kerakli gifni tanlang:", reply_markup=gifs_packages_kb())
    await c.answer()

@dp.callback_query(F.data == "order:smm")
async def order_smm_cb(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("🚀 SMM xizmatini tanlang:", reply_markup=smm_services_kb())
    await c.answer()

@dp.message(F.text == "🛒 Buyurtmalar")
async def my_orders(m: Message, state: FSMContext):
    await state.clear()
    rows = many("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (m.from_user.id,))
    if not rows:
        return await m.answer("Sizda hali buyurtmalar yo'q.")
    icons = {"pending": "⏳ Kutilmoqda", "processing": "🚀 Bajarilmoqda", "done": "✅ Bajarildi", "cancelled": "❌ Bekor qilindi"}
    text = "🛒 <b>Oxirgi buyurtmalaringiz:</b>\n\n"
    for r in rows:
        text += f"#{r['id']} — {r['item_name']} → {r['target']}\n{fmt(r['price'])} so'm | {icons.get(r['status'], r['status'])}\n\n"
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
        f"🔗 Havolangiz:\n<code>https://t.me/{me.username}?start={m.from_user.id}</code>\n\n"
        f"👥 Takliflar: <b>{ref_count}</b> ta\n💰 Ishlaganingiz: <b>{fmt(ref_earned)} so'm</b>"
    )

@dp.message(F.text == "💳 Hisobim")
async def account(m: Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    u = one("SELECT * FROM users WHERE id=?", (uid,))
    if not u:
        run("INSERT INTO users(id,name,balance,joined) VALUES(?,?,?,?)", (uid, m.from_user.full_name, 0, int(time.time())))
        u = one("SELECT * FROM users WHERE id=?", (uid,))
    balance = u['balance'] if u and 'balance' in u.keys() else 0
    cnt_res = one("SELECT COUNT(*) c FROM orders WHERE user_id=? AND status='done'", (uid,))
    cnt = cnt_res["c"] if cnt_res else 0
    await m.answer(f"💳 <b>Hisobim</b>\n\n🆔 ID: <code>{uid}</code>\n💰 Balans: <b>{fmt(balance)} so'm</b>\n🛒 Bajarilgan: {cnt}")

@dp.message(F.text == "☎️ Yordam")
async def help_(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(f"☎️ Admin: {ADMIN_USERNAME}")

@dp.message(F.text == "📄 Qo'llanma")
async def guide(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("📄 Botdan foydalanish uchun balansni to'ldiring va buyurtma bering.")

@dp.message(F.text == "💳 Hisobni to'ldirish")
async def topup_start(m: Message, state: FSMContext):
    await state.set_state(TopupS.amount)
    await m.answer(f"💳 Qancha so'm kiritmoqchisiz? ({fmt(MIN_TOPUP)} - {fmt(MAX_TOPUP)}):")

@dp.message(TopupS.amount, F.text)
async def topup_amount(m: Message, state: FSMContext):
    digits = re.sub(r"\D", "", m.text)
    if not digits or not (MIN_TOPUP <= int(digits) <= MAX_TOPUP):
        return await m.answer(f"❗ Xato summa.")
    amount = int(digits)
    await state.clear()
    now = int(time.time())
    tid = run("INSERT INTO topups(user_id,amount,status,created,expires) VALUES(?,?,?,?,?)", (m.from_user.id, amount, "new", now, now + TOPUP_TIMEOUT))
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ To'lov qildim", callback_data=f"paid:{tid}")
    kb.button(text="❌ Bekor qilish", callback_data=f"tcancel:{tid}")
    kb.adjust(1)
    msg = await m.answer(
        f"💳 <b>To'lov ma'lumotlari</b>\n\nKarta: <code>{CARD_NUMBER}</code>\nEgasi: <b>{CARD_OWNER}</b>\nSumma: <b>{fmt(amount)} so'm</b>",
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
    run("UPDATE topups SET status='cancelled' WHERE id=?", (tid,))
    await c.message.edit_text("❌ Bekor qilindi.")
    await c.answer()

@dp.callback_query(F.data.startswith("paid:"))
async def topup_paid(c: CallbackQuery):
    tid = int(c.data.split(":")[1])
    t = one("SELECT * FROM topups WHERE id=?", (tid,))
    if not t or t["user_id"] != c.from_user.id:
        return await c.answer()
    run("UPDATE topups SET status='checking' WHERE id=?", (tid,))
    await c.message.edit_text("⏳ Admin tekshirmoqda.")
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash", callback_data=f"tok:{tid}")
    kb.button(text="❌ Rad etish", callback_data=f"tno:{tid}")
    for a in ADMIN_IDS:
        await bot.send_message(a, f"💰 To'lov so'rovi #{tid}: {fmt(t['amount'])} so'm", reply_markup=kb.as_markup())
    await c.answer()

@dp.callback_query(F.data.startswith(("tok:", "tno:")))
async def topup_admin(c: CallbackQuery):
    if c.from_user.id not in ADMIN_IDS:
        return await c.answer("Ruxsat yo'q", show_alert=True)
    action, tid = c.data.split(":")
    t = one("SELECT * FROM topups WHERE id=?", (int(tid),))
    if action == "tok":
        run("UPDATE topups SET status='approved' WHERE id=?", (t["id"],))
        run("UPDATE users SET balance=balance+? WHERE id=?", (t["amount"], t["user_id"]))
        await c.message.edit_text("✅ Tasdiqlandi")
        await bot.send_message(t["user_id"], f"✅ Balansingiz {fmt(t['amount'])} so'mga to'ldirildi!")
    else:
        run("UPDATE topups SET status='rejected' WHERE id=?", (t["id"],))
        await c.message.edit_text("❌ Rad etildi")
        await bot.send_message(t["user_id"], "❌ To'lovingiz rad etildi.")
    await c.answer()

# --- STARS & GIF LOGIKASI ---
@dp.callback_query(F.data == "buy:manual")
async def buy_manual(c: CallbackQuery, state: FSMContext):
    await state.set_state(OrderS.manual)
    await c.message.answer(f"✍️ Nechta ⭐ kerak? ({MIN_STARS} - {MAX_STARS})")
    await c.answer()

@dp.callback_query(F.data.startswith("star:"))
async def buy_star_package(c: CallbackQuery, state: FSMContext):
    _, stars_str, price_str = c.data.split(":")
    await ask_target_for_item(c.message, state, c.from_user.id, "star", stars_str, int(price_str))
    await c.answer()

@dp.callback_query(F.data.startswith("gif:"))
async def buy_gif_package(c: CallbackQuery, state: FSMContext):
    _, g_icon, price_str = c.data.split(":")
    await ask_target_for_item(c.message, state, c.from_user.id, "gif", g_icon, int(price_str))
    await c.answer()

@dp.message(OrderS.manual, F.text)
async def manual_stars(m: Message, state: FSMContext):
    digits = re.sub(r"\D", "", m.text)
    if not digits or not (MIN_STARS <= int(digits) <= MAX_STARS):
        return await m.answer("❗ Xato miqdor.")
    stars = int(digits)
    await ask_target_for_item(m, state, m.from_user.id, "star", str(stars), stars * 215)

async def ask_target_for_item(msg: Message, state: FSMContext, uid: int, item_type: str, item_name: str, price: int):
    u = one("SELECT balance FROM users WHERE id=?", (uid,))
    balance = u['balance'] if u and 'balance' in u.keys() else 0
    if balance < price:
        await state.clear()
        return await msg.answer(f"❗ Balans yetarli emas. Kerak: {fmt(price)} so'm")
    await state.set_state(OrderS.target)
    await state.update_data(item_type=item_type, item_name=item_name, price=price)
    await msg.answer(f"📦 Narxi: <b>{fmt(price)} so'm</b>\n\nQabul qiluvchi <b>@username</b> ni kiriting:")

@dp.message(OrderS.target, F.text)
async def order_target(m: Message, state: FSMContext):
    target = m.text.strip()
    data = await state.get_data()
    price = data.get("price", 0)
    uid = m.from_user.id
    
    u = one("SELECT balance FROM users WHERE id=?", (uid,))
    await state.clear()
    if u['balance'] < price:
        return await m.answer("❗ Balans yetarli emas.")
    
    run("UPDATE users SET balance=balance-? WHERE id=?", (price, uid))
    oid = run("INSERT INTO orders(user_id,item_type,item_name,price,target,status,created) VALUES(?,?,?,?,?,?,?)",
              (uid, data['item_type'], data['item_name'], price, target, "pending", int(time.time())))
    await m.answer(f"✅ Buyurtma #{oid} qabul qilindi!")
    for a in ADMIN_IDS:
        await bot.send_message(a, f"🛍 Stars/Gif Buyurtma #{oid}\nKimga: {target}\nSumma: {fmt(price)} so'm")

# ===================== SMM PANEL API ORQALI AVTO-NAKRUTKA =====================
async def send_smm_order(service_id: int, link: str, quantity: int):
    payload = {
        'key': SMM_API_KEY,
        'action': 'add',
        'service': service_id,
        'link': link,
        'quantity': quantity
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(SMM_API_URL, data=payload) as resp:
                result = await resp.json(content_type=None)
                return result
        except Exception as e:
            logging.error(f"SMM API Error: {e}")
            return None

@dp.callback_query(F.data.startswith("smm_svc:"))
async def smm_service_selected(c: CallbackQuery, state: FSMContext):
    svc_key = c.data.replace("smm_svc:", "")
    svc_info = SMM_SERVICES.get(svc_key)
    await state.update_data(smm_key=svc_key, smm_name=svc_info["name"], price_1k=svc_info["price_per_1000"], min_qty=svc_info["min"], service_id=svc_info["service_id"])
    await state.set_state(SmmOrderS.target)
    await c.message.edit_text(f"🚀 <b>{svc_info['name']}</b>\n\n🔗 Havolani (link) yuboring:")
    await c.answer()

@dp.message(SmmOrderS.target, F.text)
async def smm_target_received(m: Message, state: FSMContext):
    await state.update_data(target=m.text.strip())
    await state.set_state(SmmOrderS.quantity)
    data = await state.get_data()
    await m.answer(f"🔢 Soni qancha bo'lsin? (Minimal: {data['min_qty']} ta)")

@dp.message(SmmOrderS.quantity, F.text)
async def smm_quantity_received(m: Message, state: FSMContext):
    if not m.text.isdigit():
        return await m.answer("❗ Faqat raqam kiriting!")
    qty = int(m.text)
    data = await state.get_data()
    
    if qty < data["min_qty"]:
        return await m.answer(f"❗ Minimal miqdor {data['min_qty']} tadan kam bo'lmasligi kerak.")
    
    total_price = int((qty / 1000) * data["price_1k"])
    uid = m.from_user.id
    u = one("SELECT balance FROM users WHERE id=?", (uid,))
    
    if u['balance'] < total_price:
        await state.clear()
        return await m.answer(f"❗ Balans yetarli emas. Kerak: {fmt(total_price)} so'm")
    
    # Balansdan yechamiz
    run("UPDATE users SET balance=balance-? WHERE id=?", (total_price, uid))
    
    # UzSMM Panel API ga so'rov yuboramiz
    api_res = await send_smm_order(data["service_id"], data["target"], qty)
    
    status = "processing"
    panel_text = "🚀 Avtomatik yuborildi"
    if not api_res or "order" not in api_res:
        panel_text = "⚠️ Panelga yuborishda xatolik (Admin tekshiradi)"
    
    oid = run("INSERT INTO orders(user_id,item_type,item_name,price,target,status,created) VALUES(?,?,?,?,?,?,?)",
              (uid, "smm", f"{data['smm_name']} ({qty} ta)", total_price, data["target"], status, int(time.time())))
    
    await state.clear()
    await m.answer(f"✅ <b>SMM Buyurtma #{oid} qabul qilindi!</b>\nHolati: {panel_text}\nSumma: {fmt(total_price)} so'm")

# --- ADMIN BUYRUQLARI ---
@dp.callback_query(F.data.startswith(("ook:", "ono:")))
async def order_admin(c: CallbackQuery):
    if c.from_user.id not in ADMIN_IDS:
        return await c.answer("Ruxsat yo'q", show_alert=True)
    action, oid = c.data.split(":")
    o = one("SELECT * FROM orders WHERE id=?", (int(oid),))
    if action == "ook":
        run("UPDATE orders SET status='done' WHERE id=?", (o["id"],))
        await c.message.edit_text("✅ Bajarildi")
        await bot.send_message(o["user_id"], f"✅ Buyurtma #{o['id']} bajarildi!")
    else:
        run("UPDATE orders SET status='cancelled' WHERE id=?", (o["id"],))
        run("UPDATE users SET balance=balance+? WHERE id=?", (o["price"], o["user_id"]))
        await c.message.edit_text("❌ Bekor qilindi (pul qaytarildi)")
        await bot.send_message(o["user_id"], f"❌ Buyurtma #{o['id']} bekor qilindi, pul qaytarildi.")
    await c.answer()

@dp.message(Command("stats"), F.from_user.id.in_(ADMIN_IDS))
async def stats(m: Message):
    users = one("SELECT COUNT(*) c FROM users")["c"]
    done = one("SELECT COUNT(*) c, COALESCE(SUM(price),0) s FROM orders WHERE status='done'")
    await m.answer(f"📊 Foydalanuvchilar: {users}\n✅ Bajarilgan: {done['c']} ({fmt(done['s'])} so'm)")

@dp.message(Command("add"), F.from_user.id.in_(ADMIN_IDS))
async def add_balance(m: Message, command: CommandObject):
    try:
        uid, amount = command.args.split()
        run("UPDATE users SET balance=balance+? WHERE id=?", (int(amount), int(uid)))
        await m.answer("✅ Balans qo'shildi.")
    except Exception:
        await m.answer("Foydalanish: /add USER_ID SUMMA")

async def main():
    me = await bot.get_me()
    print("BOT ISHLADI: @" + me.username)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
