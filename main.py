import telebot
from telebot import types
from gradio_client import Client, handle_file
import os
from flask import Flask
from threading import Thread
import time
import sys
from PIL import Image

# --- 1. ВЕБ-СЕРВЕР ДЛЯ RENDER ---
PORT = int(os.environ.get('PORT', 10000))
app = Flask('')
@app.route('/')
def home(): return "Bober 3.7: Ultimate Stability Active"

# Запуск Flask в фоне
def run_flask():
    try:
        app.run(host='0.0.0.0', port=PORT)
    except Exception as e:
        print(f"Ошибка Flask: {e}", flush=True)

Thread(target=run_flask, daemon=True).start()

# --- 2. КЛЮЧИ ---
TG_TOKEN = os.environ.get('TG_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')

if not TG_TOKEN or not HF_TOKEN:
    print("❌ ОШИБКА: Токены не найдены в настройках Render!", flush=True)
    # Не выходим через sys.exit, чтобы Render не считал это мгновенным крашем
    time.sleep(3600) 

bot = telebot.TeleBot(TG_TOKEN.strip())
user_data = {}

MODELS = {
    "restore": "sczhou/CodeFormer",
    "color": "piddnad/deoldify",
    "bg_remove": "briaai/RMBG-1.4",
    "anime": "TencentARC/AnimeGANv2"
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
    bot.send_message(chat_id, "Бот готов к работе! Выбери режим: 🦫", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    user_data[chat_id] = user_data.get(chat_id, {"mode": "restore", "fid": 0.7})
    if call.data.startswith("set_mode_"):
        user_data[chat_id]["mode"] = call.data.replace("set_mode_", "")
        bot.answer_callback_query(call.id, f"Включен режим {user_data[chat_id]['mode']}")
        bot.edit_message_text(f"✅ Режим {user_data[chat_id]['mode']} активен. Присылай фото!", chat_id, call.message.message_id)

# --- 5. ОБРАБОТКА ФОТО ---
@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    chat_id = message.chat.id
    settings = user_data.get(chat_id, {"mode": "restore", "fid": 0.7})
    msg = bot.reply_to(message, f"⏳ Нейросеть {settings['mode']} начала работу...")
    
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
        
        if settings['mode'] == "restore":
            job = client.submit(handle_file(input_path), settings['fid'], True, True, 2, fn_index=0)
        elif settings['mode'] == "anime":
            job = client.submit(handle_file(input_path), "v2", fn_index=0)
        else:
            job = client.submit(handle_file(input_path), fn_index=0)

        result = job.result(timeout=200)
        output_path = result if isinstance(result, str) else result[0]

        with open(output_path, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"✨ Режим {settings['mode']} готов!")
        bot.delete_message(chat_id, msg.message_id)

    except Exception as e:
        print(f"Ошибка ИИ: {e}", flush=True)
        bot.edit_message_text(f"❌ Ошибка: Сервер нейросети занят. Попробуй еще раз через 10 секунд.", chat_id, msg.message_id)
            
    finally:
        if os.path.exists(input_path): os.remove(input_path)

# --- 6. БЕСКОНЕЧНЫЙ ЗАПУСК ---
if __name__ == "__main__":
    print("--- Бобёр 3.7 запущен ---", flush=True)
    while True:
        try:
            bot.remove_webhook()
            # Бесконечный цикл опроса Телеграма
            bot.polling(none_stop=True, skip_pending=True, interval=0, timeout=40)
        except Exception as e:
            print(f"Ошибка Polling: {e}. Перезапуск через 5 секунд...", flush=True)
            time.sleep(5)
