import pytz
import os
import random
from telegram import Bot
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
import logging

# Логування помилок
logging.basicConfig(level=logging.INFO)

# Отримання токена і chat_id з оточення
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TOKEN)

# Шлях до папки з картинками
IMAGES_DIR = "images"

def send_daily_fact():
    try:
        images = os.listdir(IMAGES_DIR)
        if not images:
            logging.error("Папка зображень порожня.")
            return

        image_file = random.choice(images)
        image_path = os.path.join(IMAGES_DIR, image_file)

        caption = f"Історичний факт дня 📜"  # Можна додати текст або змінювати
        with open(image_path, "rb") as photo:
            bot.send_photo(chat_id=CHAT_ID, photo=photo, caption=caption)
        logging.info(f"Надіслано зображення: {image_file}")
    except Exception as e:
        logging.error(f"Помилка при надсиланні факту: {e}")

# Створення планувальника з часовою зоною
scheduler = BackgroundScheduler(timezone=timezone("Europe/Kyiv"))
scheduler.add_job(send_daily_fact, 'cron', hour=17, minute=15, timezone=pytz.timezone('Europe/Kyiv'))
scheduler.start()

print("✅ Бот запущено. Надсилаю тестове повідомлення...")
send_daily_fact()  # ⬅️ Цей рядок одразу запускає надсилання
scheduler.start()

# Безкінечний цикл, щоб бот не завершився одразу
import time
while True:
    time.sleep(10)
