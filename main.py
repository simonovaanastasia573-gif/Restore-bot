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
    return "Bot is alive"

Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()

# --- 2. ЗАГРУЗКА КЛЮЧЕЙ ---
TG_TOKEN = os.environ.get('TG_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')

if not TG_TOKEN or not HF_TOKEN:
    print("❌ ОШИБКА: Проверь переменные в Render!", flush=True)
    sys.exit(1)

bot = telebot.TeleBot(TG_TOKEN.strip())
client = None

# --- 3. УМНОЕ ПОДКЛЮЧЕНИЕ ---
def connect_to_ai():
    global client
    # Самый стабильный адрес на текущий момент
    space = "sczhou/CodeFormer" 
    try:
        print(f"Подключение к {space}...", flush=True)
        client = Client(space, token=HF_TOKEN.strip())
        print(f"✅ Успешно подключено к {space}", flush=True)
        return True
    except Exception as e:
        print(f"❌ Критическая ошибка ИИ: {e}", flush=True)
        return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Я снова в сети! Отправь фото, и я восстановлю лицо без искажений. 📸")

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    global client
    if client is None:
        if not connect_to_ai():
            bot.reply_to(message, "❌ Нейросеть не отвечает. Попробуй позже.")
            return

    msg = bot.reply_to(message, "⏳ Реставрация лица в процессе...")
    
    try:
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_input = "input.jpg"
        with open(temp_input, 'wb') as f:
            f.write(downloaded_file)

        # --- НАСТРОЙКИ ПРОТИВ ГЛЮКОВ ---
        # Мы используем fidelity 0.8-0.9. Это "усмиряет" нейросеть.
        # Она перестает рисовать лишнее и просто чистит то, что есть.
        result = client.predict(
            handle_file(temp_input), 
            0.8, # Fidelity (0.8 = больше сходства, меньше глюков)
            2,   # Увеличение (upscale)
        )

        output_path = result if isinstance(result, str) else result[0]

        with open(output_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="✅ Реставрация завершена.")
        
        bot.delete_message(message.chat.id, msg.message_id)

    except Exception as e:
        print(f"❌ Ошибка: {e}", flush=True)
        bot.edit_message_text(f"❌ Ошибка: {e}", message.chat.id, msg.message_id)

if __name__ == "__main__":
    time.sleep(2)
    connect_to_ai()
    print("--- Запуск polling ---", flush=True)
    # Пытаемся запустить, даже если есть конфликты
    while True:
        try:
            bot.remove_webhook()
            bot.polling(none_stop=True, skip_pending=True, interval=0)
        except Exception as e:
            print(f"Ошибка polling: {e}. Перезапуск через 5 сек...", flush=True)
            time.sleep(5)
