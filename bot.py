import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import (
    CallbackQuery, 
    InlineKeyboardButton as Btn,
    InlineKeyboardMarkup as Kb, 
    LabeledPrice, 
    Message, 
    PreCheckoutQuery
)

BOT_TOKEN = "8899590879:AAEgsVFt1Mpsn_QOf2fZvcdu3wrRQffzx_k"
ADMIN_ID = None

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

db = sqlite3.connect("shop.db", check_same_thread=False)
db.executescript("""
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, val TEXT);
CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, price INT, file_id TEXT);
CREATE TABLE IF NOT EXISTS purchases (user_id INT, item_id INT, charge_id TEXT);
""")

def get_admin_id():
    global ADMIN_ID
    if ADMIN_ID is not None:
        return ADMIN_ID
    row = db.execute("SELECT val FROM settings WHERE key='admin_id'").fetchone()
    if row:
        ADMIN_ID = int(row[0])
    return ADMIN_ID

@dp.message(Command("admin_start"))
async def setup_admin(m: Message):
    global ADMIN_ID
    current = get_admin_id()
    if current is None:
        ADMIN_ID = m.from_user.id
        db.execute("INSERT OR REPLACE INTO settings (key, val) VALUES ('admin_id', ?)", (str(ADMIN_ID),))
        db.commit()
        await m.answer(f"Ты назначен админом! Твой ID: {ADMIN_ID}")
    elif current == m.from_user.id:
        await m.answer("Ты уже администратор бота.")
    else:
        await m.answer("У бота уже есть администратор.")

@dp.message(F.photo)
async def add_item(m: Message):
    if m.from_user.id != get_admin_id():
        return
    caption = m.caption or ""
    if "|" not in caption:
        return await m.answer("Отправь фото с подписью вида:\nНазвание фото | 50")
    try:
        parts = caption.split("|")
        title = parts[0].strip()
        price = int(parts[1].strip())
        db.execute("INSERT INTO items (title, price, file_id) VALUES (?, ?, ?)",
                   (title, price, m.photo[-1].file_id))
        db.commit()
        await m.answer(f"Добавлено: {title} — {price} ⭐")
    except ValueError:
        await m.answer("Ошибка в цене. Укажи целое число после черты |")

@dp.message(CommandStart())
async def start(m: Message):
    items = db.execute("SELECT id, title, price, file_id FROM items").fetchall()
    if not items:
        await m.answer("Каталог пока пуст. Загляните позже!")
        return
    for i, title, price, fid in items:
        kb = Kb(inline_keyboard=[[Btn(text=f"Купить за {price} ⭐", callback_data=f"buy:{i}")]])
        await m.answer_photo(
            photo=fid, 
            caption=f"{title}\n{price} ⭐", 
            has_spoiler=True,
            protect_content=True, 
            reply_markup=kb
        )

@dp.callback_query(F.data.startswith("buy:"))
async def buy(c: CallbackQuery):
    item_id = int(c.data.split(":")[1])
    row = db.execute("SELECT title, price FROM items WHERE id=?", (item_id,)).fetchone()
    if not row:
        return await c.answer("Товар не найден", show_alert=True)
    title, price = row
    await bot.send_invoice(
        chat_id=c.from_user.id,
        title=title,
        description="Покупка фото в полном качестве",
        payload=f"photo:{item_id}",
        currency="XTR",
        prices=[LabeledPrice(label=title, amount=price)],
    )
    await c.answer()

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)

@dp.message(F.successful_payment)
async def paid(m: Message):
    p = m.successful_payment
    item_id = int(p.invoice_payload.replace("photo:", ""))
    db.execute("INSERT INTO purchases VALUES (?, ?, ?)",
               (m.from_user.id, item_id, p.telegram_payment_charge_id))
    db.commit()
    row = db.execute("SELECT title, file_id FROM items WHERE id=?", (item_id,)).fetchone()
    if row:
        await m.answer("Оплата прошла! Вот оригинал:")
        await m.answer_photo(row[1], caption=f"Оригинал: {row[0]}")

@dp.message(Command("refund"))
async def refund(m: Message, command: CommandObject):
    if m.from_user.id != get_admin_id():
        return
    if not command.args:
        return await m.answer("Использование: /refund <charge_id>")
    charge_id = command.args.strip()
    row = db.execute("SELECT user_id FROM purchases WHERE charge_id=?", (charge_id,)).fetchone()
    if not row:
        return await m.answer("Платёж не найден.")
    try:
        await bot.refund_star_payment(user_id=row[0], telegram_payment_charge_id=charge_id)
        await m.answer("Звёзды возвращены.")
    except Exception as e:
        await m.answer(f"Ошибка возврата: {e}")

@dp.message(Command("paysupport"))
async def paysupport(m: Message):
    await m.answer("По вопросам оплаты пишите владельцу бота.")

async def main():
    print("Бот успешно запущен и слушает команды...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())