import telebot
from gradio_client import Client, handle_file
import os
from flask import Flask
from threading import Thread

# 1. СИСТЕМА ПОДДЕРЖКИ ЖИЗНИ
PORT = int(os.environ.get('PORT', 8080))
app = Flask('')
@app.route('/')
def home(): return "Бот в сети"
def run(): app.run(host='0.0.0.0', port=PORT)
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# 2. КЛЮЧИ
TG_TOKEN = '8279520356:AAFtZme6M5sXsqYXp1Eh2lAoGsnAhbzX0Rs'
HF_TOKEN = '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'

bot = telebot.TeleBot(TG_TOKEN)

# 3. ПОДКЛЮЧЕНИЕ К НЕЙРОСЕТИ (С ПРОВЕРКОЙ)
client = None
spaces = [
    "https://huggingface.co/spaces/sczhou/CodeFormer",
    "https://huggingface.co/spaces/TencentARC/GFPGAN"
]

def connect_client():
    global client
    for space in spaces:
        try:
            print(f"Пробую подключиться к {space}...")
            client = Client(space, token=HF_TOKEN)
            print(f"✅ Успешно подключено к {space}!")
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения к {space}: {e}")
    return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Я в сети! Готов восстанавливать фото. Присылай файл! 📸")

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    global client
    if client is None:
        if not connect_client():
            bot.reply_to(message, "❌ Все нейросети сейчас заняты или недоступны. Попробуй позже.")
            return

    msg = bot.reply_to(message, "⏳ Магия реставрации началась... (около 40 сек)")
    try:
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open("input.jpg", 'wb') as new_file:
            new_file.write(downloaded_file)
        
        # Запускаем обработку
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
        print(f"Ошибка при обработке: {e}")
        bot.edit_message_text(f"❌ Ошибка нейросети. Попробуй другое фото или повтори позже.", message.chat.id, msg.message_id)

if __name__ == "__main__":
    keep_alive()
    connect_client() # Пытаемся подключиться при запуске
    print("Бот запущен!")
    bot.polling(none_stop=True)
if __name__ == "__main__":
    try:
        # 1. Запуск веб-сервера для Render
        keep_alive() 
        
        # 2. Очистка старых соединений (очень важно после смены токена!)
        print("Очистка старых сессий Telegram...")
        bot.remove_webhook()
        
        # 3. Подключение к нейросети
        print("Подключение к нейросети...")
        connect_client()
        
        print("✅ БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ!")
        
        # 4. Запуск прослушивания сообщений
        # skip_pending=True заставит бота игнорировать старые сообщения, присланные во время простоя
        bot.polling(none_stop=True, skip_pending=True, timeout=60)
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА ПРИ ЗАПУСКЕ: {e}")
