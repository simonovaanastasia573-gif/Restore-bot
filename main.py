import telebot
from gradio_client import Client, handle_file
import os
from flask import Flask
from threading import Thread
import time

# --- 1. ВЕБ-СЕРВЕР ДЛЯ RENDER (ОБЯЗАТЕЛЬНО) ---
PORT = int(os.environ.get('PORT', 10000))
app = Flask('')

@app.route('/')
def home():
    return "Бот активен"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

# Запуск Flask в фоне
Thread(target=run_flask, daemon=True).start()

# --- 2. ТВОИ ОБНОВЛЕННЫЕ КЛЮЧИ ---
import os

# Теперь бот будет брать ключи из настроек Render, а не из текста кода
TG_TOKEN = os.environ.get('TG_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')

# Проверка, что ключи дошли
if not TG_TOKEN or not HF_TOKEN:
    print("❌ ОШИБКА: Токены не найдены в переменных окружения Render!", flush=True)
else:
    print("✅ Токены успешно загружены из системы.", flush=True)

bot = telebot.TeleBot(TG_TOKEN.strip())
client = None

def connect_to_ai():
    global client
    # Используем CodeFormer — это лучшая модель для лиц на сегодня
    space = "sczhou/CodeFormer"
    try:
        print(f"Подключение к нейросети {space}...")
        client = Client(space, token=HF_TOKEN.strip())
        print(f"✅ Успешно! Нейросеть подключена.")
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к ИИ: {e}")
        return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Бот запущен на новом токене! Присылай фото для реставрации. 📸")

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    if client is None:
        if not connect_to_ai():
            bot.reply_to(message, "❌ Нейросеть сейчас не отвечает. Попробуй позже.")
            return

    msg = bot.reply_to(message, "⏳ Магия началась... Восстанавливаю детали лица.")
    try:
        # Скачивание файла
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open("input.jpg", 'wb') as f:
            f.write(downloaded_file)
        
        # Запрос к CodeFormer
        result = client.predict(
            image=handle_file("input.jpg"),
            codeformer_fidelity=0.5,
            upscale=2,
            api_name="/predict"
        )
        
        output_path = result if isinstance(result, str) else result[0]
        
        # Отправка результата
        with open(output_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="✅ Готово! Качество лица улучшено.")
        bot.delete_message(message.chat.id, msg.message_id)
        
    except Exception as e:
        print(f"Ошибка обработки: {e}")
        bot.edit_message_text(f"❌ Ошибка: {e}", message.chat.id, msg.message_id)

if __name__ == "__main__":
    time.sleep(2) # Даем Flask запуститься
    connect_to_ai()
    print("--- Запуск бота ---")
    try:
        bot.remove_webhook()
        bot.polling(none_stop=True, skip_pending=True)
    except Exception as e:
        print(f"Ошибка при работе: {e}")
