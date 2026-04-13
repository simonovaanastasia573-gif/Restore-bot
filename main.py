import telebot
from telebot import types
from gradio_client import Client, handle_file
import os
from flask import Flask
from threading import Thread
import time
from PIL import Image

# --- 1. ВЕБ-СЕРВЕР ---
PORT = int(os.environ.get('PORT', 10000))
app = Flask('')
@app.route('/')
def home(): return "Bober 4.0 is Live"
Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()

# --- 2. КОНФИГУРАЦИЯ ---
TG_TOKEN = os.environ.get('TG_TOKEN').strip()
HF_TOKEN = os.environ.get('HF_TOKEN').strip()
bot = telebot.TeleBot(TG_TOKEN)
user_data = {}

MODELS = {
    "restore": "sczhou/CodeFormer", 
    "color": "piddnad/deoldify",
    "bg_remove": "briaai/RMBG-1.4",
    "anime": "hysts/AnimeGANv2" # Самое стабильное зеркало
}

# --- 3. КЛАВИАТУРА ---
def get_main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛠 Реставрация", callback_data="set_mode_restore"),
        types.InlineKeyboardButton("🎨 Раскрасить", callback_data="set_mode_color"),
        types.InlineKeyboardButton("🖼 Удалить фон", callback_data="set_mode_bg_remove"),
        types.InlineKeyboardButton("⛩ Аниме-стиль", callback_data="set_mode_anime")
    )
    return markup

# --- 4. CALLBACKS ---
@bot.message_handler(commands=['start'])
def start(message):
    user_data[message.chat.id] = {"mode": "restore"}
    bot.send_message(message.chat.id, "Бобёр 4.0 готов! 🦫 Выбери режим:", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    mode = call.data.replace("set_mode_", "")
    user_data[call.message.chat.id] = {"mode": mode}
    bot.edit_message_text(f"✅ Режим {mode} включен. Жду твое фото!", call.message.chat.id, call.message.message_id)

# --- 5. ОБРАБОТКА ФОТО ---
@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    chat_id = message.chat.id
    mode = user_data.get(chat_id, {"mode": "restore"})["mode"]
    
    msg = bot.reply_to(message, f"⏳ Работаю над стилем {mode}... (30-60 сек)")
    
    input_path = f"in_{chat_id}.jpg"
    try:
        # 1. Скачивание
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # 2. ПОДГОТОВКА ФОТО (Критически важно!)
        with open(input_path, 'wb') as f: f.write(downloaded_file)
        with Image.open(input_path) as img:
            # Превращаем в чистый RGB (убирает ошибки прозрачности)
            img = img.convert("RGB")
            # 800px — гарантия того, что сервер не упадет от нехватки памяти
            img.thumbnail((800, 800)) 
            img.save(input_path, "JPEG", quality=85)

        # 3. ПОДКЛЮЧЕНИЕ К API
        client = Client(MODELS[mode], token=HF_TOKEN)
        
        # --- ВЫЗОВ МОДЕЛЕЙ ---
        if mode == "restore":
            job = client.submit(handle_file(input_path), 0.7, True, True, 2, fn_index=0)
        elif mode == "anime":
            # hysts/AnimeGANv2 требует фото и выбор версии (v1, v2, FacePaint)
            # "v2" — самый сочный аниме-режим
            job = client.submit(handle_file(input_path), "v2", fn_index=0)
        else:
            job = client.submit(handle_file(input_path), fn_index=0)

        # Ждем результат
        result = job.result(timeout=250)
        output_path = result if isinstance(result, str) else result[0]

        with open(output_path, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"✨ Режим {mode} завершен!")
        bot.delete_message(chat_id, msg.message_id)

    except Exception as e:
        print(f"Ошибка: {e}", flush=True)
        bot.edit_message_text("⌛️ Сервер ИИ временно капризничает. Попробуй переотправить фото — обычно со 2-го раза всё срабатывает!", chat_id, msg.message_id)
            
    finally:
        if os.path.exists(input_path): os.remove(input_path)

# --- 6. БЕЗУМНЫЙ ПОЛЛИНГ ---
if __name__ == "__main__":
    print("--- Бобёр 4.0 запущен ---", flush=True)
    while True:
        try:
            bot.remove_webhook()
            bot.polling(none_stop=True, skip_pending=True, interval=0, timeout=60)
        except Exception as e:
            time.sleep(5)
