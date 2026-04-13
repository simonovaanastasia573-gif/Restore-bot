import telebot
from gradio_client import Client, handle_file
import os
from flask import Flask
from threading import Thread
import time
import sys
from PIL import Image

# --- 1. ВЕБ-СЕРВЕР ---
PORT = int(os.environ.get('PORT', 10000))
app = Flask('')
@app.route('/')
def home(): return "BoberPhoto Ultra-Stable is Active"

Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()

# --- 2. КЛЮЧИ ---
TG_TOKEN = os.environ.get('TG_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')

if not TG_TOKEN or not HF_TOKEN:
    print("❌ ОШИБКА: Токены не найдены!", flush=True)
    sys.exit(1)

bot = telebot.TeleBot(TG_TOKEN.strip())
client = None

def connect_to_ai():
    global client
    space = "sczhou/CodeFormer" 
    try:
        client = Client(space, token=HF_TOKEN.strip())
        print(f"✅ Связь с CodeFormer установлена.", flush=True)
        return True
    except Exception as e:
        print(f"❌ Ошибка ИИ: {e}", flush=True)
        return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я Бобёр-реставратор. 🦫\nПрисылай фото, и я сделаю его четким. Теперь я работаю еще стабильнее!")

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    global client
    if client is None:
        if not connect_to_ai():
            bot.reply_to(message, "❌ Нейросеть спит. Попробуй через минуту.")
            return

    msg = bot.reply_to(message, "⏳ Начинаю полную реставрацию (лицо + фон)...")
    
    try:
        # 1. Скачивание
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        input_path = f"raw_{message.chat.id}.jpg"
        processed_path = f"input_{message.chat.id}.jpg"

        with open(input_path, 'wb') as f:
            f.write(downloaded_file)

        # 2. УМНОЕ ПОДГОТОВЛЕНИЕ (Сжатие для стабильности)
        with Image.open(input_path) as img:
            img = img.convert("RGB")
            # 1200px — идеальный баланс для бесплатного GPU
            max_size = 1200 
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            img.save(processed_path, "JPEG", quality=95)

        # 3. ПОПЫТКА №1: ПОЛНАЯ РЕСТАВРАЦИЯ
        try:
            print(f"[{message.chat.id}] Запуск Full Mode...", flush=True)
            job = client.submit(
                handle_file(processed_path), 
                0.7,   # Fidelity
                True,  # Background Enhance (Фон)
                True,  # Face Upsample (Лицо)
                2      # Upscale 2x
            )
            result = job.result(timeout=250) # Ждем долго
            caption = "✅ Реставрация завершена! Улучшено всё фото (4K)."
            
        except Exception as e:
            # ПОПЫТКА №2: БЕЗОПАСНЫЙ РЕЖИМ (Только лицо)
            print(f"[{message.chat.id}] Сбой Full Mode ({e}), перехожу в Lite...", flush=True)
            bot.edit_message_text("⚠️ Фон слишком сложный, перехожу в безопасный режим (только лицо)...", message.chat.id, msg.message_id)
            
            job = client.submit(
                handle_file(processed_path), 
                0.7, 
                False, # Отключаем фон
                True,  # Оставляем лицо
                1      # Без увеличения
            )
            result = job.result(timeout=150)
            caption = "✅ Реставрация завершена! (Использован безопасный режим для лица)."

        output_path = result if isinstance(result, str) else result[0]

        with open(output_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption=caption)
        
        bot.delete_message(message.chat.id, msg.message_id)

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}", flush=True)
        bot.edit_message_text(f"❌ Не удалось обработать фото: {e}", message.chat.id, msg.message_id)
    
    # Чистим временные файлы
    finally:
        for f in [input_path, processed_path]:
            if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    connect_to_ai()
    bot.remove_webhook()
    bot.polling(none_stop=True, skip_pending=True)
