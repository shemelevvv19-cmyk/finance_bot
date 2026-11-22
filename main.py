import asyncio
import os
import sqlite3
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web
from aiogram.types import BufferedInputFile

BOT_TOKEN = '9147667306:AAG4HlWeBUWlL2JzQtvIPaZgr3g0bBCpq2o'
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS money
                 (user_id INTEGER, month TEXT, amount REAL)''')
    conn.commit()
    conn.close()

def add_money(user_id, month, amount):
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    c.execute("INSERT INTO money VALUES (?, ?, ?)", (user_id, month, amount))
    conn.commit()
    conn.close()

def get_money(user_id):
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    c.execute("SELECT month, amount FROM money WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я твой финансовый помощник.\n\n"
                         "Чтобы добавить сумму, напиши:\n"
                         "`/add Январь 50000` (где 50000 - это доход, или -20000 - это расход)\n\n"
                         "Чтобы посмотреть график, напиши: `/chart`")

@dp.message(Command("add"))
async def cmd_add(message: types.Message):
    args = message.text.split()
    if len(args) != 3:
        await message.answer("Ошибка! Пиши так: /add Месяц Сумма\nНапример: /add Январь 5000")
        return
    month = args[1]
    try:
        amount = float(args[2])
    except ValueError:
        await message.answer("Сумма должна быть числом. Например: 5000 или -2000")
        return
    
    add_money(message.from_user.id, month, amount)
    await message.answer(f"✅ Сохранено: {month} — {amount}")

@dp.message(Command("chart"))
async def cmd_chart(message: types.Message):
    data = get_money(message.from_user.id)
    if not data:
        await message.answer("У тебя пока нет данных. Добавь их через /add")
        return

    months = [row[0] for row in data]
    amounts = [row[1] for row in data]

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ['#2ecc71' if v >= 0 else '#e74c3c' for v in amounts]
    bars = ax.bar(months, amounts, color=colors, edgecolor='black')
    
    ax.spines['left'].set_position(('data', 0))
    ax.spines['bottom'].set_position(('data', 0))
    ax.spines['right'].set_color('none')
    ax.spines['top'].set_color('none')
    
    ax.axhline(0, color='black', linewidth=1.2)
    ax.set_title("Финансовый график (0 в центре)")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    photo = BufferedInputFile(buf.read(), filename="chart.png")
    await message.answer_photo(photo=photo, caption="Твой финансовый график")

async def handle(request):
    return web.Response(text="Bot is alive!")

async def main():
    init_db()
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
