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
def home(): return "Bober 4.10: Safe Params Active"
Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()

# --- 2. КОНФИГУРАЦИЯ ---
TG_TOKEN = os.environ.get('TG_TOKEN').strip()
HF_TOKEN = os.environ.get('HF_TOKEN').strip()
bot = telebot.TeleBot(TG_TOKEN)
user_data = {}

# --- РАБОЧИЕ АДРЕСА ---
MODELS = {
    "restore": "sczhou/CodeFormer",
    "cartoon": "akhaliq/AnimeGANv2",         
    "bg_remove": "briaai/BRIA-RMBG-1.4"      
}

# --- 3. ФУНКЦИЯ-ХАТИКО ---
def get_ai_client_with_wait(mode, bot, chat_id, msg_id):
    for attempt in range(1, 9): 
        try:
            return Client(MODELS[mode], token=HF_TOKEN)
        except Exception as e:
            error_str = str(e)
            if "404" in error_str or "Not Found" in error_str:
                bot.edit_message_text(f"❌ Критическая ошибка: Адрес {MODELS[mode]} не существует!", chat_id, msg_id)
                return None
                
            if attempt < 8:
                try:
                    bot.edit_message_text(f"☕️ Сервер {mode} просыпается ({attempt}/8). Ждем 10 сек...", chat_id, msg_id)
                except: pass
                time.sleep(10)
            else:
                bot.edit_message_text(f"❌ Сервер {mode} не ответил за 80 секунд.", chat_id, msg_id)
                return None

# --- 4. КЛАВИАТУРА ---
def get_main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛠 Реставрация", callback_data="set_mode_restore"),
        types.InlineKeyboardButton("🧸 3D Мультик", callback_data="set_mode_cartoon"),
        types.InlineKeyboardButton("🖼 Удалить фон", callback_data="set_mode_bg_remove")
    )
    return markup

@bot.message_handler(commands=['start', 'settings'])
def start(message):
    user_data[message.chat.id] = {"mode": "restore"}
    bot.send_message(message.chat.id, "Бобёр 4.10 на связи! 🦫\nПараметры безопасности выкручены на максимум.", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    mode = call.data.replace("set_mode_", "")
    user_data[call.message.chat.id] = {"mode": mode}
    bot.edit_message_text(f"✅ Режим {mode} активен. Жду твое фото!", call.message.chat.id, call.message.message_id)

# --- 5. ОБРАБОТКА ФОТО ---
@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    chat_id = message.chat.id
    mode = user_data.get(chat_id, {"mode": "restore"})["mode"]
    
    status_msg = bot.reply_to(message, f"📡 Подключаюсь к {mode}...")
    client = get_ai_client_with_wait(mode, bot, chat_id, status_msg.message_id)
    
    if not client:
        return

    bot.edit_message_text(f"⏳ Сервер готов! Рисую {mode}...", chat_id, status_msg.message_id)
    
    input_path = f"in_{chat_id}.jpg"
    try:
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open(input_path, 'wb') as f: f.write(downloaded_file)
        
        with Image.open(input_path) as img:
            img = img.convert("RGB")
            img.thumbnail((800, 800))
            img.save(input_path, "JPEG", quality=85)

        # --- САМОЕ ВАЖНОЕ: БЕЗОПАСНЫЕ ПАРАМЕТРЫ ---
        if mode == "cartoon":
            # Используем самый базовый параметр "version 2", чтобы сервер не подавился названием
            result = client.predict(handle_file(input_path), "version 2", fn_index=0)
        elif mode == "restore":
            result = client.predict(handle_file(input_path), 0.7, True, True, 2, fn_index=0)
        elif mode == "bg_remove":
            # Для фона никаких дополнительных параметров не шлем
            result = client.predict(handle_file(input_path), fn_index=0)

        output_path = result if isinstance(result, str) else result[0]

        with open(output_path, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"✨ Готово!")
        bot.delete_message(chat_id, status_msg.message_id)

    except Exception as e:
        error_text = str(e)[:300]
        print(f"Ошибка: {error_text}", flush=True)
        bot.edit_message_text(f"❌ Опять капризы сервера Hugging Face. Попробуй ещё разок!\n\n`{error_text}`", chat_id, status_msg.message_id, parse_mode="Markdown")
            
    finally:
        if os.path.exists(input_path): os.remove(input_path)

if __name__ == "__main__":
    bot.polling(none_stop=True, skip_pending=True)
