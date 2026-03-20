import asyncio
import os
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
import threading

# 🔥 FIX для Python 3.12+
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# ================= НАСТРОЙКИ =================
BOT_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден в переменных окружения!")

ADMIN_ID = 7235056179
MY_CARD = "9112 3872 98"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ================= БД =================
conn = sqlite3.connect("shop.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    uc INTEGER,
    price INTEGER,
    status TEXT
)
""")
conn.commit()

# ================= ДАННЫЕ =================
prices = {
    "60 UC": 78,
    "325 UC": 400,
    "660 UC": 790,
    "1800 UC": 2000,
    "3850 UC": 3900,
    "8100 UC": 7600,
    "16200 UC": 16000,
    "24300 UC": 24000,
    "32400 UC": 32000,
    "40500 UC": 40000,
}

cart = {}
user_states = {}
user_pubg_id = {}

# ================= МЕНЮ =================
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🛒 Купить UC"))
    kb.add(KeyboardButton("👤 Профиль"), KeyboardButton("📦 Мои заказы"))
    kb.add(KeyboardButton("⭐️ Отзывы"), KeyboardButton("🛠 Поддержка"))
    kb.add(KeyboardButton("🕒 График работы"))
    kb.add(KeyboardButton("📜 Правила"))
    return kb

def shop_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    for pack in prices:
        kb.add(InlineKeyboardButton(f"➕ {pack}", callback_data=f"add_{pack}"))
    kb.add(
        InlineKeyboardButton("💳 Купить", callback_data="buy"),
        InlineKeyboardButton("🗑 Очистить", callback_data="clear")
    )
    return kb

async def update_cart(call):
    user = call.from_user.id
    uc = cart[user]["uc"]
    money = cart[user]["money"]
    text = f"🛒 Корзина\n\nUC: {uc}\nСумма: {money}₽"
    await call.message.edit_text(text, reply_markup=shop_keyboard())

# ================= ХЕНДЛЕРЫ =================
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    cart[msg.from_user.id] = {"uc": 0, "money": 0}
    await msg.answer("👋 Добро пожаловать!", reply_markup=main_menu())

@dp.message_handler(lambda msg: msg.text == "🛒 Купить UC")
async def shop(msg: types.Message):
    user = msg.from_user.id
    cart.setdefault(user, {"uc": 0, "money": 0})
    await msg.answer("Выберите UC:", reply_markup=shop_keyboard())

@dp.callback_query_handler(lambda c: c.data.startswith("add_"))
async def add_uc(call: types.CallbackQuery):
    user = call.from_user.id
    pack = call.data.replace("add_", "")
    uc = int(pack.split()[0])
    price = prices[pack]
    cart.setdefault(user, {"uc": 0, "money": 0})
    cart[user]["uc"] += uc
    cart[user]["money"] += price
    await update_cart(call)
    await call.answer()

@dp.callback_query_handler(lambda c: c.data == "clear")
async def clear(call: types.CallbackQuery):
    cart[call.from_user.id] = {"uc": 0, "money": 0}
    await update_cart(call)
    await call.answer("Очищено")

@dp.callback_query_handler(lambda c: c.data == "buy")
async def buy(call: types.CallbackQuery):
    user = call.from_user.id
    total = cart[user]["money"]
    if total == 0:
        return await call.answer("Корзина пустая")
    await bot.send_message(
        user,
        f"💳 Оплатите {total}₽\n\nКарта:\n{MY_CARD}\n\nОтправьте скрин"
    )

@dp.message_handler(content_types=["photo"])
async def payment(msg: types.Message):
    user = msg.from_user.id
    uc = cart[user]["uc"]
    total = cart[user]["money"]
    cursor.execute(
        "INSERT INTO orders(user_id, uc, price, status) VALUES(?,?,?,?)",
        (user, uc, total, "pending")
    )
    conn.commit()
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Принять", callback_data=f"accept_{user}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_{user}")
    )
    await bot.send_photo(
        ADMIN_ID,
        msg.photo[-1].file_id,
        caption=f"Заказ\n{uc} UC\n{total}₽",
        reply_markup=kb
    )
    await msg.answer("✅ На проверке")

@dp.callback_query_handler(lambda c: c.data.startswith("accept_"))
async def accept(call: types.CallbackQuery):
    user = int(call.data.split("_")[1])
    await bot.send_message(user, "✅ Оплата подтверждена")

@dp.callback_query_handler(lambda c: c.data.startswith("decline_"))
async def decline(call: types.CallbackQuery):
    user = int(call.data.split("_")[1])
    await bot.send_message(user, "❌ Оплата отклонена")

# ================= HTTP СЕРВЕР ДЛЯ RENDER =================
async def handle(request):
    return web.Response(text="Bot is running!")

def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle)
    port = int(os.environ.get("PORT", 10000))
    web.run_app(app, host="0.0.0.0", port=port)

# ================= ЗАПУСК =================
if __name__ == "__main__":
    print("🚀 BOT STARTED")
    threading.Thread(target=start_webserver, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
