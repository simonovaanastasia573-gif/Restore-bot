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
def home(): return "Bober 4.1: Auto-Retry Mode Active"
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
    "anime": "hysts/AnimeGANv2" 
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
    bot.send_message(message.chat.id, "Бобёр 4.1 в деле! 🦫\nТеперь я сам переподаю запросы, если сервер тормозит.", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    mode = call.data.replace("set_mode_", "")
    user_data[call.message.chat.id] = {"mode": mode}
    bot.edit_message_text(f"✅ Режим {mode} включен. Жду фото!", call.message.chat.id, call.message.message_id)

# --- 5. ФУНКЦИЯ ОБРАБОТКИ (С ПОВТОРАМИ) ---
def process_with_retry(mode, input_path, fid, chat_id):
    client = Client(MODELS[mode], token=HF_TOKEN)
    max_attempts = 3  # Пробуем 3 раза прежде чем сдаться
    
    for attempt in range(max_attempts):
        try:
            print(f"[{chat_id}] Попытка {attempt + 1} для {mode}...", flush=True)
            
            if mode == "restore":
                job = client.submit(handle_file(input_path), fid, True, True, 2, fn_index=0)
            elif mode == "anime":
                job = client.submit(handle_file(input_path), "v2", fn_index=0)
            else:
                job = client.submit(handle_file(input_path), fn_index=0)
            
            return job.result(timeout=250)
        except Exception as e:
            if attempt < max_attempts - 1:
                print(f"Попытка не удалась, жду 5 сек... Ошибка: {e}", flush=True)
                time.sleep(5)
            else:
                raise e

# --- 6. ОБРАБОТКА СООБЩЕНИЙ ---
@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    chat_id = message.chat.id
    mode = user_data.get(chat_id, {"mode": "restore"})["mode"]
    msg = bot.reply_to(message, f"⏳ Магия {mode}... (авто-повторы включены)")
    
    input_path = f"in_{chat_id}.jpg"
    try:
        # Скачивание и оптимизация
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open(input_path, 'wb') as f: f.write(downloaded_file)
        with Image.open(input_path) as img:
            img = img.convert("RGB")
            img.thumbnail((720, 720)) # Оптимальный размер для бесплатного ИИ
            img.save(input_path, "JPEG", quality=85)

        # Запуск обработки с ретритами
        result_path = process_with_retry(mode, input_path, 0.7, chat_id)
        output_path = result_path if isinstance(result_path, str) else result_path[0]

        with open(output_path, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"✨ Готово! Режим: {mode}")
        bot.delete_message(chat_id, msg.message_id)

    except Exception as e:
        print(f"Критическая ошибка: {e}", flush=True)
        bot.edit_message_text("❌ Сервер ИИ перегружен после 3 попыток. Попробуй другое фото или смени режим.", chat_id, msg.message_id)
            
    finally:
        import os
        if os.path.exists(input_path): os.remove(input_path)

if __name__ == "__main__":
    while True:
        try:
            bot.remove_webhook()
            bot.polling(none_stop=True, skip_pending=True, interval=0, timeout=60)
        except:
            time.sleep(5)
