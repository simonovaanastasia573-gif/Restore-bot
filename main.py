import telebot
from gradio_client import Client, handle_file
import os
from flask import Flask
from threading import Thread
import time
import sys

# --- 1. ВЕБ-СЕРВЕР ДЛЯ RENDER ---
PORT = int(os.environ.get('PORT', 10000))
app = Flask('')

@app.route('/')
def home():
    return "Бот на базе Microsoft RestoreFormer активен"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

Thread(target=run_flask, daemon=True).start()

# --- 2. ЗАГРУЗКА КЛЮЧЕЙ ---
TG_TOKEN = os.environ.get('TG_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')

if not TG_TOKEN or not HF_TOKEN:
    print("❌ ОШИБКА: Переменные окружения не найдены!", flush=True)
    sys.exit(1)

bot = telebot.TeleBot(TG_TOKEN.strip())
client = None

def connect_to_ai():
    global client
    # Переключаемся на модель от Microsoft
    space = "microsoft/RestoreFormer"
    try:
        print(f"Подключение к Microsoft {space}...", flush=True)
        client = Client(space, token=HF_TOKEN.strip())
        print(f"✅ Успешно! Модель Microsoft подключена.", flush=True)
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к Microsoft: {e}", flush=True)
        # Если Microsoft недоступен, пробуем запасной вариант
        print("Пробую запасной сервер...", flush=True)
        try:
            client = Client("sczhou/CodeFormer", token=HF_TOKEN.strip())
            return True
        except:
            return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Использую технологию Microsoft RestoreFormer. Присылай фото! 📸")

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    global client
    if client is None:
        if not connect_to_ai():
            bot.reply_to(message, "❌ Серверы нейросети перегружены. Попробуй позже.")
            return

    msg = bot.reply_to(message, "⏳ Реставрация от Microsoft началась...")
    try:
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_input = "input.jpg"
        with open(temp_input, 'wb') as f:
            f.write(downloaded_file)

        # Запрос к Microsoft RestoreFormer
        # Обычно она принимает просто картинку, без лишних "глючных" ползунков
        print(f"Обработка через RestoreFormer...", flush=True)
        result = client.predict(
            handle_file(temp_input), 
            api_name="/predict"
        )

        output_path = result if isinstance(result, str) else result[0]

        with open(output_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="✅ Восстановлено технологией Microsoft.")
        
        bot.delete_message(message.chat.id, msg.message_id)

    except Exception as e:
        print(f"Ошибка: {e}", flush=True)
        bot.edit_message_text(f"❌ Ошибка реставрации: {e}", message.chat.id, msg.message_id)

if __name__ == "__main__":
    time.sleep(3)
    connect_to_ai()
    print("--- Бот запущен ---", flush=True)
    try:
        bot.remove_webhook()
        bot.polling(none_stop=True, skip_pending=True)
    except Exception as e:
        print(f"Ошибка polling: {e}", flush=True)
