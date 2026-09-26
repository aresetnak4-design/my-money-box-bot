import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"goal": 0, "saved": 0, "history": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main_text(data):
    goal = data["goal"]
    saved = data["saved"]
    remaining = max(goal - saved, 0)

    if goal > 0:
        progress = saved / goal * 100
    else:
        progress = 0

    return (
        "🌸 <b>Копилка</b>\n\n"
        f"💰 Накоплено: <b>{saved:,.0f} ₽</b>\n"
        f"🎯 Цель: <b>{goal:,.0f} ₽</b>\n"
        f"💸 Осталось: <b>{remaining:,.0f} ₽</b>\n"
        f"📊 Прогресс: <b>{progress:.1f}%</b>"
    ).replace(",", " ")

def keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Положить", callback_data="add"),
            InlineKeyboardButton("➖ Забрать", callback_data="remove")
        ],
        [
            InlineKeyboardButton("🎯 Цель", callback_data="goal")
        ]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    await update.message.reply_text(
        main_text(data),
        parse_mode="HTML",
        reply_markup=keyboard()
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data

    if action == "add":
        context.user_data["action"] = "add"
        await query.message.reply_text("💰 Напиши, сколько положить:")
    elif action == "remove":
        context.user_data["action"] = "remove"
        await query.message.reply_text("💸 Напиши, сколько забрать:")
    elif action == "goal":
        context.user_data["action"] = "goal"
        await query.message.reply_text("🎯 Напиши сумму цели:")

async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get("action")

    if not action:
        return

    try:
        amount = float(update.message.text.replace(" ", "").replace(",", "."))
    except ValueError:
        await update.message.reply_text("Напиши только сумму, например: 5000")
        return

    data = load_data()

    if amount <= 0:
        await update.message.reply_text("Сумма должна быть больше нуля.")
        return

    if action == "add":
        data["saved"] += amount
        data["history"].append({"type": "add", "amount": amount})

    elif action == "remove":
        data["saved"] -= amount
        data["saved"] = max(data["saved"], 0)
        data["history"].append({"type": "remove", "amount": amount})

    elif action == "goal":
        data["goal"] = amount

    save_data(data)
    context.user_data.clear()

    await update.message.reply_text(
        main_text(data),
        parse_mode="HTML",
        reply_markup=keyboard()
    )

def run():
    token = os.environ["BOT_TOKEN"]

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))

    app.run_polling()

if __name__ == "__main__":
    run()
