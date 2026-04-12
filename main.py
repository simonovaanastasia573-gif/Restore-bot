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
    return "Бот на базе Microsoft & Tencent активен"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

# Запуск Flask сразу в фоне
Thread(target=run_flask, daemon=True).start()

# --- 2. ЗАГРУЗКА КЛЮЧЕЙ ИЗ СИСТЕМЫ RENDER ---
TG_TOKEN = os.environ.get('TG_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')

if not TG_TOKEN or not HF_TOKEN:
    print("❌ ОШИБКА: Переменные TG_TOKEN или HF_TOKEN не найдены в настройках Render!", flush=True)
    sys.exit(1)

bot = telebot.TeleBot(TG_TOKEN.strip())
client = None

# --- 3. ЛОГИКА ПОДКЛЮЧЕНИЯ К НЕЙРОСЕТЯМ ---
def connect_to_ai():
    global client
    # Список качественных моделей (Microsoft RestoreFormer и Tencent GFPGAN)
    spaces = [
        "cvp/RestoreFormer", 
        "TencentARC/GFPGAN"
    ]
    
    for space in spaces:
        try:
            print(f"Попытка подключения к {space}...", flush=True)
            client = Client(space, token=HF_TOKEN.strip())
            print(f"✅ Успешно! Работаем через {space}", flush=True)
            return True
        except Exception as e:
            print(f"❌ Модель {space} недоступна: {e}", flush=True)
    return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Бот обновлен! Использую технологии Microsoft и Tencent для чистой реставрации без глюков. Присылай фото! 📸")

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    global client
    if client is None:
        if not connect_to_ai():
            bot.reply_to(message, "❌ Нейросети сейчас перегружены. Попробуй через пару минут.")
            return

    msg = bot.reply_to(message, "⏳ Реставрация началась... Убираю шумы и восстанавливаю лицо.")
    
    try:
        # Скачивание файла
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_input = "input.jpg"
        with open(temp_input, 'wb') as f:
            f.write(downloaded_file)

        # Обработка через нейросеть
        print(f"Отправка в {client.src}...", flush=True)
        
        # Разные модели требуют разного количества аргументов
        if "RestoreFormer" in client.src:
            # Microsoft RestoreFormer обычно требует только само изображение
            result = client.predict(handle_file(temp_input))
        else:
            # Tencent GFPGAN требует (картинка, версия, увеличение)
            result = client.predict(handle_file(temp_input), "v1.4", 2)

        # Вытаскиваем путь к готовому файлу
        output_path = result if isinstance(result, str) else result[0]

        # Отправка пользователю
        with open(output_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption=f"✅ Готово! Обработано через {client.src.split('/')[-1]}")
        
        bot.delete_message(message.chat.id, msg.message_id)
        print("✅ Результат отправлен!", flush=True)

    except Exception as e:
        print(f"❌ Ошибка обработки: {e}", flush=True)
        bot.edit_message_text(f"❌ Ошибка нейросети: {e}. Попробуй другое фото.", message.chat.id, msg.message_id)

if __name__ == "__main__":
    time.sleep(3) # Пауза для инициализации порта
    connect_to_ai()
    
    print("--- Бот запускает polling ---", flush=True)
    try:
        bot.remove_webhook()
        bot.polling(none_stop=True, skip_pending=True)
    except Exception as e:
        print(f"Критическая ошибка: {e}", flush=True)
