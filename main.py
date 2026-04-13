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
def home(): return "Multi-AI Bober is Active"
Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()

# --- 2. КЛЮЧИ ---
TG_TOKEN = os.environ.get('TG_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')

if not TG_TOKEN or not HF_TOKEN:
    print("❌ ОШИБКА: Проверь переменные!", flush=True)
    sys.exit(1)

bot = telebot.TeleBot(TG_TOKEN.strip())
user_data = {}

# Константы моделей
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

# --- 4. ОБРАБОТКА CALLBACK ---

@bot.message_handler(commands=['start', 'settings'])
def start_cmd(message):
    chat_id = message.chat.id
    user_data[chat_id] = user_data.get(chat_id, {"mode": "restore", "fid": 0.7})
    bot.send_message(chat_id, "Выбери режим работы ИИ:", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    user_data[chat_id] = user_data.get(chat_id, {"mode": "restore", "fid": 0.7})

    if call.data.startswith("set_mode_"):
        mode = call.data.replace("set_mode_", "")
        user_data[chat_id]["mode"] = mode
        if mode == "restore":
            bot.edit_message_text("Выбрана реставрация. Интенсивность:", chat_id, call.message.message_id, reply_markup=get_restore_keyboard())
        else:
            bot.edit_message_text(f"Режим {mode} активирован! Жду фото. 📸", chat_id, call.message.message_id)
    
    elif call.data.startswith("set_fid_"):
        user_data[chat_id]["fid"] = float(call.data.replace("set_fid_", ""))
        bot.edit_message_text(f"Готово! Присылай фото для реставрации. 📸", chat_id, call.message.message_id)
    
    elif call.data == "main_menu":
        bot.edit_message_text("Выбери режим работы ИИ:", chat_id, call.message.message_id, reply_markup=get_main_keyboard())

# --- 5. ОБРАБОТКА ФОТО ---

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    chat_id = message.chat.id
    settings = user_data.get(chat_id, {"mode": "restore", "fid": 0.7})
    msg = bot.reply_to(message, f"⏳ Магия ИИ ({settings['mode']}) началась...")
    
    input_path = f"in_{chat_id}.jpg"
    try:
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open(input_path, 'wb') as f: f.write(downloaded_file)
        
        with Image.open(input_path) as img:
            img = img.convert("RGB")
            img.thumbnail((1200, 1200))
            img.save(input_path, "JPEG", quality=90)

        # Подключаемся к модели
        client = Client(MODELS[settings['mode']], token=HF_TOKEN.strip())
        
        # ВЕЗДЕ добавляем api_name="/predict", чтобы не было путаницы
        if settings['mode'] == "restore":
            job = client.submit(handle_file(input_path), settings['fid'], True, True, 2, api_name="/predict")
        elif settings['mode'] == "bg_remove":
            job = client.submit(handle_file(input_path), api_name="/predict")
        elif settings['mode'] == "color":
            job = client.submit(handle_file(input_path), api_name="/predict")
        elif settings['mode'] == "anime":
            # Тут api_name был КРИТИЧЕСКИ важен
            job = client.submit(handle_file(input_path), "version 2 (cherry blossoms)", api_name="/predict")

        result = job.result(timeout=200)
        output_path = result if isinstance(result, str) else result[0]

        with open(output_path, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"✅ Режим {settings['mode']} выполнен!")
        
        bot.delete_message(chat_id, msg.message_id)

    except Exception as e:
        print(f"Error: {e}", flush=True)
        bot.edit_message_text(f"❌ Ошибка: {e}\nПопробуй еще раз или смени режим.", chat_id, msg.message_id)
    
    finally:
        if os.path.exists(input_path): os.remove(input_path)

if __name__ == "__main__":
    print("--- Бобёр 3.1 запущен ---", flush=True)
    bot.remove_webhook()
    bot.polling(none_stop=True)
