import os
import json
import logging
from datetime import date, timedelta, time

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Файл для зберігання контактів ─────────────────────────────────────────────
DATA_FILE = "/app/data/birthdays.json"


def load_data() -> dict:
    """Завантажити контакти з файлу."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_data(data: dict) -> None:
    """Зберегти контакти у файл."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Команди бота ───────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Привітальне повідомлення."""
    text = (
        "👋 *Привіт! Я бот для нагадування про дні народження.*\n\n"
        "Я надішлю тобі нагадування за 7 днів до дня народження кожного контакту.\n\n"
        "📋 *Команди:*\n"
        "/add Ім'я ДД.ММ — додати контакт\n"
        "/list — показати всі контакти\n"
        "/delete Ім'я — видалити контакт\n"
        "/myid — дізнатися свій Chat ID\n"
        "/help — ця довідка"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показати Chat ID користувача."""
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"🆔 Твій Chat ID: `{chat_id}`\n\n"
        "Скопіюй це число і встав у змінну `CHAT_ID` на Railway.",
        parse_mode="Markdown",
    )


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Додати контакт. Використання: /add Ім'я ДД.ММ"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Використання: `/add Ім'я ДД.ММ`\n"
            "Приклад: `/add Іван 15.06`",
            parse_mode="Markdown",
        )
        return

    name = context.args[0]
    date_str = context.args[1]

    try:
        parts = date_str.split(".")
        if len(parts) != 2:
            raise ValueError
        day, month = int(parts[0]), int(parts[1])
        if not (1 <= month <= 12 and 1 <= day <= 31):
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Неправильний формат дати.\n"
            "Використовуй *ДД.ММ*, наприклад: `15.06`",
            parse_mode="Markdown",
        )
        return

    data = load_data()
    data[name] = {"day": day, "month": month}
    save_data(data)

    await update.message.reply_text(
        f"✅ Додано: *{name}* — {day:02d}.{month:02d}",
        parse_mode="Markdown",
    )


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показати список усіх контактів."""
    data = load_data()
    if not data:
        await update.message.reply_text(
            "📋 Список порожній.\nДодай контакти командою `/add`",
            parse_mode="Markdown",
        )
        return

    # Сортуємо за місяцем, потім за днем
    sorted_contacts = sorted(data.items(), key=lambda x: (x[1]["month"], x[1]["day"]))

    lines = ["🎂 *Дні народження:*\n"]
    for name, info in sorted_contacts:
        lines.append(f"• *{name}* — {info['day']:02d}.{info['month']:02d}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Видалити контакт. Використання: /delete Ім'я"""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Використання: `/delete Ім'я`\n"
            "Приклад: `/delete Іван`",
            parse_mode="Markdown",
        )
        return

    name = context.args[0]
    data = load_data()

    if name not in data:
        await update.message.reply_text(
            f"❌ Контакт *{name}* не знайдено у списку.",
            parse_mode="Markdown",
        )
        return

    del data[name]
    save_data(data)
    await update.message.reply_text(
        f"🗑️ *{name}* видалено зі списку.",
        parse_mode="Markdown",
    )


# ── Щоденна перевірка днів народження ─────────────────────────────────────────

async def check_birthdays(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Перевіряє чи є дні народження через 7 днів і надсилає нагадування."""
    chat_id = os.environ.get("CHAT_ID")
    if not chat_id:
        logger.warning("CHAT_ID не встановлено — нагадування не надсилаються.")
        return

    today = date.today()
    target = today + timedelta(days=7)

    data = load_data()
    for name, info in data.items():
        if info["day"] == target.day and info["month"] == target.month:
            logger.info(f"Надсилаю нагадування про {name}")
            await context.bot.send_message(
                chat_id=int(chat_id),
                text=(
                    f"🎂 *Нагадування!*\n\n"
                    f"Через 7 днів — *{target.strftime('%d.%m')}* — "
                    f"день народження у *{name}*! 🎉\n\n"
                    f"Не забудь привітати!"
                ),
                parse_mode="Markdown",
            )


# ── Запуск ─────────────────────────────────────────────────────────────────────

def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("Змінна середовища BOT_TOKEN не встановлена!")

    app = Application.builder().token(token).build()

    # Реєструємо команди
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("myid", cmd_myid))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("delete", cmd_delete))

    # Щоденна перевірка о 09:00
    app.job_queue.run_daily(
        check_birthdays,
        time=time(hour=9, minute=0),
    )

    logger.info("Бот запущено!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
