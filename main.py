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
def home(): return "Bober 4.2: High Performance Active"
Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()

# --- 2. КОНФИГУРАЦИЯ ---
TG_TOKEN = os.environ.get('TG_TOKEN').strip()
HF_TOKEN = os.environ.get('HF_TOKEN').strip()
bot = telebot.TeleBot(TG_TOKEN)

# Инициализируем клиентов ОДИН РАЗ при старте
print("🚀 Прогрев нейросетей...", flush=True)
AI_CLIENTS = {
    "restore": Client("sczhou/CodeFormer", token=HF_TOKEN),
    "anime": Client("piddnad/animegan2-pytorch", token=HF_TOKEN), # Сменили на более легкую
    "bg_remove": Client("briaai/RMBG-1.4", token=HF_TOKEN)
}
print("✅ Нейросети готовы к труду!", flush=True)

user_data = {}

# --- 3. КЛАВИАТУРА ---
def get_main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛠 Реставрация", callback_data="set_mode_restore"),
        types.InlineKeyboardButton("⛩ Аниме-стиль", callback_data="set_mode_anime"),
        types.InlineKeyboardButton("🖼 Удалить фон", callback_data="set_mode_bg_remove")
    )
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    user_data[message.chat.id] = {"mode": "restore"}
    bot.send_message(message.chat.id, "Бобёр 4.2: Теперь в 2 раза быстрее! 🦫", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    mode = call.data.replace("set_mode_", "")
    user_data[call.message.chat.id] = {"mode": mode}
    bot.edit_message_text(f"✅ Режим {mode} активен. Шли фото!", call.message.chat.id, call.message.message_id)

# --- 4. ЯДРО ОБРАБОТКИ ---
def smart_process(mode, path, chat_id):
    # Пытаемся обработать с нарастающей паузой
    delays = [2, 7, 15] 
    for attempt, delay in enumerate(delays):
        try:
            client = AI_CLIENTS[mode]
            if mode == "restore":
                return client.predict(handle_file(path), 0.7, True, True, 2, fn_index=0)
            elif mode == "anime":
                # У этой модели другой набор параметров: [фото, стиль]
                return client.predict(handle_file(path), "FacePaint v1", fn_index=0)
            else:
                return client.predict(handle_file(path), fn_index=0)
        except Exception as e:
            if attempt < len(delays) - 1:
                print(f"⚠️ Сбой (попытка {attempt+1}), жду {delay} сек...", flush=True)
                time.sleep(delay)
            else:
                raise e

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    chat_id = message.chat.id
    mode = user_data.get(chat_id, {"mode": "restore"})["mode"]
    msg = bot.reply_to(message, f"⏳ Работаю в режиме {mode}...")
    
    input_path = f"in_{chat_id}.jpg"
    try:
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open(input_path, 'wb') as f: f.write(downloaded_file)
        with Image.open(input_path) as img:
            img = img.convert("RGB")
            img.thumbnail((720, 720)) # Золотой стандарт для скорости
            img.save(input_path, "JPEG", quality=85)

        result = smart_process(mode, input_path, chat_id)
        output_path = result if isinstance(result, str) else result[0]

        with open(output_path, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"✨ Готово!")
        bot.delete_message(chat_id, msg.message_id)

    except Exception as e:
        bot.edit_message_text("❌ Сервер ИИ очень занят. Попробуй другое фото или режим 'Реставрация' (он стабильнее).", chat_id, msg.message_id)
            
    finally:
        if os.path.exists(input_path): os.remove(input_path)

if __name__ == "__main__":
    bot.polling(none_stop=True, skip_pending=True)
