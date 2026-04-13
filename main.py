import telebot
from telebot import types
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
def home(): return "Bober 3.8 is Alive"
Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()

# --- 2. КЛЮЧИ ---
TG_TOKEN = os.environ.get('TG_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')
bot = telebot.TeleBot(TG_TOKEN.strip())
user_data = {}

# Список моделей (Аниме заменен на супер-стабильный hysts)
MODELS = {
    "restore": "sczhou/CodeFormer",
    "color": "piddnad/deoldify",
    "bg_remove": "briaai/RMBG-1.4",
    "anime": "hysts/AnimeGANv2" 
}

# --- 3. ИНТЕРФЕЙС ---
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
@bot.message_handler(commands=['start', 'settings'])
def start_cmd(message):
    chat_id = message.chat.id
    user_data[chat_id] = user_data.get(chat_id, {"mode": "restore", "fid": 0.7})
    bot.send_message(chat_id, "Бобёр на связи! 🦫 Выбери режим:", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    if call.data.startswith("set_mode_"):
        user_data[chat_id] = {"mode": call.data.replace("set_mode_", ""), "fid": 0.7}
        bot.edit_message_text(f"✅ Режим {user_data[chat_id]['mode']} включен. Шли фото!", chat_id, call.message.message_id)

# --- 5. ОБРАБОТКА ФОТО ---
@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    chat_id = message.chat.id
    settings = user_data.get(chat_id, {"mode": "restore", "fid": 0.7})
    msg = bot.reply_to(message, f"⏳ {settings['mode']} в процессе... Обычно это занимает 20-40 сек.")
    
    input_path = f"in_{chat_id}.jpg"
    try:
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open(input_path, 'wb') as f: f.write(downloaded_file)
        
        with Image.open(input_path) as img:
            img = img.convert("RGB")
            img.thumbnail((1000, 1000))
            img.save(input_path, "JPEG", quality=85)

        client = Client(MODELS[settings['mode']], token=HF_TOKEN.strip())
        
        # --- СПЕЦИФИЧНЫЕ НАСТРОЙКИ ДЛЯ КАЖДОЙ МОДЕЛИ ---
        if settings['mode'] == "restore":
            result = client.predict(handle_file(input_path), settings['fid'], True, True, 2, fn_index=0)
        elif settings['mode'] == "anime":
            # hysts/AnimeGANv2 требует фото и версию стиля ("v2" — самая крутая)
            result = client.predict(handle_file(input_path), "v2", fn_index=0)
        else:
            result = client.predict(handle_file(input_path), fn_index=0)

        output_path = result if isinstance(result, str) else result[0]
        with open(output_path, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"✨ Режим {settings['mode']} готов!")
        bot.delete_message(chat_id, msg.message_id)

    except Exception as e:
        print(f"Ошибка: {e}", flush=True)
        # Если ошибка — даем пользователю шанс нажать еще раз
        bot.edit_message_text(f"❌ Сервер Hugging Face притормаживает. Попробуй отправить это же фото еще раз прямо сейчас!", chat_id, msg.message_id)
            
    finally:
        if os.path.exists(input_path): os.remove(input_path)

if __name__ == "__main__":
    print("--- Бобёр 3.8 запущен ---", flush=True)
    while True:
        try:
            bot.remove_webhook()
            bot.polling(none_stop=True, skip_pending=True, interval=0, timeout=40)
        except:
            time.sleep(5)
