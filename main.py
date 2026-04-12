import telebot
from gradio_client import Client, handle_file
import os
from flask import Flask
from threading import Thread
import time
import sys

# --- 1. ВЕБ-СЕРВЕР ДЛЯ RENDER (Health Check) ---
PORT = int(os.environ.get('PORT', 10000))
app = Flask('')

@app.route('/')
def home():
    return "Бот активен и готов к работе"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

# Запуск Flask в фоне сразу при старте
Thread(target=run_flask, daemon=True).start()

# --- 2. ЗАГРУЗКА КЛЮЧЕЙ ИЗ RENDER ENVIRONMENT ---
TG_TOKEN = os.environ.get('TG_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')

if not TG_TOKEN or not HF_TOKEN:
    print("❌ ОШИБКА: Токены не найдены в настройках (Environment) Render!", flush=True)
    sys.exit(1)
else:
    print("✅ Токены успешно загружены из системы.", flush=True)

# Инициализация бота с очисткой пробелов
bot = telebot.TeleBot(TG_TOKEN.strip())
client = None

def connect_to_ai():
    global client
    space = "sczhou/CodeFormer"
    try:
        print(f"Попытка подключения к нейросети {space}...", flush=True)
        # strip() защищает от случайных пробелов в ключе
        client = Client(space, token=HF_TOKEN.strip())
        print(f"✅ Успешно! Нейросеть {space} подключена.", flush=True)
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к ИИ: {e}", flush=True)
        return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Бот готов! Присылай фото (лучше файлом или просто фото), и я восстановлю детали лица. 📸")

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    global client
    if client is None:
        if not connect_to_ai():
            bot.reply_to(message, "❌ Нейросеть сейчас недоступна. Попробуй позже.")
            return

    msg = bot.reply_to(message, "⏳ Магия началась... Восстанавливаю текстуры лица (30-60 сек).")
    try:
        # 1. Скачивание файла
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_input = "input.jpg"
        with open(temp_input, 'wb') as f:
            f.write(downloaded_file)

        # 2. Запрос к CodeFormer (БЕЗ api_name)
        # Передаем: файл, fidelity (0.5), upscale (2)
        print(f"Отправка фото в нейросеть...", flush=True)
        result = client.predict(
            handle_file(temp_input), # Поток данных файла
            0.5,                     # Fidelity: баланс между оригиналом и качеством
            2,                       # Upscale: увеличение разрешения
        )

        # 3. Обработка результата
        output_path = result if isinstance(result, str) else result[0]

        # 4. Отправка результата
        with open(output_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="✅ Готово! Качество лица улучшено моделью CodeFormer.")
        
        bot.delete_message(message.chat.id, msg.message_id)
        print("✅ Успешная отправка результата пользователю.", flush=True)

    except Exception as e:
        print(f"Ошибка при обработке фото: {e}", flush=True)
        bot.edit_message_text(f"❌ Произошла ошибка: {e}", message.chat.id, msg.message_id)

if __name__ == "__main__":
    # Небольшая пауза, чтобы Flask успел занять порт
    time.sleep(3)
    
    if connect_to_ai():
        print("--- Запуск polling Telegram ---", flush=True)
        try:
            bot.remove_webhook()
            bot.polling(none_stop=True, skip_pending=True)
        except Exception as e:
            print(f"Критическая ошибка polling: {e}", flush=True)
    else:
        print("❌ Бот не запущен, так как не удалось подключиться к Hugging Face.", flush=True)
