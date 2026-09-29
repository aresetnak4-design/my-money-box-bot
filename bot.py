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

logging.basicConfig(level=logging.INFO)

data = {}


# =========================
# Работа с данными
# =========================

def load_data():
    global data

    if not os.path.exists(DATA_FILE):
        data = {}
        return

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        data = {}


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def get_user(user_id):
    user_id = str(user_id)

    if user_id not in data:
        data[user_id] = {"goals": {}}
        save_data()

    # На случай старой версии
    if "goals" not in data[user_id]:
        data[user_id]["goals"] = {}

    return data[user_id]


def money(value):
    return f"{int(value):,}".replace(",", " ") + " ₽"


def progress_bar(saved, target):
    if target <= 0:
        return "□□□□□□□□□□"

    percent = min(saved / target, 1)
    filled = int(percent * 10)

    return "■" * filled + "□" * (10 - filled)


def goal_text(goal):
    saved = goal.get("saved", 0)
    target = goal.get("target", 0)
    name = goal.get("name", "Без названия")

    if target > 0:
        percent = min(saved / target * 100, 100)

        return (
            f"<b>{name}</b>\n"
            f"{money(saved)} / {money(target)}\n"
            f"{progress_bar(saved, target)} {percent:.0f}%"
        )

    return (
        f"<b>{name}</b>\n"
        f"{money(saved)} / цель не установлена"
    )


# =========================
# Клавиатуры
# =========================

def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ Добавить деньги",
                callback_data="add"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 Статистика",
                callback_data="stats"
            )
        ],
        [
            InlineKeyboardButton(
                "⚙️ Цели",
                callback_data="goals"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Перенести деньги",
                callback_data="transfer"
            )
        ],
        [
            InlineKeyboardButton(
                "➖ Снять деньги",
                callback_data="withdraw"
            )
        ],
    ])


def goal_buttons(prefix, goals):
    buttons = []

    for key, goal in goals.items():
        buttons.append([
            InlineKeyboardButton(
                goal["name"],
                callback_data=f"{prefix}:{key}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "◀️ Назад",
            callback_data="home"
        )
    ])

    return InlineKeyboardMarkup(buttons)


def settings_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ Добавить цель",
                callback_data="new_goal"
            )
        ],
        [
            InlineKeyboardButton(
                "✏️ Изменить цель",
                callback_data="edit_goal"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 Удалить цель",
                callback_data="delete_goal"
            )
        ],
        [
            InlineKeyboardButton(
                "◀️ Назад",
                callback_data="home"
            )
        ],
    ])


# =========================
# Главная
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)

    total = sum(
        goal.get("saved", 0)
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


# =========================
# Кнопки
# =========================

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = get_user(update.effective_user.id)
    goals = user["goals"]
    action = query.data

    # -------------------------
    # Главный экран
    # -------------------------

    if action == "home":
        total = sum(
            goal.get("saved", 0)
            for goal in goals.values()
        )

        await query.edit_message_text(
            "🌸 <b>Копилка</b>\n\n"
            f"💰 Всего накоплено: <b>{money(total)}</b>\n\n"
            "Выбирай, что хочешь сделать:",
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
        return

    # -------------------------
    # Добавить деньги
    # -------------------------

    if action == "add":
        if not goals:
            await query.edit_message_text(
                "У тебя пока нет целей.\n\n"
                "Сначала создай хотя бы одну цель ✨",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "➕ Создать цель",
                            callback_data="new_goal"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "◀️ Назад",
                            callback_data="home"
                        )
                    ]
                ])
            )
            return

        context.user_data["mode"] = "add_select"

        await query.edit_message_text(
            "➕ <b>Добавляем деньги</b>\n\n"
            "Выбери цель:",
            parse_mode="HTML",
            reply_markup=goal_buttons("add", goals)
        )
        return

    if action.startswith("add:"):
        goal_key = action.split(":", 1)[1]

        context.user_data["goal"] = goal_key
        context.user_data["mode"] = "add_amount"

        goal = goals[goal_key]

        await query.edit_message_text(
            f"➕ {goal['name']}\n\n"
            "Напиши сумму, которую хочешь отложить:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "◀️ Назад",
                        callback_data="add"
                    )
                ]
            ])
        )
        return

    # -------------------------
    # Статистика
    # -------------------------

    if action == "stats":
        if not goals:
            text = (
                "📊 <b>Статистика</b>\n\n"
                "Пока нет ни одной цели."
            )
        else:
            text = "📊 <b>Твои накопления</b>\n\n"

            for goal in goals.values():
                text += goal_text(goal) + "\n\n"

            total_saved = sum(
                goal.get("saved", 0)
                for goal in goals.values()
            )

            total_target = sum(
                goal.get("target", 0)
                for goal in goals.values()
            )

            text += f"💰 <b>Всего накоплено:</b> {money(total_saved)}\n"

            if total_target:
                text += f"🎯 <b>Всего целей:</b> {money(total_target)}"

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "◀️ Назад",
                        callback_data="home"
                    )
                ]
            ])
        )
        return

    # -------------------------
    # Цели
    # -------------------------

    if action == "goals":
        await query.edit_message_text(
            "⚙️ <b>Мои цели</b>\n\n"
            "Здесь ты можешь создавать, менять и удалять цели.",
            parse_mode="HTML",
            reply_markup=settings_keyboard()
        )
        return

    # -------------------------
    # Новая цель
    # -------------------------

    if action == "new_goal":
        context.user_data.clear()
        context.user_data["mode"] = "new_goal_name"

        await query.edit_message_text(
            "➕ <b>Новая цель</b>\n\n"
            "Как её назовём?\n\n"
            "Например: ✈️ Поездка, 🇵🇹 Португалия, 💻 MacBook"
        )
        return

    # -------------------------
    # Изменить цель
    # -------------------------

    if action == "edit_goal":
        if not goals:
            await query.edit_message_text(
                "У тебя пока нет целей.",
                reply_markup=settings_keyboard()
            )
            return

        await query.edit_message_text(
            "✏️ <b>Какую цель изменить?</b>",
            parse_mode="HTML",
            reply_markup=goal_buttons("edit", goals)
        )
        return

    if action.startswith("edit:"):
        goal_key = action.split(":", 1)[1]

        context.user_data["goal"] = goal_key
        context.user_data["mode"] = "edit_name"

        goal = goals[goal_key]

        await query.edit_message_text(
            f"✏️ Сейчас цель называется:\n"
            f"<b>{goal['name']}</b>\n\n"
            "Напиши новое название:",
            parse_mode="HTML"
        )
        return

    # -------------------------
    # Удалить цель
    # -------------------------

    if action == "delete_goal":
        if not goals:
            await query.edit_message_text(
                "У тебя пока нет целей.",
                reply_markup=settings_keyboard()
            )
            return

        await query.edit_message_text(
            "🗑 <b>Какую цель удалить?</b>",
            parse_mode="HTML",
            reply_markup=goal_buttons("delete", goals)
        )
        return

    if action.startswith("delete:"):
        goal_key = action.split(":", 1)[1]
        goal = goals[goal_key]

        context.user_data["delete_goal"] = goal_key

        await query.edit_message_text(
            f"🗑 Удалить цель <b>{goal['name']}</b>?\n\n"
            f"В ней сейчас: <b>{money(goal.get('saved', 0))}</b>\n\n"
            "Если удалить её, деньги тоже исчезнут из копилки.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "❌ Да, удалить",
                        callback_data="delete_confirm"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "◀️ Отмена",
                        callback_data="goals"
                    )
                ]
            ])
        )
        return

    if action == "delete_confirm":
        goal_key = context.user_data.get("delete_goal")

        if goal_key in goals:
            deleted_name = goals[goal_key]["name"]
            del goals[goal_key]
            save_data()

            context.user_data.clear()

            await query.edit_message_text(
                f"🗑 Цель <b>{deleted_name}</b> удалена.",
                parse_mode="HTML",
                reply_markup=settings_keyboard()
            )
        else:
            await query.edit_message_text(
                "Цель уже удалена.",
                reply_markup=settings_keyboard()
            )
        return

    # -------------------------
    # Снять деньги
    # -------------------------

    if action == "withdraw":
        if not goals:
            await query.edit_message_text(
                "У тебя пока нет целей.",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "◀️ Назад",
                            callback_data="home"
                        )
                    ]
                ])
            )
            return

        await query.edit_message_text(
            "➖ <b>Снять деньги</b>\n\n"
            "Из какой цели снять?",
            parse_mode="HTML",
            reply_markup=goal_buttons("withdraw", goals)
        )
        return

    if action.startswith("withdraw:"):
        goal_key = action.split(":", 1)[1]

        context.user_data["goal"] = goal_key
        context.user_data["mode"] = "withdraw_amount"

        goal = goals[goal_key]

        await query.edit_message_text(
            f"➖ {goal['name']}\n\n"
            f"Доступно: <b>{money(goal.get('saved', 0))}</b>\n\n"
            "Напиши сумму, которую хочешь снять:",
            parse_mode="HTML"
        )
        return

    # -------------------------
    # Перенос денег
    # -------------------------

    if action == "transfer":
        if len(goals) < 2:
            await query.edit_message_text(
                "Для переноса нужны хотя бы две цели.",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "◀️ Назад",
                            callback_data="home"
                        )
                    ]
                ])
            )
            return

        context.user_data.clear()
        context.user_data["mode"] = "transfer_from"

        await query.edit_message_text(
            "🔄 <b>Перенос денег</b>\n\n"
            "Откуда переносим?",
            parse_mode="HTML",
            reply_markup=goal_buttons("from", goals)
        )
        return

    if action.startswith("from:"):
        goal_key = action.split(":", 1)[1]

        context.user_data["from_goal"] = goal_key
        context.user_data["mode"] = "transfer_to"

        await query.edit_message_text(
            "🔄 <b>Куда переносим?</b>",
            parse_mode="HTML",
            reply_markup=goal_buttons("to", goals)
        )
        return

    if action.startswith("to:"):
        goal_key = action.split(":", 1)[1]
        from_goal = context.user_data.get("from_goal")

        if goal_key == from_goal:
            await query.edit_message_text(
                "😅 Нельзя перенести деньги сами в себя.\n\n"
                "Выбери другую цель:",
                reply_markup=goal_buttons("to", goals)
            )
            return

        context.user_data["to_goal"] = goal_key
        context.user_data["mode"] = "transfer_amount"

        source = goals[from_goal]

        await query.edit_message_text(
            f"🔄 <b>Перенос денег</b>\n\n"
            f"Откуда: {source['name']}\n"
            f"Доступно: {money(source.get('saved', 0))}\n\n"
            "Напиши сумму:",
            parse_mode="HTML"
        )
        return


# =========================
# Текстовые сообщения
# =========================

async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    goals = user["goals"]
    mode = context.user_data.get("mode")

    text = update.message.text.strip()

    # -------------------------
    # Название новой цели
    # -------------------------

    if mode == "new_goal_name":
        if not text:
            await update.message.reply_text(
                "Название не может быть пустым."
            )
            return

        context.user_data["new_goal_name"] = text
        context.user_data["mode"] = "new_goal_target"

        await update.message.reply_text(
            f"Название: <b>{text}</b>\n\n"
            "Теперь напиши, сколько нужно накопить:",
            parse_mode="HTML"
        )
        return

    # -------------------------
    # Сумма новой цели
    # -------------------------

    if mode == "new_goal_target":
        try:
            target = int(
                float(
                    text.replace(" ", "").replace(",", ".")
                )
            )

            if target <= 0:
                raise ValueError

        except ValueError:
            await update.message.reply_text(
                "Напиши сумму числом, например: <b>500000</b>",
                parse_mode="HTML"
            )
            return

        name = context.user_data["new_goal_name"]

        # Уникальный ID
        goal_id = str(
            max(
                [int(key) for key in goals.keys() if key.isdigit()],
                default=0
            ) + 1
        )

        goals[goal_id] = {
            "name": name,
            "target": target,
            "saved": 0
        }

        save_data()
        context.user_data.clear()

        await update.message.reply_text(
            "🎉 <b>Цель создана!</b>\n\n"
            + goal_text(goals[goal_id]),
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
        return

    # -------------------------
    # Редактирование названия
    # -------------------------

    if mode == "edit_name":
        goal_key = context.user_data["goal"]

        if goal_key not in goals:
            context.user_data.clear()
            await update.message.reply_text(
                "Эта цель больше не существует."
            )
            return

        goals[goal_key]["name"] = text

        context.user_data["mode"] = "edit_target"

        await update.message.reply_text(
            f"Название изменено на <b>{text}</b>.\n\n"
            "Теперь напиши новую сумму цели:",
            parse_mode="HTML"
        )
        return

    # -------------------------
    # Редактирование суммы
    # -------------------------

    if mode == "edit_target":
        try:
            target = int(
                float(
                    text.replace(" ", "").replace(",", ".")
                )
            )

            if target <= 0:
                raise ValueError

        except ValueError:
            await update.message.reply_text(
                "Напиши сумму числом, например: <b>500000</b>",
                parse_mode="HTML"
            )
            return

        goal_key = context.user_data["goal"]

        goals[goal_key]["target"] = target

        save_data()
        context.user_data.clear()

        await update.message.reply_text(
            "✅ <b>Цель обновлена!</b>\n\n"
            + goal_text(goals[goal_key]),
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
        return

    # -------------------------
    # Добавление денег
    # -------------------------

    if mode == "add_amount":
        try:
            amount = int(
                float(
                    text.replace(" ", "").replace(",", ".")
                )
            )

            if amount <= 0:
                raise ValueError

        except ValueError:
            await update.message.reply_text(
                "Напиши сумму числом, например: <b>30000</b>",
                parse_mode="HTML"
            )
            return

        goal_key = context.user_data["goal"]

        goals[goal_key]["saved"] += amount

        save_data()
        context.user_data.clear()

        await update.message.reply_text(
            f"✅ Добавлено <b>{money(amount)}</b>\n\n"
            + goal_text(goals[goal_key]),
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
        return

    # -------------------------
    # Снятие
    # -------------------------

    if mode == "withdraw_amount":
        try:
            amount = int(
                float(
                    text.replace(" ", "").replace(",", ".")
                )
            )

            if amount <= 0:
                raise ValueError

        except ValueError:
            await update.message.reply_text(
                "Напиши сумму числом.",
                parse_mode="HTML"
            )
            return

        goal_key = context.user_data["goal"]
        goal = goals[goal_key]

        if amount > goal["saved"]:
            await update.message.reply_text(
                f"У цели только <b>{money(goal['saved'])}</b>.",
                parse_mode="HTML"
            )
            return

        goal["saved"] -= amount

        save_data()
        context.user_data.clear()

        await update.message.reply_text(
            f"➖ Снято <b>{money(amount)}</b>\n\n"
            + goal_text(goal),
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
        return

    # -------------------------
    # Перенос
    # -------------------------

    if mode == "transfer_amount":
        try:
            amount = int(
                float(
                    text.replace(" ", "").replace(",", ".")
                )
            )

            if amount <= 0:
                raise ValueError

        except ValueError:
            await update.message.reply_text(
                "Напиши сумму числом.",
                parse_mode="HTML"
            )
            return

        from_key = context.user_data["from_goal"]
        to_key = context.user_data["to_goal"]

        from_goal = goals[from_key]
        to_goal = goals[to_key]

        if amount > from_goal["saved"]:
            await update.message.reply_text(
                f"У {from_goal['name']} только "
                f"<b>{money(from_goal['saved'])}</b>.",
                parse_mode="HTML"
            )
            return

        from_goal["saved"] -= amount
        to_goal["saved"] += amount

        save_data()
        context.user_data.clear()

        await update.message.reply_text(
            f"🔄 Перенёс <b>{money(amount)}</b>\n\n"
            f"Из: {from_goal['name']}\n"
            f"В: {to_goal['name']}",
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
        return

    await update.message.reply_text(
        "Выбери действие:",
        reply_markup=main_keyboard()
    )


# =========================
# Ошибки
# =========================

async def error_handler(update, context):
    logging.error(
        "Ошибка:",
        exc_info=context.error
    )


# =========================
# Запуск
# =========================

def main():
    if not TOKEN:
        raise RuntimeError(
            "Не найден BOT_TOKEN"
        )

    load_data()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CallbackQueryHandler(button)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message
        )
    )

    application.add_error_handler(error_handler)

    print("Бот запущен!")

    application.run_polling()


if __name__ == "__main__":
    main()
