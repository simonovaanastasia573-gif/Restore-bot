import telebot
from gradio_client import Client, handle_file
import os
from flask import Flask
from threading import Thread
import time
import sys

# --- 1. ВЕБ-СЕРВЕР ---
PORT = int(os.environ.get('PORT', 10000))
app = Flask('')
@app.route('/')
def home(): return "Бот полной реставрации активен"

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
        print(f"✅ Успешно подключено к {space}", flush=True)
        return True
    except Exception as e:
        print(f"❌ Ошибка ИИ: {e}", flush=True)
        return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Режим полной реставрации включен! Теперь я улучшаю и лицо, и фон. Присылай фото. 📸")

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    global client
    if client is None:
        if not connect_to_ai():
            bot.reply_to(message, "❌ Нейросеть не отвечает. Попробуй позже.")
            return

    msg = bot.reply_to(message, "⏳ Глубокая реставрация всего снимка... (это займет чуть больше времени)")
    
    try:
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_input = "input.jpg"
        with open(temp_input, 'wb') as f:
            f.write(downloaded_file)

        # --- ОБНОВЛЕННЫЙ ВЫЗОВ ДЛЯ ВСЕГО ФОТО ---
        # Параметры по порядку для CodeFormer:
        # 1. Файл изображения
        # 2. Fidelity (0.7) - баланс глюков и сходства
        # 3. Background_enhance (True) - ВКЛЮЧАЕМ УЛУЧШЕНИЕ ФОНА
        # 4. Face_upsample (True) - ВКЛЮЧАЕМ УЛУЧШЕНИЕ ЛИЦА В ВЫСОКОМ РАЗРЕШЕНИИ
        # 5. Upscale (2) - Увеличение всего фото в 2 раза
        
        result = client.predict(
            handle_file(temp_input), 
            0.7,   # Fidelity
            True,  # Background Enhance (Улучшение фона)
            True,  # Face Upsample (Детальное лицо)
            2,     # Upscale
        )

        output_path = result if isinstance(result, str) else result[0]

        with open(output_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="✅ Реставрация завершена. Улучшено всё фото!")
        
        bot.delete_message(message.chat.id, msg.message_id)

    except Exception as e:
        print(f"❌ Ошибка: {e}", flush=True)
        bot.edit_message_text(f"❌ Ошибка обработки: {e}", message.chat.id, msg.message_id)

if __name__ == "__main__":
    time.sleep(2)
    connect_to_ai()
    print("--- Бот запущен (Full Photo Mode) ---", flush=True)
    while True:
        try:
            bot.remove_webhook()
            bot.polling(none_stop=True, skip_pending=True, interval=0, timeout=60)
        except Exception as e:
            print(f"Ошибка: {e}. Рестарт...", flush=True)
            time.sleep(5)
