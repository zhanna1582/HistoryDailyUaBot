import pytz
import os
import random
import json
import psycopg2
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler
import logging
from flask import Flask, request
import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Получение токена из окружения
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logging.error("Ошибка: Не найден BOT_TOKEN в переменных окружения")
    exit(1)

# Получение порта из переменной окружения (для Render)
PORT = int(os.environ.get('PORT', 5000))

# Файл для хранения ID подписчиков
SUBSCRIBERS_FILE = "subscribers.json"
# Путь к папке с изображениями
IMAGES_DIR = "images"

# Время для отправки сообщений (Киевское время)
SEND_HOUR_1 = 17
SEND_MINUTE_1 = 0
SEND_HOUR_2 = 20
SEND_MINUTE_2 = 0

# Проверка и создание папки с картинками
if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)
    logging.warning(f"Создана директория {IMAGES_DIR}")
    # Создаем тестовое изображение, если папка пуста
    with open(os.path.join(IMAGES_DIR, "test_image.txt"), "w") as f:
        f.write("Это тестовый файл, замените его реальными изображениями")
    logging.info("Создан тестовый файл в директории images")

# Получение URL базы данных из переменной окружения
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logging.error("Ошибка: Не найден DATABASE_URL в переменных окружения")
    exit(1)

def get_connection():
    """Получает соединение с базой данных."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logging.error(f"Ошибка при подключении к базе данных: {e}")
        raise

# Загрузка списка подписчиков
def load_subscribers():
    """Загружает подписчиков из базы данных."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id FROM subscribers")
        rows = cursor.fetchall()
        subscribers = [row[0] for row in rows]
        cursor.close()
        conn.close()
        logging.info(f"Загружены подписчики: {subscribers}")
        return subscribers
    except Exception as e:
        logging.error(f"Ошибка при загрузке подписчиков из базы данных: {e}")
        return []

# Сохранение списка подписчиков
def save_subscribers(subscribers):
    """Сохраняет подписчиков в базу данных."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM subscribers")  # Очистить таблицу перед добавлением
        for chat_id in subscribers:
            cursor.execute("INSERT INTO subscribers (chat_id) VALUES (%s)", (chat_id,))
        conn.commit()
        cursor.close()
        conn.close()
        logging.info(f"Сохранены подписчики: {subscribers}")
    except Exception as e:
        logging.error(f"Ошибка при сохранении подписчиков в базу данных: {e}")

# Функция для проверки наличия изображений
def check_images():
    images = [f for f in os.listdir(IMAGES_DIR) if os.path.isfile(os.path.join(IMAGES_DIR, f))]
    if not images:
        logging.error("Папка изображений пуста. Создаю тестовый файл.")
        with open(os.path.join(IMAGES_DIR, "test_image.txt"), "w") as f:
            f.write("Это тестовый файл для отправки")
        return ["test_image.txt"]
    return images

# Функция для отправки фактов всем подписчикам
def send_daily_fact(bot):
    try:
        logging.info("Начинаю отправку ежедневного факта...")
        
        # Проверяем наличие изображений
        images = check_images()
        if not images:
            logging.error("Директория изображений пуста даже после попытки создать тестовый файл")
            return
        
        image_file = random.choice(images)
        image_path = os.path.join(IMAGES_DIR, image_file)
        caption = f"Історичний факт дня 📜 - {datetime.datetime.now().strftime('%d.%m.%Y')}"
        
        # Загружаем подписчиков
        subscribers = load_subscribers()
        logging.info(f"Загружены подписчики: {subscribers}")
        
        if not subscribers:
            logging.warning("Нет подписчиков для отправки фактов.")
            # Отправляем тестовое сообщение на дефолтный ID, если он задан в переменных окружения
            default_id = os.getenv("DEFAULT_CHAT_ID")
            if default_id:
                try:
                    with open(image_path, "rb") as photo:
                        bot.send_photo(chat_id=default_id, photo=photo, caption=caption + " (тестовая отправка, нет подписчиков)")
                    logging.info(f"Отправлено тестовое изображение на ID {default_id}")
                except Exception as e:
                    logging.error(f"Ошибка при тестовой отправке: {e}")
            return
        
        successful = 0
        for chat_id in subscribers:
            try:
                with open(image_path, "rb") as photo:
                    bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
                logging.info(f"Отправлено изображение пользователю {chat_id}: {image_file}")
                successful += 1
            except Exception as e:
                logging.error(f"Ошибка при отправке {chat_id}: {e}")
        
        logging.info(f"Отправка завершена. Успешно: {successful}/{len(subscribers)}")
    except Exception as e:
        logging.error(f"Ошибка при отправке ежедневного факта: {e}")

# Команда для ручной отправки (для тестирования)
def send_now(update: Update, context: CallbackContext):
    admin_ids = os.getenv("ADMIN_IDS", "").split(",")
    chat_id = str(update.effective_chat.id)
    
    if chat_id in admin_ids:
        update.message.reply_text("Начинаю отправку исторического факта всем подписчикам...")
        send_daily_fact(context.bot)
        update.message.reply_text("Отправка завершена!")
    else:
        update.message.reply_text("Вибачте, ця команда доступна тільки адміністраторам бота.")

# Команда для проверки статуса подписки
def status(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    subscribers = load_subscribers()
    
    if chat_id in subscribers:
        update.message.reply_text(f"Ви підписані на щоденні історичні факти. Вони надходять о {SEND_HOUR_1}:00 та {SEND_HOUR_2}:00 за київським часом.")
    else:
        update.message.reply_text("Ви не підписані на щоденні історичні факти. Використовуйте /subscribe для підписки.")

# Команда для подписки
def subscribe(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    subscribers = load_subscribers()
    
    if chat_id not in subscribers:
        subscribers.append(chat_id)
        save_subscribers(subscribers)
        update.message.reply_text(f"Ви успішно підписалися на щоденні історичні факти! Факти надходитимуть щодня о {SEND_HOUR_1}:00 та {SEND_HOUR_2}:00 за київським часом.")
    else:
        update.message.reply_text("Ви вже підписані на щоденні історичні факти.")

# Команда для отписки
def unsubscribe(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    subscribers = load_subscribers()
    
    if chat_id in subscribers:
        subscribers.remove(chat_id)
        save_subscribers(subscribers)
        update.message.reply_text("Ви відписалися від щоденних історичних фактів.")
    else:
        update.message.reply_text("Ви не були підписані на щоденні історичні факти.")

# Команда для получения помощи
def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Доступні команди:\n"
        "/start - Інформація про бота\n"
        "/subscribe - Підписатися на щоденні історичні факти\n"
        "/unsubscribe - Відписатися від щоденних історичних фактів\n"
        "/status - Перевірити статус підписки\n"
        "/help - Показати це повідомлення"
    )

# Команда для запуска бота
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Привіт! Я бот щоденних історичних фактів.\n"
        "Використовуйте /subscribe, щоб підписатися на щоденну розсилку історичних фактів. "
        f"Факти надходять о {SEND_HOUR_1}:00 та {SEND_HOUR_2}:00 за київським часом."
    )

def main():
    # Создание Flask приложения для привязки к порту (требуется Render)
    app = Flask(__name__)
    
    @app.route('/')
    def index():
        return "Бот історії запущено! Версія 1.1.0"
    
    @app.route('/ping')
    def ping():
        return "Pong! Бот активний. Поточний час: " + datetime.datetime.now().strftime("%H:%M:%S %d.%m.%Y")
    
    # Создание бота и updater
    bot = Bot(TOKEN)
    updater = Updater(bot=bot, use_context=True)  # Use the explicit bot instance
    dispatcher = updater.dispatcher
    
    # Регистрация обработчиков команд
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("subscribe", subscribe))
    dispatcher.add_handler(CommandHandler("unsubscribe", unsubscribe))
    dispatcher.add_handler(CommandHandler("status", status))
    
    # Добавляем команду для ручной отправки
    dispatcher.add_handler(CommandHandler("sendnow", send_now))
    
    # Настройка планировщика с часовым поясом Киева
    kyiv_tz = pytz.timezone('Europe/Kyiv')
    scheduler = BackgroundScheduler(timezone=kyiv_tz)
    
    # Регистрируем задачу на 17:00
    scheduler.add_job(
        send_daily_fact,
        'cron',
        hour=SEND_HOUR_1,
        minute=SEND_MINUTE_1,
        timezone=kyiv_tz,
        args=[bot],  # Передаем экземпляр бота в задачу
        id='morning_fact'
    )
    
    # Регистрируем задачу на 20:00
    scheduler.add_job(
        send_daily_fact,
        'cron',
        hour=SEND_HOUR_2,
        minute=SEND_MINUTE_2,
        timezone=kyiv_tz,
        args=[bot],  # Передаем экземпляр бота в задачу
        id='evening_fact'
    )
    
    # Добавляем дополнительную задачу для проверки активности каждые 15 минут
    def keep_alive():
        logging.info("Перевірка активності: Бот працює. Поточний час (UTC): " +
                     datetime.datetime.utcnow().strftime("%H:%M:%S %d.%m.%Y"))
        
        # Додаємо перевірку наступного виконання запланованих завдань
        jobs = scheduler.get_jobs()
        for job in jobs:
            if job.id in ['morning_fact', 'evening_fact']:
                next_run = job.next_run_time
                logging.info(f"Наступне виконання завдання {job.id}: {next_run}")
    
    scheduler.add_job(keep_alive, 'interval', minutes=15, id='keep_alive')
    
    # Запуск планировщика
    scheduler.start()
    logging.info(f"Планувальник запущено. Факти будуть надсилатися о {SEND_HOUR_1}:00 та {SEND_HOUR_2}:00 за київським часом.")
    
    # Проверяем текущее состояние
    subs = load_subscribers()
    logging.info(f"Завантажені підписники при запуску: {subs}")
    
    # Настройка вебхука для Render
    if 'RENDER_EXTERNAL_HOSTNAME' in os.environ:
        webhook_url = f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/webhook"
        updater.bot.set_webhook(webhook_url)
        logging.info(f"Вебхук встановлено на {webhook_url}")
    else:
        logging.warning("RENDER_EXTERNAL_HOSTNAME не знайдено, вебхук не встановлено")
    
    # Обработчик для вебхука Flask (Render отправляет сюда обновления)
    @app.route("/webhook", methods=['POST'])
    def webhook():
        update = Update.de_json(request.get_json(force=True), bot=updater.bot)  # Pass bot to from_json
        dispatcher.process_update(update)
        return "ok", 200
    
    # Запуск Flask приложения, чтобы привязаться к порту
    app.run(host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    # Создаем таблицу subscribers, если она не существует
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS subscribers (chat_id BIGINT PRIMARY KEY)""")
        conn.commit()
        cursor.close()
        conn.close()
        logging.info("Таблиця підписників перевірена/створена")
    except Exception as e:
        logging.error(f"Помилка створення таблиці: {e}")
    main()