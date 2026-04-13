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
def home(): return "Bober 3.4 API Fix Active"
Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()

# --- 2. КЛЮЧИ ---
TG_TOKEN = os.environ.get('TG_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')

if not TG_TOKEN or not HF_TOKEN:
    print("❌ ОШИБКА: Токены не найдены!", flush=True)
    sys.exit(1)

bot = telebot.TeleBot(TG_TOKEN.strip())
user_data = {}

MODELS = {
    "restore": "sczhou/CodeFormer",
    "color": "piddnad/deoldify",
    "bg_remove": "briaai/RMBG-1.4",
    "anime": "akhaliq/AnimeGANv2"
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
    bot.send_message(chat_id, "Выбери магию ИИ:", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    user_data[chat_id] = user_data.get(chat_id, {"mode": "restore", "fid": 0.7})
    if call.data.startswith("set_mode_"):
        user_data[chat_id]["mode"] = call.data.replace("set_mode_", "")
        bot.edit_message_text(f"Режим {user_data[chat_id]['mode']} активирован! Жду фото. 📸", chat_id, call.message.message_id)
    elif call.data == "main_menu":
        bot.edit_message_text("Выбери магию ИИ:", chat_id, call.message.message_id, reply_markup=get_main_keyboard())

# --- 5. ОБРАБОТКА ФОТО ---

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    chat_id = message.chat.id
    settings = user_data.get(chat_id, {"mode": "restore", "fid": 0.7})
    msg = bot.reply_to(message, f"⏳ Запускаю ИИ ({settings['mode']})...")
    
    # Создаем уникальное имя для файла, чтобы избежать конфликтов
    input_path = f"in_{chat_id}_{int(time.time())}.jpg"
    
    try:
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open(input_path, 'wb') as f: f.write(downloaded_file)
        
        # Сжатие для стабильности
        with Image.open(input_path) as img:
            img = img.convert("RGB")
            img.thumbnail((1200, 1200))
            img.save(input_path, "JPEG", quality=90)

        client = Client(MODELS[settings['mode']], token=HF_TOKEN.strip())
        
        # --- ФИКС: ЯВНОЕ УКАЗАНИЕ API_NAME ДЛЯ КАЖДОЙ МОДЕЛИ ---
        print(f"Отправка в {settings['mode']} через api_name...", flush=True)
        
        if settings['mode'] == "restore":
            job = client.submit(handle_file(input_path), settings['fid'], True, True, 2, api_name="/predict")
        elif settings['mode'] == "bg_remove":
            job = client.submit(handle_file(input_path), api_name="/predict")
        elif settings['mode'] == "color":
            job = client.submit(handle_file(input_path), api_name="/predict")
        elif settings['mode'] == "anime":
            # У аниме модели часто api_name может быть другим, пробуем универсальный /predict
            job = client.submit(handle_file(input_path), "version 2 (cherry blossoms)", api_name="/predict")

        result = job.result(timeout=240)
        output_path = result if isinstance(result, str) else result[0]

        with open(output_path, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"✨ Готово в режиме {settings['mode']}!")
        bot.delete_message(chat_id, msg.message_id)

    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        # Если /predict не сработал, пробуем последний шанс без api_name, но с fn_index
        try:
            print("Пробую запасной метод через fn_index...", flush=True)
            client = Client(MODELS[settings['mode']], token=HF_TOKEN.strip())
            if settings['mode'] == "anime":
                res = client.predict(handle_file(input_path), "version 2 (cherry blossoms)", fn_index=0)
            else:
                res = client.predict(handle_file(input_path), fn_index=0)
            
            out = res if isinstance(res, str) else res[0]
            with open(out, 'rb') as f:
                bot.send_document(chat_id, f, caption="✨ Готово (через запасной метод)!")
            bot.delete_message(chat_id, msg.message_id)
        except:
            bot.edit_message_text(f"❌ Ошибка нейросети: {str(e)[:100]}", chat_id, msg.message_id)
            
    finally:
        if os.path.exists(input_path): os.remove(input_path)

if __name__ == "__main__":
    print("--- Бобёр 3.4 запущен ---", flush=True)
    bot.remove_webhook()
    bot.polling(none_stop=True, skip_pending=True)
