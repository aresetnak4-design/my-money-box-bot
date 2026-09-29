import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")

DATA_FILE = "savings.json"

DEFAULT_GOALS = {
    "trip": {"name": "✈️ Поездка", "target": 0, "saved": 0},
    "hair": {"name": "💇‍♀️ Волосы", "target": 0, "saved": 0},
    "apartment": {"name": "🏠 Квартира", "target": 0, "saved": 0},
    "reserve": {"name": "✨ НЗ", "target": 0, "saved": 0},
}


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


data = load_data()


def get_user(user_id):
    user_id = str(user_id)

    if user_id not in data:
        data[user_id] = {
            "goals": {
                key: value.copy()
                for key, value in DEFAULT_GOALS.items()
            }
        }
        save_data(data)

    return data[user_id]


def money(value):
    return f"{value:,.0f}".replace(",", " ") + " ₽"


def progress_bar(saved, target):
    if target <= 0:
        return "□□□□□□□□□□"

    percent = min(saved / target, 1)
    filled = int(percent * 10)
    return "■" * filled + "□" * (10 - filled)


def goal_text(goal):
    saved = goal["saved"]
    target = goal["target"]

    if target > 0:
        percent = min(saved / target * 100, 100)
        return (
            f"{goal['name']}\n"
            f"{money(saved)} / {money(target)}\n"
            f"{progress_bar(saved, target)} {percent:.0f}%"
        )

    return (
        f"{goal['name']}\n"
        f"{money(saved)} / цель не установлена"
    )


def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Добавить деньги", callback_data="add")
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data="stats")
        ],
        [
            InlineKeyboardButton("⚙️ Настроить цели", callback_data="settings")
        ],
        [
            InlineKeyboardButton("🔄 Перенести деньги", callback_data="transfer")
        ],
        [
            InlineKeyboardButton("➖ Снять деньги", callback_data="withdraw")
        ],
    ])


def goals_keyboard(prefix):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✈️ Поездка", callback_data=f"{prefix}:trip")
        ],
        [
            InlineKeyboardButton("💇‍♀️ Волосы", callback_data=f"{prefix}:hair")
        ],
        [
            InlineKeyboardButton("🏠 Квартира", callback_data=f"{prefix}:apartment")
        ],
        [
            InlineKeyboardButton("✨ НЗ", callback_data=f"{prefix}:reserve")
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="home")
        ],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)

    total = sum(
        goal["saved"]
        for goal in user["goals"].values()
    )

    text = (
        "🌸 <b>Копилка</b>\n\n"
        f"💰 Всего накоплено: <b>{money(total)}</b>\n\n"
        "Выбирай, что хочешь сделать:"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = get_user(update.effective_user.id)
    action = query.data

    if action == "home":
        total = sum(
            goal["saved"]
            for goal in user["goals"].values()
        )

        await query.edit_message_text(
            f"🌸 <b>Копилка</b>\n\n"
            f"💰 Всего накоплено: <b>{money(total)}</b>\n\n"
            "Выбирай, что хочешь сделать:",
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
        return

    if action == "add":
        context.user_data["mode"] = "add"
        await query.edit_message_text(
            "➕ <b>Добавляем деньги</b>\n\n"
            "Сначала выбери цель:",
            parse_mode="HTML",
            reply_markup=goals_keyboard("add")
        )
        return

    if action.startswith("add:"):
        goal_key = action.split(":")[1]
        context.user_data["goal"] = goal_key
        context.user_data["mode"] = "add_amount"

        goal = user["goals"][goal_key]

        await query.edit_message_text(
            f"{goal['name']}\n\n"
            "Напиши сумму, которую хочешь отложить:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="add")]
            ])
        )
        return

    if action == "stats":
        text = "📊 <b>Твои накопления</b>\n\n"

        for goal in user["goals"].values():
            text += goal_text(goal) + "\n\n"

        total_saved = sum(
            goal["saved"]
            for goal in user["goals"].values()
        )

        total_target = sum(
            goal["target"]
            for goal in user["goals"].values()
        )

        text += f"💰 <b>Всего:</b> {money(total_saved)}"

        if total_target > 0:
            text += f" из {money(total_target)}"

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="home")]
            ])
        )
        return

    if action == "settings":
        await query.edit_message_text(
            "⚙️ <b>Настройка целей</b>\n\n"
            "Выбери цель, для которой хочешь установить сумму:",
            parse_mode="HTML",
            reply_markup=goals_keyboard("set")
        )
        return

    if action.startswith("set:"):
        goal_key = action.split(":")[1]

        context.user_data["goal"] = goal_key
        context.user_data["mode"] = "set_target"

        goal = user["goals"][goal_key]

        await query.edit_message_text(
            f"{goal['name']}\n\n"
            f"Сейчас цель: {money(goal['target'])}\n\n"
            "Напиши новую сумму цели:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="settings")]
            ])
        )
        return

    if action == "withdraw":
        context.user_data["mode"] = "withdraw"

        await query.edit_message_text(
            "➖ <b>Снять деньги</b>\n\n"
            "Выбери, из какой цели снять:",
            parse_mode="HTML",
            reply_markup=goals_keyboard("withdraw")
        )
        return

    if action.startswith("withdraw:"):
        goal_key = action.split(":")[1]

        context.user_data["goal"] = goal_key
        context.user_data["mode"] = "withdraw_amount"

        goal = user["goals"][goal_key]

        await query.edit_message_text(
            f"{goal['name']}\n\n"
            f"Доступно: {money(goal['saved'])}\n\n"
            "Напиши сумму, которую хочешь снять:"
        )
        return

    if action == "transfer":
        context.user_data["mode"] = "transfer_from"

        await query.edit_message_text(
            "🔄 <b>Перенос денег</b>\n\n"
            "Сначала выбери, ОТКУДА переносим деньги:",
            parse_mode="HTML",
            reply_markup=goals_keyboard("from")
        )
        return

    if action.startswith("from:"):
        goal_key = action.split(":")[1]

        context.user_data["from_goal"] = goal_key
        context.user_data["mode"] = "transfer_to"

        await query.edit_message_text(
            "Теперь выбери, <b>КУДА</b> перенести деньги:",
            parse_mode="HTML",
            reply_markup=goals_keyboard("to")
        )
        return

    if action.startswith("to:"):
        goal_key = action.split(":")[1]

        from_goal = context.user_data.get("from_goal")

        if goal_key == from_goal:
            await query.edit_message_text(
                "😅 Нельзя перенести деньги сами в себя.\n\n"
                "Выбери другую цель:",
                reply_markup=goals_keyboard("to")
            )
            return

        context.user_data["to_goal"] = goal_key
        context.user_data["mode"] = "transfer_amount"

        source = user["goals"][from_goal]

        await query.edit_message_text(
            f"🔄 Перенос\n\n"
            f"Откуда: {source['name']}\n"
            f"Доступно: {money(source['saved'])}\n\n"
            "Напиши сумму:"
        )
        return


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    mode = context.user_data.get("mode")

    if not mode:
        await update.message.reply_text(
            "Выбери действие:",
            reply_markup=main_keyboard()
        )
        return

    try:
        amount = float(
            update.message.text.replace(" ", "").replace(",", ".")
        )

        if amount <= 0:
            raise ValueError

        amount = int(amount)

    except ValueError:
        await update.message.reply_text(
            "Напиши сумму числом, например: <b>30000</b>",
            parse_mode="HTML"
        )
        return

    if mode == "add_amount":
        goal_key = context.user_data["goal"]
        goal = user["goals"][goal_key]

        goal["saved"] += amount
        save_data(data)

        context.user_data.clear()

        await update.message.reply_text(
            f"✅ Добавил <b>{money(amount)}</b>\n\n"
            f"{goal_text(goal)}",
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
        return

    if mode == "withdraw_amount":
        goal_key = context.user_data["goal"]
        goal = user["goals"][goal_key]

        if amount > goal["saved"]:
            await update.message.reply_text(
                f"У этой цели только <b>{money(goal['saved'])}</b>.\n"
                "Столько снять нельзя 😌",
                parse_mode="HTML"
            )
            return

        goal["saved"] -= amount
        save_data(data)

        context.user_data.clear()

        await update.message.reply_text(
            f"➖ Снял <b>{money(amount)}</b>\n\n"
            f"{goal_text(goal)}",
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
        return

    if mode == "set_target":
        goal_key = context.user_data["goal"]
        goal = user["goals"][goal_key]

        goal["target"] = amount
        save_data(data)

        context.user_data.clear()

        await update.message.reply_text(
            f"⚙️ Цель обновлена!\n\n"
            f"{goal_text(goal)}",
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
        return

    if mode == "transfer_amount":
        from_goal_key = context.user_data["from_goal"]
        to_goal_key = context.user_data["to_goal"]

        from_goal = user["goals"][from_goal_key]
        to_goal = user["goals"][to_goal_key]

        if amount > from_goal["saved"]:
            await update.message.reply_text(
                f"У {from_goal['name']} только "
                f"<b>{money(from_goal['saved'])}</b>.",
                parse_mode="HTML"
            )
            return

        from_goal["saved"] -= amount
        to_goal["saved"] += amount

        save_data(data)

        context.user_data.clear()

        await update.message.reply_text(
            f"🔄 Перенёс <b>{money(amount)}</b>\n\n"
            f"Из: {from_goal['name']}\n"
            f"В: {to_goal['name']}",
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
        return


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error("Ошибка:", exc_info=context.error)


def main():
    if not TOKEN:
        raise RuntimeError(
            "Не найден BOT_TOKEN. Добавь токен бота в переменные окружения."
        )

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message)
    )

    application.add_error_handler(error_handler)

    print("Бот запущен!")

    application.run_polling()


if __name__ == "__main__":
    main()
