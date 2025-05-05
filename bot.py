import pytz
import os
import random
import json
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler
import logging
from flask import Flask

# Логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Отримання змінних середовища
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logging.error("BOT_TOKEN не знайдено в змінних середовища")
    exit(1)

PORT = int(os.environ.get('PORT', 5000))

SUBSCRIBERS_FILE = "subscribers.json"
IMAGES_DIR = "images"

if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)
    logging.warning(f"Створено директорію {IMAGES_DIR}")

# Завантаження/збереження підписників
def load_subscribers():
    try:
        if os.path.exists(SUBSCRIBERS_FILE):
            with open(SUBSCRIBERS_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        logging.error(f"Помилка завантаження підписників: {e}")
        return []

def save_subscribers(subscribers):
    try:
        with open(SUBSCRIBERS_FILE, 'w') as f:
            json.dump(subscribers, f)
    except Exception as e:
        logging.error(f"Помилка збереження підписників: {e}")

# Розсилка
def send_daily_fact(bot):
    try:
        images = os.listdir(IMAGES_DIR)
        if not images:
            logging.error("Папка images пуста.")
            return

        image_file = random.choice(images)
        image_path = os.path.join(IMAGES_DIR, image_file)
        caption = f"Історичний факт дня 📜"

        subscribers = load_subscribers()
        if not subscribers:
            logging.warning("Немає підписників.")
            return

        for chat_id in subscribers:
            try:
                with open(image_path, "rb") as photo:
                    bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
                logging.info(f"Надіслано {chat_id}: {image_file}")
            except Exception as e:
                logging.error(f"Помилка при відправці {chat_id}: {e}")
    except Exception as e:
        logging.error(f"Помилка під час розсилки: {e}")

# Команди
    def subscribe(update: Update, context: CallbackContext):
        chat_id = update.effective_chat.id
        subscribers = load_subscribers()

        if chat_id not in subscribers:
            subscribers.append(chat_id)
            save_subscribers(subscribers)
            logging.info(f"Підписано користувача {chat_id}. Поточні підписники: {load_subscribers()}")
            update.message.reply_text("Ви підписались на щоденну розсилку історичних фактів. 📜")
        else:
            update.message.reply_text("Ви вже підписані.")
    
def unsubscribe(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    subscribers = load_subscribers()

    if chat_id in subscribers:
        subscribers.remove(chat_id)
        save_subscribers(subscribers)
        update.message.reply_text("Ви відписались від розсилки.")
    else:
        update.message.reply_text("Ви не були підписані.")

def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Команди:\n"
        "/start — Інформація\n"
        "/subscribe — Підписатись\n"
        "/unsubscribe — Відписатись\n"
        "/help — Допомога"
    )

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Привіт! Я бот щоденних історичних фактів.\n"
        "Натисніть /subscribe, щоб підписатись."
    )

# Основна функція
def main():
    app = Flask(__name__)

    @app.route('/')
    def index():
        return "Історичний бот працює!"

    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("subscribe", subscribe))
    dispatcher.add_handler(CommandHandler("unsubscribe", unsubscribe))

    # Планувальник
    kyiv_tz = pytz.timezone('Europe/Kyiv')
    scheduler = BackgroundScheduler(timezone=kyiv_tz)
    scheduler.add_job(
        send_daily_fact,
        'cron',
        hour=20,
        minute=35,
        timezone=kyiv_tz,
        args=[updater.bot]
    )
    scheduler.start()
    logging.info("Розсилка налаштована на 19:00 за Києвом.")

    # Додано рядок для виведення запланованих завдань
    logging.info(f"Заплановані завдання: {scheduler.get_jobs()}")

    #updater.start_polling()
    app.run(host='0.0.0.0', port=PORT, threaded=True)

if __name__ == '__main__':
    main()
