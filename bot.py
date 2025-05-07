import pytz
import os
import random
import json
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

# Проверка и создание папки с картинками
if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)
    logging.warning(f"Создана директория {IMAGES_DIR}")
    # Создаем тестовое изображение, если папка пуста
    with open(os.path.join(IMAGES_DIR, "test_image.txt"), "w") as f:
        f.write("Это тестовый файл, замените его реальными изображениями")
    logging.info("Создан тестовый файл в директории images")

# Загрузка списка подписчиков
def load_subscribers():
    try:
        if os.path.exists(SUBSCRIBERS_FILE):
            with open(SUBSCRIBERS_FILE, 'r') as f:
                try:
                    data = json.load(f)  # Попытка загрузить JSON
                    if isinstance(data, list):
                        return data
                    else:
                        logging.warning(f"Файл {SUBSCRIBERS_FILE} содержал не список: {data}, возвращаю пустой список")
                        return []
                except json.JSONDecodeError:
                    logging.warning(f"Файл {SUBSCRIBERS_FILE} поврежден, возвращаю пустой список")
                    return []
        else:
            return []
    except Exception as e:
        logging.error(f"Ошибка при загрузке подписчиков: {e}")
        return []

# Сохранение списка подписчиков
def save_subscribers(subscribers):
    try:
        # Ensure the directory exists
        dir_name = os.path.dirname(SUBSCRIBERS_FILE)
        if dir_name:  # Check if the directory name is not empty
            os.makedirs(dir_name, exist_ok=True)
        # Use a temporary file to ensure atomic write
        temp_file = SUBSCRIBERS_FILE + ".tmp"
        with open(temp_file, 'w') as f:
            json.dump(subscribers, f)
        os.rename(temp_file, SUBSCRIBERS_FILE)  # Atomic rename
        logging.info(f"Сохранены подписчики: {subscribers}")
    except Exception as e:
        logging.error(f"Ошибка при сохранении подписчиков: {e}")

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
        update.message.reply_text("Извините, эта команда доступна только администраторам бота.")

# Команда для проверки статуса подписки
def status(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    subscribers = load_subscribers()
    
    if chat_id in subscribers:
        update.message.reply_text("Вы подписаны на ежедневные исторические факты. Они приходят в 18:23 по киевскому времени.")
    else:
        update.message.reply_text("Вы не подписаны на ежедневные исторические факты. Используйте /subscribe для подписки.")

# Команда для подписки
def subscribe(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    subscribers = load_subscribers()
    
    if chat_id not in subscribers:
        subscribers.append(chat_id)
        save_subscribers(subscribers)
        update.message.reply_text("Вы успешно подписались на ежедневные исторические факты! Факты будут приходить каждый день в 20:50 по киевскому времени.")
    else:
        update.message.reply_text("Вы уже подписаны на ежедневные исторические факты.")

# Команда для отписки
def unsubscribe(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    subscribers = load_subscribers()
    
    if chat_id in subscribers:
        subscribers.remove(chat_id)
        save_subscribers(subscribers)
        update.message.reply_text("Вы отписались от ежедневных исторических фактов.")
    else:
        update.message.reply_text("Вы не были подписаны на ежедневные исторические факты.")

# Команда для получения помощи
def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Доступные команды:\n"
        "/start - Информация о боте\n"
        "/subscribe - Подписаться на ежедневные исторические факты\n"
        "/unsubscribe - Отписаться от ежедневных исторических фактов\n"
        "/status - Проверить статус подписки\n"
        "/help - Показать это сообщение"
    )

# Команда для запуска бота
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Привет! Я бот ежедневных исторических фактов.\n"
        "Используйте /subscribe, чтобы подписаться на ежедневную рассылку исторических фактов. "
        "Факты приходят в 20:50 по киевскому времени."
    )

def main():
    # Создание Flask приложения для привязки к порту (требуется Render)
    app = Flask(__name__)
    
    @app.route('/')
    def index():
        return "Бот истории запущен! Версия 1.0.1"
    
    @app.route('/ping')
    def ping():
        return "Pong! Бот активен. Текущее время: " + datetime.datetime.now().strftime("%H:%M:%S %d.%m.%Y")
    
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
    
    # Регистрируем задачу на 18:33
    scheduler.add_job(
        send_daily_fact,
        'cron',
        hour=19,
        minute=29,  # Исправлено значение минуты
        timezone=kyiv_tz,
        args=[bot]  # Pass bot instance to the job
    )
    
    # Добавляем дополнительную задачу для проверки активности каждые 15 минут
    def keep_alive():
        logging.info("Проверка активности: Бот работает. Текущее время (UTC): " +
                     datetime.datetime.utcnow().strftime("%H:%M:%S %d.%m.%Y"))
    
    scheduler.add_job(keep_alive, 'interval', minutes=15)
    
    # Запуск планировщика
    scheduler.start()
    logging.info("Планировщик запущен. Факты будут отправляться в 18:33 по киевскому времени.")
    
    # Проверяем текущее состояние
    subs = load_subscribers()
    logging.info(f"Загружены подписчики при запуске: {subs}")
    
    # Настройка вебхука для Render
    webhook_url = f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/webhook"
    updater.bot.set_webhook(webhook_url)
    
    # Обработчик для вебхука Flask (Render отправляет сюда обновления)
    @app.route("/webhook", methods=['POST'])
    def webhook():
        update = Update.de_json(request.get_json(force=True), bot=updater.bot)  # Pass bot to from_json
        dispatcher.process_update(update)
        return "ok", 200
    
    # Запуск Flask приложения, чтобы привязаться к порту
    app.run(host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    main()
