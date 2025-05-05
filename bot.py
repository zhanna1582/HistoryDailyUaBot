import pytz
import os
import random
from telegram import Bot
from apscheduler.schedulers.background import BackgroundScheduler
import logging

# Логування помилок
logging.basicConfig(level=logging.INFO)

# Отримання токена і chat_id з оточення
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Перевірка наявності необхідних змінних оточення
if not TOKEN or not CHAT_ID:
    logging.error("Помилка: Не знайдено BOT_TOKEN або CHAT_ID в змінних оточення")
    exit(1)

bot = Bot(token=TOKEN)

# Шлях до папки з картинками
IMAGES_DIR = "images"

# Перевірка наявності папки з картинками
if not os.path.exists(IMAGES_DIR) or not os.path.isdir(IMAGES_DIR):
    logging.error(f"Помилка: Директорія {IMAGES_DIR} не існує")
    exit(1)

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
kyiv_tz = pytz.timezone('Europe/Kyiv')
scheduler = BackgroundScheduler(timezone=kyiv_tz)
scheduler.add_job(send_daily_fact, 'cron', hour=17, minute=30, timezone=kyiv_tz)

# Запуск планувальника
scheduler.start()

print("✅ Бот запущено. Надсилаю тестове повідомлення...")
try:
    send_daily_fact()  # Тестове надсилання
except Exception as e:
    logging.error(f"Помилка при тестовому надсиланні: {e}")

# Тримаємо програму запущеною більш елегантним способом
try:
    # Блокує виконання поки планувальник не завершиться (що не відбудеться)
    import signal
    
    def shutdown(signum, frame):
        scheduler.shutdown()
        print("Бот зупинено.")
        exit(0)
    
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    # Безпечніший варіант безкінечного циклу
    signal.pause()
except (KeyboardInterrupt, SystemExit):
    scheduler.shutdown()
    print("Бот зупинено.")