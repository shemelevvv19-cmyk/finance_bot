import asyncio
import os
import sqlite3
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiohttp import web
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

BOT_TOKEN = '9147667306:AAG4HlWeBUWlL2JzQtvIPaZgr3g0bBCpq2o'
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- База данных ---
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

def delete_month(user_id, month):
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    c.execute("DELETE FROM money WHERE user_id = ? AND month = ?", (user_id, month))
    conn.commit()
    conn.close()

# --- Состояния для ввода ---
class AddMoney(StatesGroup):
    month = State()
    amount = State()

# --- Клавиатуры ---
def get_main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Показать график", callback_data="show_chart")],
        [InlineKeyboardButton(text="➕ Добавить доход", callback_data="add_income")],
        [InlineKeyboardButton(text="➖ Добавить расход", callback_data="add_expense")],
        [InlineKeyboardButton(text="🗑 Удалить запись", callback_data="delete_menu")]
    ])
    return keyboard

# --- Команды ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я твой финансовый радар.\n\n"
        "Я помогу тебе наглядно увидеть, как растут твои доходы и падают расходы.\n\n"
        "Выбери действие на кнопках ниже 👇",
        reply_markup=get_main_menu()
    )

# --- Обработка кнопок ---
@dp.callback_query(F.data == "show_chart")
async def show_chart(callback: CallbackQuery):
    data = get_money(callback.from_user.id)
    if not data:
        await callback.message.answer("У тебя пока нет данных. Добавь их через меню.")
        await callback.answer()
        return

    months = [row[0] for row in data]
    amounts = [row[1] for row in data]

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor('#1e1e1e')
    ax.set_facecolor('#1e1e1e')
    
    colors = ['#2ecc71' if v >= 0 else '#e74c3c' for v in amounts]
    bars = ax.bar(months, amounts, color=colors, edgecolor='white', linewidth=0.5)
    
    ax.spines['left'].set_position(('data', 0))
    ax.spines['bottom'].set_position(('data', 0))
    ax.spines['right'].set_color('none')
    ax.spines['top'].set_color('none')
    ax.spines['left'].set_color('white')
    ax.spines['bottom'].set_color('white')
    
    ax.axhline(0, color='white', linewidth=1.2)
    ax.set_title("Финансовый график (0 в центре)", color='white', pad=20)

    for bar, val in zip(bars, amounts):
        height = bar.get_height()
        va = 'bottom' if val >= 0 else 'top'
        offset = 1000 if val >= 0 else -1000
        ax.text(bar.get_x() + bar.get_width()/2., height + offset,
                f'{int(val)}', ha='center', va=va, color='white', fontsize=9)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#1e1e1e')
    buf.seek(0)
    plt.close(fig)
    plt.style.use('default')

    photo = BufferedInputFile(buf.read(), filename="chart.png")
    await callback.message.answer_photo(photo=photo, caption="Твой финансовый график", reply_markup=get_main_menu())
    await callback.answer()

@dp.callback_query(F.data == "add_income")
async def add_income_start(callback: CallbackQuery, state: FSMContext):
    await state.update_data(is_income=True)
    await callback.message.answer("Введи месяц и сумму через пробел (например: `Март 50000`):")
    await state.set_state(AddMoney.month)
    await callback.answer()

@dp.callback_query(F.data == "add_expense")
async def add_expense_start(callback: CallbackQuery, state: FSMContext):
    await state.update_data(is_income=False)
    await callback.message.answer("Введи месяц и сумму через пробел (например: `Март 15000`):")
    await state.set_state(AddMoney.month)
    await callback.answer()

@dp.message(AddMoney.month)
async def process_add(message: types.Message, state: FSMContext):
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Ошибка! Пиши так: `Март 50000`")
        return
    
    month = args[0]
    try:
        amount = float(args[1])
    except ValueError:
        await message.answer("Сумма должна быть числом!")
        return
    
    data = await state.get_data()
    if not data.get('is_income', False):
        amount = -amount

    add_money(message.from_user.id, month, amount)
    await message.answer(f"✅ Сохранено: {month} — {amount}", reply_markup=get_main_menu())
    await state.clear()

@dp.callback_query(F.data == "delete_menu")
async def delete_menu(callback: CallbackQuery):
    data = get_money(callback.from_user.id)
    if not data:
        await callback.message.answer("Нет данных для удаления.")
        await callback.answer()
        return

    keyboard = []
    for row in data:
        month = row[0]
        keyboard.append([InlineKeyboardButton(text=f"❌ {month}", callback_data=f"del_{month}")])
    
    await callback.message.answer("Выбери месяц для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()

@dp.callback_query(F.data.startswith("del_"))
async def process_delete(callback: CallbackQuery):
    month = callback.data.split("_")[1]
    delete_month(callback.from_user.id, month)
    await callback.message.answer(f"🗑 Удалено: {month}", reply_markup=get_main_menu())
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
