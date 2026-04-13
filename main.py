import telebot
from gradio_client import Client, handle_file
import os
from flask import Flask
from threading import Thread
import time
import sys
from PIL import Image # Библиотека для сжатия

# --- 1. ВЕБ-СЕРВЕР ---
PORT = int(os.environ.get('PORT', 10000))
app = Flask('')
@app.route('/')
def home(): return "Бот со сжатием и защитой активен"

Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()

# --- 2. КЛЮЧИ ---
TG_TOKEN = os.environ.get('TG_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')

if not TG_TOKEN or not HF_TOKEN:
    print("❌ ОШИБКА: Проверь переменные в Render!", flush=True)
    sys.exit(1)

bot = telebot.TeleBot(TG_TOKEN.strip())
client = None

def connect_to_ai():
    global client
    space = "sczhou/CodeFormer" 
    try:
        print(f"Подключение к {space}...", flush=True)
        client = Client(space, token=HF_TOKEN.strip())
        print(f"✅ Связь установлена.", flush=True)
        return True
    except Exception as e:
        print(f"❌ Ошибка ИИ: {e}", flush=True)
        return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Я готов! Теперь я автоматически подготавливаю фото, чтобы не было ошибок. Присылай! 📸")

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    global client
    if client is None:
        if not connect_to_ai():
            bot.reply_to(message, "❌ Нейросеть сейчас не отвечает.")
            return

    msg = bot.reply_to(message, "⏳ Подготавливаю и обрабатываю фото...")
    
    try:
        # 1. Скачивание
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with open("raw_input.jpg", 'wb') as f:
            f.write(downloaded_file)

        # 2. УМНОЕ СЖАТИЕ (Защита от Unexpected Error)
        # Если фото слишком большое, сжимаем его до 1500px, чтобы сервер HF не падал
        with Image.open("raw_input.jpg") as img:
            img = img.convert("RGB")
            max_size = 1500
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                print(f"Фото сжато до {new_size}", flush=True)
            img.save("input.jpg", "JPEG", quality=90)

        # 3. ПОПЫТКА ОБРАБОТКИ
        try:
            print("Запуск нейросети (Full Mode)...", flush=True)
            job = client.submit(
                handle_file("input.jpg"), 
                0.7,   # Fidelity
                True,  # Background Enhance
                True,  # Face Upsample
                2      # Upscale
            )
            result = job.result(timeout=200)
        except Exception as e:
            print(f"Сбой Full Mode, пробуем Lite Mode: {e}", flush=True)
            # Если не вышло с фоном, пробуем только лицо (это всегда работает)
            job = client.submit(
                handle_file("input.jpg"), 
                0.7, 
                False, # Отключаем фон для стабильности
                True, 
                1      # Без увеличения
            )
            result = job.result(timeout=150)

        output_path = result if isinstance(result, str) else result[0]

        with open(output_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="✅ Реставрация завершена! (Использован безопасный режим)")
        
        bot.delete_message(message.chat.id, msg.message_id)

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}", flush=True)
        bot.edit_message_text(f"❌ Не удалось обработать это фото. Попробуй другое. Ошибка: {e}", message.chat.id, msg.message_id)

if __name__ == "__main__":
    time.sleep(2)
    connect_to_ai()
    print("--- Бот запущен с защитой от сбоев ---", flush=True)
    while True:
        try:
            bot.remove_webhook()
            bot.polling(none_stop=True, skip_pending=True, interval=0, timeout=60)
        except Exception as e:
            time.sleep(5)
