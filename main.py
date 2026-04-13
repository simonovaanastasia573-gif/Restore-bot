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
    return "Бот активен и готов к реставрации"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

# Запуск Flask в фоне, чтобы Render видел, что сервис живой
Thread(target=run_flask, daemon=True).start()

# --- 2. ЗАГРУЗКА КЛЮЧЕЙ ИЗ СИСТЕМЫ ---
TG_TOKEN = os.environ.get('TG_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')

if not TG_TOKEN or not HF_TOKEN:
    print("❌ ОШИБКА: Токены не найдены в Environment Variables Render!", flush=True)
    sys.exit(1)

bot = telebot.TeleBot(TG_TOKEN.strip())
client = None

# --- 3. ПОДКЛЮЧЕНИЕ К НЕЙРОСЕТИ ---
def connect_to_ai():
    global client
    space = "sczhou/CodeFormer"
    try:
        print(f"Попытка связи с {space}...", flush=True)
        # Подключаемся к стабильному зеркалу CodeFormer
        client = Client(space, token=HF_TOKEN.strip())
        print(f"✅ Успешно! Нейросеть {space} подключена.", flush=True)
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к ИИ: {e}", flush=True)
        return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Я в сети! Присылай фото (лучше файлом), и я восстановлю лицо. Настройки оптимизированы для минимума глюков. 📸")

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    global client
    if client is None:
        if not connect_to_ai():
            bot.reply_to(message, "❌ Нейросеть не отвечает. Попробуй через минуту.")
            return

    msg = bot.reply_to(message, "⏳ Магия началась... Пожалуйста, подожди (до 1 минуты).")
    
    try:
        # Скачивание
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_input = "input.jpg"
        with open(temp_input, 'wb') as f:
            f.write(downloaded_file)

        # Обработка через нейросеть
        print(f"Запрос к нейросети для чата {message.chat.id}...", flush=True)
        
        # Мы НЕ используем api_name, чтобы избежать ошибок версий
        # Параметры: (изображение, fidelity=0.7, upscale=2)
        result = client.predict(
            handle_file(temp_input), 
            0.7,  # Уровень сходства: 0.7 убирает глюки, но оставляет четкость
            2,    # Увеличение разрешения
        )

        # Вытаскиваем путь к файлу
        output_path = result if isinstance(result, str) else result[0]

        # Отправка результата
        with open(output_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="✅ Реставрация завершена! Глюки минимизированы.")
        
        bot.delete_message(message.chat.id, msg.message_id)
        print(f"✅ Успех для чата {message.chat.id}", flush=True)

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Ошибка обработки: {error_msg}", flush=True)
        
        if "timeout" in error_msg.lower():
            bot.edit_message_text("❌ Сервер нейросети слишком долго отвечал. Попробуй отправить это фото еще раз, сейчас канал должен быть 'прогрет'.", message.chat.id, msg.message_id)
        else:
            bot.edit_message_text(f"❌ Произошла ошибка: {error_msg}", message.chat.id, msg.message_id)

# --- 4. ЗАПУСК БОТА ---
if __name__ == "__main__":
    time.sleep(3)
    connect_to_ai()
    
    print("--- Бот запущен и готов к работе ---", flush=True)
    
    # Бесконечный цикл с перезапуском при ошибках (защита от падений)
    while True:
        try:
            bot.remove_webhook()
            bot.polling(none_stop=True, skip_pending=True, interval=0, timeout=60)
        except Exception as e:
            print(f"Ошибка Polling: {e}. Перезапуск через 5 секунд...", flush=True)
            time.sleep(5)
