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
def home(): return "Bober 3.9: Resilience Mode"
Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()

# --- 2. КОНФИГУРАЦИЯ ---
TG_TOKEN = os.environ.get('TG_TOKEN').strip()
HF_TOKEN = os.environ.get('HF_TOKEN').strip()
bot = telebot.TeleBot(TG_TOKEN)
user_data = {}

# Обновленные зеркала моделей (более стабильные)
MODELS = {
    "restore": "sczhou/CodeFormer", 
    "color": "piddnad/deoldify",
    "bg_remove": "briaai/RMBG-1.4",
    "anime": "akhaliq/AnimeGANv2" 
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
    bot.send_message(message.chat.id, "Бобёр снова в строю! 🦫 Выбери режим:", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    mode = call.data.replace("set_mode_", "")
    user_data[call.message.chat.id] = {"mode": mode}
    bot.edit_message_text(f"✅ Режим {mode} включен. Жду фото! (Если будет ошибка — просто пришли фото еще раз)", call.message.chat.id, call.message.message_id)

# --- 5. ОБРАБОТКА ФОТО ---
@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    chat_id = message.chat.id
    mode = user_data.get(chat_id, {"mode": "restore"})["mode"]
    
    msg = bot.reply_to(message, f"⏳ Подключаюсь к серверу {mode}... (это может занять до 1 минуты)")
    
    input_path = f"in_{chat_id}.jpg"
    try:
        # Скачивание
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open(input_path, 'wb') as f: f.write(downloaded_file)
        
        # Сжатие (облегчаем задачу серверу)
        with Image.open(input_path) as img:
            img = img.convert("RGB")
            img.thumbnail((800, 800)) # Уменьшили до 800px для мгновенной обработки
            img.save(input_path, "JPEG", quality=80)

        # Подключение к API
        client = Client(MODELS[mode], token=HF_TOKEN)
        
        # --- ИСПОЛЬЗУЕМ SUBMIT ДЛЯ ОЖИДАНИЯ В ОЧЕРЕДИ ---
        if mode == "restore":
            job = client.submit(handle_file(input_path), 0.7, True, True, 2, fn_index=0)
        elif mode == "anime":
            job = client.submit(handle_file(input_path), "version 2 (cherry blossoms)", fn_index=0)
        else:
            job = client.submit(handle_file(input_path), fn_index=0)

        # Ждем результат до 300 секунд (5 минут)
        result = job.result(timeout=300)
        output_path = result if isinstance(result, str) else result[0]

        with open(output_path, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"✨ Готово! Режим: {mode}")
        bot.delete_message(chat_id, msg.message_id)

    except Exception as e:
        err = str(e).lower()
        if "timeout" in err or "queue" in err:
            bot.edit_message_text("⌛️ Сервер ИИ очень занят или просыпается. Попробуй переотправить это же фото через 15 секунд.", chat_id, msg.message_id)
        else:
            bot.edit_message_text(f"❌ Ошибка: {str(e)[:100]}", chat_id, msg.message_id)
            
    finally:
        import os
        if os.path.exists(input_path): os.remove(input_path)

if __name__ == "__main__":
    bot.polling(none_stop=True, skip_pending=True)
