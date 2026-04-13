import telebot
from gradio_client import Client, handle_file
import os
from flask import Flask
from threading import Thread
import time
import sys

# --- 1. ВЕБ-СЕРВЕР ДЛЯ RENDER (HEALTH CHECK) ---
PORT = int(os.environ.get('PORT', 10000))
app = Flask('')

@app.route('/')
def home():
    return "Бот глубокой реставрации (Stable Version) активен"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

Thread(target=run_flask, daemon=True).start()

# --- 2. ЗАГРУЗКА КЛЮЧЕЙ ---
TG_TOKEN = os.environ.get('TG_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')

if not TG_TOKEN or not HF_TOKEN:
    print("❌ ОШИБКА: Токены не найдены в Environment Variables!", flush=True)
    sys.exit(1)

bot = telebot.TeleBot(TG_TOKEN.strip())
client = None

def connect_to_ai():
    global client
    space = "sczhou/CodeFormer" 
    try:
        print(f"Подключение к {space}...", flush=True)
        client = Client(space, token=HF_TOKEN.strip())
        print(f"✅ Связь с нейросетью установлена.", flush=True)
        return True
    except Exception as e:
        print(f"❌ Ошибка ИИ: {e}", flush=True)
        return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Режим глубокой реставрации (лицо + фон) активен. Теперь я умею ждать ответа дольше, таймауты должны исчезнуть! 📸")

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    global client
    if client is None:
        if not connect_to_ai():
            bot.reply_to(message, "❌ Нейросеть не отвечает. Попробуй позже.")
            return

    msg = bot.reply_to(message, "⏳ Идет глубокая обработка... Это может занять до 1-2 минут, не отключайся.")
    
    try:
        # Скачивание файла
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_input = "input.jpg"
        with open(temp_input, 'wb') as f:
            f.write(downloaded_file)

        # --- НОВЫЙ МЕХАНИЗМ SUBMIT (БЕЗ ТАЙМАУТОВ) ---
        print(f"Отправка задачи в очередь нейросети...", flush=True)
        
        # Создаем задачу (job) вместо прямого запроса
        job = client.submit(
            handle_file(temp_input), 
            0.7,   # Fidelity (баланс качества и сходства)
            True,  # Background Enhance (улучшение фона)
            True,  # Face Upsample (детальное лицо)
            2,     # Upscale (увеличение 2x)
        )
        
        # Ждем результат до 300 секунд (5 минут)
        result = job.result(timeout=300)

        output_path = result if isinstance(result, str) else result[0]

        # Отправка результата
        with open(output_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="✅ Готово! Лицо и фон восстановлены.")
        
        bot.delete_message(message.chat.id, msg.message_id)
        print("✅ Результат успешно отправлен.", flush=True)

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Ошибка: {error_msg}", flush=True)
        
        if "timeout" in error_msg.lower():
            bot.edit_message_text("❌ Сервер нейросети перегружен. Я попробовал подождать 5 минут, но ответа нет. Попробуй другое фото или чуть позже.", message.chat.id, msg.message_id)
        else:
            bot.edit_message_text(f"❌ Ошибка при обработке: {error_msg}", message.chat.id, msg.message_id)

if __name__ == "__main__":
    time.sleep(2)
    connect_to_ai()
    print("--- Бот запущен в режиме стабильного ожидания ---", flush=True)
    
    while True:
        try:
            bot.remove_webhook()
            bot.polling(none_stop=True, skip_pending=True, interval=0, timeout=60)
        except Exception as e:
            print(f"Перезапуск polling из-за ошибки: {e}", flush=True)
            time.sleep(5)
