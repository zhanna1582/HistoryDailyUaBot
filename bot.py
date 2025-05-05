import pytz
import os
import random
import json
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Получение токена из окружения
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logging.error("Ошибка: Не найден BOT_TOKEN в переменных окружения")
    exit(1)

# Файл для хранения ID подписчиков
SUBSCRIBERS_FILE = "subscribers.json"
# Путь к папке с изображениями
IMAGES_DIR = "images"

# Проверка наличия папки с картинками
if not os.path.exists(IMAGES_DIR) or not os.path.isdir(IMAGES_DIR):
    logging.error(f"Ошибка: Директория {IMAGES_DIR} не существует")
    exit(1)

# Загрузка списка подписчиков
def load_subscribers():
    try:
        if os.path.exists(SUBSCRIBERS_FILE):
            with open(SUBSCRIBERS_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        logging.error(f"Ошибка при загрузке подписчиков: {e}")
        return []

# Сохранение списка подписчиков
def save_subscribers(subscribers):
    try:
        with open(SUBSCRIBERS_FILE, 'w') as f:
            json.dump(subscribers, f)
    except Exception as e:
        logging.error(f"Ошибка при сохранении подписчиков: {e}")

# Функция для отправки фактов всем подписчикам
def send_daily_fact(bot):
    try:
        images = os.listdir(IMAGES_DIR)
        if not images:
            logging.error("Папка изображений пуста.")
            return
        
        image_file = random.choice(images)
        image_path = os.path.join(IMAGES_DIR, image_file)
        caption = f"Історичний факт дня 📜"
        
        subscribers = load_subscribers()
        if not subscribers:
            logging.warning("Нет подписчиков для отправки фактов.")
            return
            
        for chat_id in subscribers:
            try:
                with open(image_path, "rb") as photo:
                    bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
                logging.info(f"Отправлено изображение пользователю {chat_id}: {image_file}")
            except Exception as e:
                logging.error(f"Ошибка при отправке {chat_id}: {e}")
    except Exception as e:
        logging.error(f"Ошибка при отправке ежедневного факта: {e}")

# Команда для подписки
def subscribe(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    subscribers = load_subscribers()
    
    if chat_id not in subscribers:
        subscribers.append(chat_id)
        save_subscribers(subscribers)
        update.message.reply_text("Вы успешно подписались на ежедневные исторические факты! Факты будут приходить каждый день в 17:30.")
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
        "/help - Показать это сообщение"
    )

# Команда для запуска бота
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Привет! Я бот ежедневных исторических фактов.\n"
        "Используйте /subscribe, чтобы подписаться на ежедневную рассылку исторических фактов."
    )

def main():
    # Создание бота
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    
    # Регистрация обработчиков команд
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("subscribe", subscribe))
    dispatcher.add_handler(CommandHandler("unsubscribe", unsubscribe))
    
    # Запуск бота
    updater.start_polling()
    logging.info("Бот запущен и готов к работе.")
    
    # Настройка планировщика с часовым поясом Киева
    kyiv_tz = pytz.timezone('Europe/Kyiv')
    scheduler = BackgroundScheduler(timezone=kyiv_tz)
    scheduler.add_job(
        send_daily_fact, 
        'cron', 
        hour=17, 
        minute=55, 
        timezone=kyiv_tz,
        args=[updater.bot]
    )
    
    # Запуск планировщика
    scheduler.start()
    logging.info("Планировщик запущен. Факты будут отправляться в 17:30 по киевскому времени.")
    
    # Ожидание прерывания для завершения
    updater.idle()
    
    # Остановка планировщика при завершении
    scheduler.shutdown()

if __name__ == '__main__':
    main()