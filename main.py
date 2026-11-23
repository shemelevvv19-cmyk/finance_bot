import asyncio
import os
import sqlite3
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import re
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiohttp import web
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

BOT_TOKEN = '9147667306:AAFP3McHJOBHGMScJg0WBcMvaqnhRk6hHXU'
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- База данных ---
def init_db():
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    # Добавили колонку currency для валюты
    c.execute('''CREATE TABLE IF NOT EXISTS money
                 (user_id INTEGER, date_time TEXT, amount REAL, currency TEXT)''')
    conn.commit()
    conn.close()

def add_money(user_id, date_time, amount, currency):
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    c.execute("SELECT amount FROM money WHERE user_id = ? AND date_time = ?", (user_id, date_time))
    row = c.fetchone()
    if row:
        new_amount = row[0] + amount
        c.execute("UPDATE money SET amount = ? WHERE user_id = ? AND date_time = ?", (new_amount, user_id, date_time))
    else:
        c.execute("INSERT INTO money VALUES (?, ?, ?, ?)", (user_id, date_time, amount, currency))
    conn.commit()
    conn.close()

def get_money(user_id):
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    c.execute("SELECT date_time, amount, currency FROM money WHERE user_id = ? ORDER BY date_time", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def delete_record(user_id, date_time):
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    c.execute("DELETE FROM money WHERE user_id = ? AND date_time = ?", (user_id, date_time))
    conn.commit()
    conn.close()

# --- Меню ---
def get_main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Показать график", callback_data="show_chart")],
        [InlineKeyboardButton(text="🗑 Удалить запись", callback_data="delete_menu")]
    ])
    return keyboard

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я твой финансовый радар.\n\n"
        "Просто напиши мне дату и сумму, и я запишу это.\n\n"
        "📌 **Примеры ввода:**\n"
        "• `23.11.2026 5000` (рубли)\n"
        "• `23.11.2026 15:30 -2000` (минус = расход)\n"
        "• `23.11.2026 100 usd` (доллары)\n"
        "• `23.11.2026 50 eur` (евро)\n\n"
        "Я сам пойму, что ты написал, и добавлю в базу!",
        reply_markup=get_main_menu()
    )

# --- Обработка текста на лету (без команд) ---
@dp.message(F.text & ~F.text.startswith('/'))
async def process_free_text(message: types.Message):
    text = message.text.lower().strip()
    
    # Регулярное выражение для поиска даты (ДД.ММ.ГГГГ или ДД.ММ)
    date_match = re.search(r'(\d{1,2}\.\d{1,2}(?:\.\d{2,4})?)', text)
    # Поиск времени (ЧЧ:ММ) - необязательно
    time_match = re.search(r'(\d{1,2}:\d{2})', text)
    # Поиск суммы (число с возможным минусом)
    amount_match = re.search(r'(-?\d+(?:\.\d+)?)', text.replace(date_match.group(1) if date_match else "", "").replace(time_match.group(1) if time_match else "", ""))
    
    if not date_match or not amount_match:
        await message.answer("Не совсем понял. Пожалуйста, напиши дату и сумму (например: `23.11.2026 5000` или `23.11 -2000 usd`).")
        return

    date_str = date_match.group(1)
    time_str = time_match.group(1) if time_match else "00:00"
    amount = float(amount_match.group(1))
    
    # Определяем валюту
    currency = "RUB"
    if "usd" in text or "$" in text:
        currency = "USD"
    elif "eur" in text or "€" in text:
        currency = "EUR"

    # Если дата без года (например, 23.11), добавляем текущий год
    if len(date_str.split('.')) == 2:
        date_str = f"{date_str}.{datetime.now().year}"

    # Проверяем корректность даты
    try:
        datetime.strptime(date_str, "%d.%m.%Y")
        if time_match:
            datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await message.answer("Ошибка в дате. Пример: `23.11.2026` или `23.11`")
        return

    full_datetime = f"{date_str} {time_str}"
    add_money(message.from_user.id, full_datetime, amount, currency)
    
    # Форматируем ответ
    sign = "➕ Доход" if amount > 0 else "➖ Расход"
    currency_symbol = "₽" if currency == "RUB" else ("$" if currency == "USD" else "€")
    await message.answer(f"✅ {sign} сохранен: {full_datetime} — {abs(amount)} {currency_symbol}", reply_markup=get_main_menu())

# --- График ---
@dp.callback_query(F.data == "show_chart")
async def show_chart(callback: CallbackQuery):
    data = get_money(callback.from_user.id)
    if not data:
        await callback.message.answer("У тебя пока нет данных.")
        await callback.answer()
        return

    dates = [row[0] for row in data]
    amounts = [row[1] for row in data]
    # Валюты мы пока не выводим на график, чтобы не усложнять, просто рисуем суммы

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor('black')
    ax.set_facecolor('black')

    ax.spines['left'].set_position(('axes', 0))
    ax.spines['bottom'].set_position(('data', 0))
    ax.spines['right'].set_color('none')
    ax.spines['top'].set_color('none')
    ax.spines['left'].set_color('white')
    ax.spines['bottom'].set_color('white')

    for i in range(len(dates)):
        color = '#2ecc71' if amounts[i] >= 0 else '#e74c3c'
        ax.plot(i, amounts[i], marker='o', color=color, markersize=8, zorder=3)
        
        va = 'bottom' if amounts[i] >= 0 else 'top'
        offset = max(amounts) * 0.05 if amounts[i] >= 0 else min(amounts) * 0.05
        ax.text(i, amounts[i] + offset, f'{amounts[i]:.0f}', color=color, ha='center', va=va, fontsize=9, fontweight='bold')
        
        if i < len(dates) - 1:
            next_color = '#2ecc71' if amounts[i+1] >= 0 else '#e74c3c'
            ax.plot([i, i+1], [amounts[i], amounts[i+1]], color=next_color, linestyle='-', linewidth=2, zorder=2)

    ax.set_xticks(range(len(dates)))
    ax.set_xticklabels(dates, rotation=45, ha='right', color='white', fontsize=8)

    ax.set_title("Финансовый график (слева ноль, по датам)", color='white', pad=20)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='black')
    buf.seek(0)
    plt.close(fig)
    plt.style.use('default')

    photo = BufferedInputFile(buf.read(), filename="chart.png")
    await callback.message.answer_photo(photo=photo, caption="Твой график", reply_markup=get_main_menu())
    await callback.answer()

# --- Удаление ---
@dp.callback_query(F.data == "delete_menu")
async def delete_menu(callback: CallbackQuery):
    data = get_money(callback.from_user.id)
    if not data:
        await callback.message.answer("Нет данных для удаления.")
        await callback.answer()
        return

    keyboard = []
    for row in data:
        dt = row[0]
        keyboard.append([InlineKeyboardButton(text=f"❌ {dt}", callback_data=f"del_{dt}")])
    
    await callback.message.answer("Выбери запись для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()

@dp.callback_query(F.data.startswith("del_"))
async def process_delete(callback: CallbackQuery):
    dt = callback.data.split("_", 1)[1]
    delete_record(callback.from_user.id, dt)
    await callback.message.answer(f"🗑 Удалено: {dt}", reply_markup=get_main_menu())
    await callback.answer()

# --- Заглушка для Render ---
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
