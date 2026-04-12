import telebot
from gradio_client import Client, handle_file
import os
from flask import Flask
from threading import Thread

# --- БЛОК ПОДДЕРЖКИ ЖИЗНИ (WEB SERVER) ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
# ----------------------------------------

# Твои ключи
TG_TOKEN = '8279520356:AAEpnBNi_COSffWE9BBQJuhwoNUY3LuCdJQ'
HF_TOKEN = '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' # Я подставил твой рабочий токен

bot = telebot.TeleBot(TG_TOKEN)
client = Client("TencentARC/GFPGAN", token=HF_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Бот переехал на Render и готов к работе! Присылай фото.")

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    msg = bot.reply_to(message, "⏳ Обработка на мощностях Render... Подожди немного.")
    try:
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open("input.jpg", 'wb') as new_file:
            new_file.write(downloaded_file)
        
        result = client.predict(handle_file("input.jpg"), "v1.4", 2, api_name="/predict")
        output_path = result[0] if isinstance(result, (tuple, list)) else result
        
        with open(output_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="✅ Реставрация завершена!")
        bot.delete_message(message.chat.id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: {e}", message.chat.id, msg.message_id)

if __name__ == "__main__":
    keep_alive() # Запускаем веб-сервер
    print("Бот запущен!")
    bot.polling(none_stop=True)
