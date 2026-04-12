import telebot
from gradio_client import Client, handle_file
import os
from flask import Flask
from threading import Thread

# 1. ФИКС ПОРТА ДЛЯ RENDER
PORT = int(os.environ.get('PORT', 8080))

app = Flask('')
@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=PORT)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# 2. ТВОИ КЛЮЧИ (Исправил H на h)
TG_TOKEN = '8279520356:AAEpnBNi_COSffWE9BBQJuhwoNUY3LuCdJQ'
HF_TOKEN = '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'

bot = telebot.TeleBot(TG_TOKEN)

# 3. ПОДКЛЮЧЕНИЕ К НЕЙРОСЕТИ
client = None
try:
    print("Подключение к GFPGAN...")
    try:
        client = Client("TencentARC/GFPGAN", token=HF_TOKEN)
    except TypeError:
        client = Client("TencentARC/GFPGAN", hf_token=HF_TOKEN)
    print("✅ Нейросеть готова!")
except Exception as e:
    print(f"❌ Ошибка нейросети: {e}")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Я готов к работе! Присылай фото (лучше файлом).")

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    if client is None:
        bot.reply_to(message, "❌ Ошибка: Сервер нейросети временно недоступен.")
        return

    msg = bot.reply_to(message, "⏳ Начинаю реставрацию... Это займет около 40-60 секунд.")
    try:
        # Скачивание файла
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open("input.jpg", 'wb') as new_file:
            new_file.write(downloaded_file)
        
        # Обработка в GFPGAN
        result = client.predict(handle_file("input.jpg"), "v1.4", 2, api_name="/predict")
        output_path = result[0] if isinstance(result, (tuple, list)) else result
        
        # Отправка результата
        with open(output_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="✅ Готово! Качество улучшено.")
        bot.delete_message(message.chat.id, msg.message_id)
    except Exception as e:
        print(f"Ошибка: {e}")
        bot.edit_message_text(f"❌ Произошла ошибка. Попробуй другое фото.", message.chat.id, msg.message_id)

if __name__ == "__main__":
    keep_alive() # Держим сервер «живым»
    print("Бот запускается...")
    bot.polling(none_stop=True)
