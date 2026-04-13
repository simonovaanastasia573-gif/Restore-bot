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
def home(): return "Bober 3.3: Multiple Endpoints Fixed"
Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()

# --- 2. КЛЮЧИ ---
TG_TOKEN = os.environ.get('TG_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')

if not TG_TOKEN or not HF_TOKEN:
    print("❌ ОШИБКА: Проверь TG_TOKEN и HF_TOKEN в Render!", flush=True)
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

def get_restore_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("Мягко", callback_data="set_fid_0.9"),
        types.InlineKeyboardButton("Средне", callback_data="set_fid_0.7"),
        types.InlineKeyboardButton("Ультра", callback_data="set_fid_0.3")
    )
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
    return markup

# --- 4. CALLBACKS ---

@bot.message_handler(commands=['start', 'settings'])
def start_cmd(message):
    chat_id = message.chat.id
    user_data[chat_id] = user_data.get(chat_id, {"mode": "restore", "fid": 0.7})
    bot.send_message(chat_id, "Выбери режим:", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    user_data[chat_id] = user_data.get(chat_id, {"mode": "restore", "fid": 0.7})
    if call.data.startswith("set_mode_"):
        user_data[chat_id]["mode"] = call.data.replace("set_mode_", "")
        txt = "Выбран режим реставрации. Качество:" if user_data[chat_id]["mode"] == "restore" else f"Режим {user_data[chat_id]['mode']} активирован!"
        bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=get_restore_keyboard() if user_data[chat_id]["mode"] == "restore" else None)
    elif call.data.startswith("set_fid_"):
        user_data[chat_id]["fid"] = float(call.data.replace("set_fid_", ""))
        bot.edit_message_text("Настройки приняты. Присылай фото!", chat_id, call.message.message_id)
    elif call.data == "main_menu":
        bot.edit_message_text("Выбери режим:", chat_id, call.message.message_id, reply_markup=get_main_keyboard())

# --- 5. ОБРАБОТКА ФОТО ---

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    chat_id = message.chat.id
    settings = user_data.get(chat_id, {"mode": "restore", "fid": 0.7})
    msg = bot.reply_to(message, f"⏳ Магия {settings['mode']} в процессе...")
    
    input_path = f"in_{chat_id}.jpg"
    try:
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open(input_path, 'wb') as f: f.write(downloaded_file)
        
        with Image.open(input_path) as img:
            img = img.convert("RGB")
            img.thumbnail((1000, 1000))
            img.save(input_path, "JPEG", quality=90)

        client = Client(MODELS[settings['mode']], token=HF_TOKEN.strip())
        
        # --- ФИКС ЭНДПОИНТОВ ЧЕРЕЗ FN_INDEX ---
        if settings['mode'] == "restore":
            # CodeFormer: img, fidelity, bg_enhance, face_upsample, upscale
            job = client.submit(handle_file(input_path), settings['fid'], True, True, 2, fn_index=0)
        elif settings['mode'] == "bg_remove":
            job = client.submit(handle_file(input_path), fn_index=0)
        elif settings['mode'] == "color":
            job = client.submit(handle_file(input_path), fn_index=0)
        elif settings['mode'] == "anime":
            # AnimeGAN: img, version
            job = client.submit(handle_file(input_path), "version 2 (cherry blossoms)", fn_index=0)

        result = job.result(timeout=180)
        output_path = result if isinstance(result, str) else result[0]

        with open(output_path, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"✨ Режим {settings['mode']} успешно завершен!")
        bot.delete_message(chat_id, msg.message_id)

    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        bot.edit_message_text(f"❌ Ошибка в {settings['mode']}. Попробуй еще раз или смени режим.\n\nТех. данные: {str(e)[:100]}", chat_id, msg.message_id)
    finally:
        if os.path.exists(input_path): os.remove(input_path)

if __name__ == "__main__":
    print("--- Бобёр 3.3 запущен ---", flush=True)
    bot.remove_webhook()
    bot.polling(none_stop=True, skip_pending=True)
