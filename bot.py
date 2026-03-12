import asyncio
import aiosqlite
import logging
import time

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


BOT_TOKEN = "8712838824:AAFVOLx_yOox4FiWvGf2dQa6_YMaBQIgv3Y"
ADMIN_ID = 7235056179
CARD = "9112 3872 9876 1234"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

DB = "shop.db"


products = {
    "325 UC": 380,
    "660 UC": 790,
    "1800 UC": 1990,
    "3850 UC": 3825,
    "8100 UC": 7600,
    "12610 UC":12200,
}


cart = {}


last = {}
DELAY = 1


def anti_spam(user):
    now = time.time()
    if user in last and now - last[user] < DELAY:
        return False
    last[user] = now
    return True


async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            uc INTEGER,
            price INTEGER,
            status TEXT
        )
        """)
        await db.commit()



menu = ReplyKeyboardMarkup(resize_keyboard=True)
menu.add(KeyboardButton("🛒 Магазин"), KeyboardButton("📦 Мои заказы"))
menu.add(KeyboardButton("🎧 Поддержка"), KeyboardButton("🕒 График работы"))
menu.add(KeyboardButton("⭐ Отзывы"))



class Review(StatesGroup):
    waiting = State()


class Support(StatesGroup):
    waiting = State()



def shop_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    for p, price in products.items():
        kb.add(
            InlineKeyboardButton(
                f"{p} — {price}₽",
                callback_data=f"add_{p}"
            )
        )
    kb.add(InlineKeyboardButton("💳 Купить", callback_data="buy"))
    return kb



@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    user = msg.from_user.id
    if user not in cart:
        cart[user] = {"uc": 0, "money": 0}
    await msg.answer("Добро пожаловать в UC магазин", reply_markup=menu)



@dp.message_handler(lambda message: message.text == "🛒 Магазин")
async def shop(msg: types.Message):
    user = msg.from_user.id
    if user not in cart:
        cart[user] = {"uc": 0, "money": 0}
    text = (
        f"🛒 Магазин UC\n\n"
        f"Корзина:\nUC: {cart[user]['uc']}\n"
        f"Сумма: {cart[user]['money']}₽\n\n"
        "Выберите пакет:"
    )
    await msg.answer(text, reply_markup=shop_kb())



@dp.callback_query_handler(lambda c: c.data.startswith("add_"))
async def add_uc(call: types.CallbackQuery):
    user = call.from_user.id
    pack = call.data.replace("add_", "")
    uc = int(pack.split()[0])
    price = products[pack]
    if user not in cart:
        cart[user] = {"uc": 0, "money": 0}
    cart[user]["uc"] += uc
    cart[user]["money"] += price
    text = (
        f"🛒 Корзина\n\n"
        f"UC: {cart[user]['uc']}\n"
        f"Сумма: {cart[user]['money']}₽"
    )
    await call.message.edit_text(text, reply_markup=shop_kb())



@dp.callback_query_handler(lambda c: c.data == "buy")
async def buy(call: types.CallbackQuery):
    user = call.from_user.id
    if user not in cart or cart[user]["money"] == 0:
        await call.answer("Корзина пустая")
        return
    total = cart[user]["money"]
    await bot.send_message(
        user,
        f"💳 Оплатите {total}₽\n\nКарта:\n{CARD}\n\nПосле оплаты отправьте скрин."
    )



@dp.message_handler(content_types=["photo"])
async def payment(msg: types.Message):
    user = msg.from_user.id
    if user not in cart or cart[user]["money"] == 0:
        await msg.answer("Сначала сделайте заказ")
        return
    uc = cart[user]["uc"]
    money = cart[user]["money"]
    # Запись заказа в БД
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "INSERT INTO orders(user_id, uc, price, status) VALUES(?,?,?,?)",
            (user, uc, money, "waiting")
        )
        await db.commit()
        order_id = cursor.lastrowid
    # Отправка подтверждения
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"ok_{order_id}_{user}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"no_{order_id}_{user}")
    )
    await bot.send_photo(
        ADMIN_ID,
        msg.photo[-1].file_id,
        caption=f"Новый заказ\nUC: {uc}\nСумма: {money}",
        reply_markup=kb
    )
    await msg.answer("Заказ отправлен на проверку")
    # Очистка корзины
    cart[user] = {"uc": 0, "money": 0}



@dp.message_handler(lambda message: message.text == "🕒 График работы")
async def work(msg: types.Message):
    await msg.answer(
        "🕒 График работы\n\n"
        "Пн-Пт: 15:00 - 22:00\n"
        "Сб-Вс: 6:00 - 22:00"
    )



@dp.message_handler(lambda message: message.text == "⭐ Отзывы")
async def review_start(msg: types.Message):
    await msg.answer("Напишите ваш отзыв:")
    await Review.waiting.set()


@dp.message_handler(state=Review.waiting)
async def review_send(msg: types.Message, state: FSMContext):
    await bot.send_message(
        ADMIN_ID,
        f"Новый отзыв\n\n"
        f"{msg.from_user.full_name}\n"
        f"{msg.text}"
    )
    await msg.answer("Спасибо за отзыв!")
    await state.finish()



@dp.message_handler(lambda message: message.text == "🎧 Поддержка")
async def support_start(msg: types.Message):
    await msg.answer("Напишите сообщение в поддержку:")
    await Support.waiting.set()


@dp.message_handler(state=Support.waiting)
async def support_send(msg: types.Message, state: FSMContext):
    await bot.send_message(
        ADMIN_ID,
        f"Сообщение в поддержку\n\n"
        f"{msg.from_user.full_name}\n"
        f"{msg.text}"
    )
    await msg.answer("Сообщение отправлено поддержке")
    await state.finish()



@dp.message_handler(lambda message: message.text == "📦 Мои заказы")
async def orders(msg: types.Message):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT uc, price, status FROM orders WHERE user_id=?",
            (msg.from_user.id,)
        )
        rows = await cursor.fetchall()
    if not rows:
        await msg.answer("У вас пока нет заказов")
        return
    text = "Ваши заказы:\n\n"
    for uc, price, status in rows:
        text += f"{uc} UC - {price}₽ ({status})\n"
    await msg.answer(text)


@dp.callback_query_handler(lambda c: c.data.startswith("ok_"))
async def approve(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    data = call.data.split("_")
    order_id = int(data[1])
    user_id = int(data[2])
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE orders SET status='paid' WHERE id=?", (order_id,))
        await db.commit()
    await bot.send_message(user_id, "Платеж подтвержден")



@dp.callback_query_handler(lambda c: c.data.startswith("no_"))
async def reject(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    data = call.data.split("_")
    order_id = int(data[1])
    user_id = int(data[2])
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE orders SET status='rejected' WHERE id=?", (order_id,))
        await db.commit()
    await bot.send_message(user_id, "Заказ отклонен")


if __name__ == "__main__":
    loop.run_until_complete(init_db())
    executor.start_polling(dp)