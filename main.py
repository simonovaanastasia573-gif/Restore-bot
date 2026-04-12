import telebot
from gradio_client import Client, handle_file
import os
from flask import Flask
from threading import Thread
import time

# --- БЛОК ЖИЗНИ ДЛЯ RENDER ---
PORT = int(os.environ.get('PORT', 8080))
app = Flask('')

@app.route('/')
def home():
    return "Bot is active"

def run_flask():
    try:
        app.run(host='0.0.0.0', port=PORT)
    except Exception as e:
        print(f"Flask error: {e}")

thread = Thread(target=run_flask)
thread.daemon = True
thread.start()

# --- ТВОИ ДАННЫЕ (УЖЕ БЕЗ ПРОБЕЛОВ) ---
TG_TOKEN = '8279520356:AAFtZme6M5sXsqYXp1Eh2lAoGsnAhbzX0Rs'
HF_TOKEN = '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'

# Инициализация с защитой .strip() - она обрежет любые невидимые пробелы
bot = telebot.TeleBot(TG_TOKEN.strip())
client = None

def connect_to_ai():
    global client
    models = ["sczhou/CodeFormer", "TencentARC/GFPGAN"]
    for model_name in models:
        try:
            print(f"Подключение к {model_name}...")
            client = Client(model_name, token=HF_TOKEN.strip())
            print(f"✅ Подключено к {model_name}")
            return True
        except Exception as e:
            print(f"❌ Пропуск {model_name}: {e}")
    return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Я в сети! Присылай фото, и я восстановлю лицо. 📸")

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    if client is None:
        if not connect_to_ai():
            bot.reply_to(message, "❌ Нейросети сейчас заняты. Попробуй через минуту.")
            return

    msg = bot.reply_to(message, "⏳ Магия началась... Жду ответа от нейросети.")
    try:
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open("input.jpg", 'wb') as new_file:
            new_file.write(downloaded_file)
        
        result = client.predict(
            image=handle_file("input.jpg"),
            codeformer_fidelity=0.5,
            upscale=2,
            api_name="/predict"
        )
        
        output_path = result if isinstance(result, str) else result[0]
        
        with open(output_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="✅ Готово! Текстуры восстановлены.")
        bot.delete_message(message.chat.id, msg.message_id)
        
    except Exception as e:
        print(f"Ошибка: {e}")
        bot.edit_message_text(f"❌ Ошибка: {e}", message.chat.id, msg.message_id)

if __name__ == "__main__":
    time.sleep(2) # Даем Render время подцепить порт
    connect_to_ai()
    print("--- Бот запускает polling ---")
    try:
        bot.remove_webhook()
        bot.polling(none_stop=True, skip_pending=True)
    except Exception as e:
        print(f"Ошибка запуска: {e}")
