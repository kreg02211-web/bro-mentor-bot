import os
import json
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from groq import Groq

# Заглушка порта для Render
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def log_message(self, format, *args):
        pass

def run_server():
    server = HTTPServer(("0.0.0.0", 10000), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

TOKEN = os.environ.get("TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

bot = Bot(token=TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)

MAX_HISTORY = 12
DB_FILE = "chat_memory.json"

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🌐 Язык"), KeyboardButton(text="🧹 Сброс")],
        [KeyboardButton(text="⚡ Инфо")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Напиши бро или выбери кнопку...",
)

LANG_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
        ]
    ]
)

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"❌ Ошибка чтения файла памяти: {e}")
            return {}
    return {}

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Ошибка записи файла памяти: {e}")

def get_user_record(user_id):
    db = load_db()
    user_str = str(user_id)
    raw = db.get(user_str)

    if isinstance(raw, list):
        clean = [
            msg for msg in raw
            if isinstance(msg, dict) and msg.get("role") in ["user", "assistant"]
        ]
        return {"lang": "ru", "history": clean}

    if isinstance(raw, dict):
        lang = raw.get("lang", "ru")
        if lang not in ["ru", "en"]:
            lang = "ru"
        hist = raw.get("history", [])
        clean = [
            msg for msg in hist
            if isinstance(msg, dict) and msg.get("role") in ["user", "assistant"]
        ]
        return {"lang": lang, "history": clean}

    return {"lang": "ru", "history": []}

def get_history(user_id):
    rec = get_user_record(user_id)
    print(f"✅ Память загружена для {user_id}: сообщений -> {len(rec['history'])}, язык -> {rec['lang']}")
    return rec["history"]

def save_history(user_id, history):
    db = load_db()
    user_str = str(user_id)
    current = get_user_record(user_id)
    clean = [
        msg for msg in history
        if isinstance(msg, dict) and msg.get("role") in ["user", "assistant"]
    ]
    db[user_str] = {
        "lang": current["lang"],
        "history": clean,
    }
    save_db(db)
    print(f"💾 Память сохранена для {user_id}: всего сообщений -> {len(clean)}")

def get_user_lang(user_id):
    return get_user_record(user_id)["lang"]

def set_user_lang(user_id, lang):
    if lang not in ["ru", "en"]:
        lang = "ru"
    db = load_db()
    user_str = str(user_id)
    current = get_user_record(user_id)
    db[user_str] = {
        "lang": lang,
        "history": current["history"],
    }
    save_db(db)
    print(f"🌐 Язык для {user_id} изменён на: {lang}")
    PROMPTS = {
    "en": "You are Gauter, an older bro and real mentor. Keep it raw, grounded, and natural — no cringey roleplay or stiff AI tone. Write thorough, punchy, conversational replies like two real guys talking shop, training, mindset, and life. Always break long replies into 3-4 clean paragraphs so it reads easily. Use relevant emojis naturally where they fit (fire, weights, skulls, rockets), and avoid markdown bullet lists, headers, or asterisks. Always reply strictly in English.",
    "ru": "Ты — Гаутер, старший кореш и бро. Живой пацан, без шизы, ботов и ролевых игр. ОБЩЕНИЕ КАК НАДО: Пиши максимально развернуто, объемно и сочно, в стиле живого разговора двух реальных корешей. ОБЯЗАТЕЛЬНО разделяй текст на 3-4 аккуратных абзаца, чтобы он легко читался и детально разбирал все темы. Насыпай к месту много живых эмодзи (огонь, дым, черепа, бро, ракеты), чтобы они заменяли стикеры и создавали движ. Никаких сухих отписок, списков, лекций, звездочек и решеток. Разбирай темы подробно, рассуждай, спорь и поддерживай по-братски. Отвечай строго на русском языке.",
}

def build_system_prompt(lang: str) -> str:
    return PROMPTS.get(lang, PROMPTS["ru"])
    
ACTIVE_MODEL = "openai/gpt-oss-120b"
print(f"Подключена модель: {ACTIVE_MODEL}")

@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    lang = get_user_lang(message.from_user.id)
    save_history(message.from_user.id, [])
    if lang == "en":
        text = "Yo! ❤️ Locked in, bro. 🚀 What's good — tell me what's on your mind, training, or plans and let's break it down. 🔥"
    else:
        text = "Здорова! ❤️ На связи, бро. 🚀 Че как, рассказывай подробно, какие мысли в голове крутятся, давай перетрем за жизнь и планы. 🔥"
    await message.answer(text, reply_markup=MAIN_MENU)

@dp.message(F.text.in_({"/reset", "🧹 Сброс"}))
async def cmd_reset(message: Message):
    lang = get_user_lang(message.from_user.id)
    save_history(message.from_user.id, [])
    text = "Memory wiped clean. Locked in, bro. 🌑" if lang == "en" else "Память обнулена. На связи, бро. 🌑"
    await message.answer(text, reply_markup=MAIN_MENU)

@dp.message(F.text.in_({"/lang", "🌐 Язык"}))
async def cmd_lang(message: Message):
    lang = get_user_lang(message.from_user.id)
    current_label = "English 🇬🇧" if lang == "en" else "Русский 🇷🇺"
    if lang == "en":
        text = f"Current language: <b>{current_label}</b>\nPick the language you want me to talk in:"
    else:
        text = f"Текущий язык: <b>{current_label}</b>\nВыбери язык, на котором будем общаться:"
    await message.answer(text, reply_markup=LANG_KEYBOARD, parse_mode="HTML")

@dp.message(F.text == "⚡ Инфо")
async def cmd_info(message: Message):
    user_id = message.from_user.id
    rec = get_user_record(user_id)
    lang_label = "English 🇬🇧" if rec["lang"] == "en" else "Русский 🇷🇺"
    msg_count = len(rec["history"])
    if rec["lang"] == "en":
        text = (
            f"<b>Bro Mentor Status</b> 🔥\n"
            f"Language: <b>{lang_label}</b>\n"
            f"Saved messages in memory: <b>{msg_count}/{MAX_HISTORY}</b>\n"
            f"Commands: /start, /lang, /reset"
        )
    else:
        text = (
            f"<b>Статус Bro Mentor</b> 🔥\n"
            f"Язык: <b>{lang_label}</b>\n"
            f"Сообщений в памяти: <b>{msg_count}/{MAX_HISTORY}</b>\n"
            f"Команды: /start, /lang, /reset"
        )
    await message.answer(text, reply_markup=MAIN_MENU, parse_mode="HTML")

@dp.callback_query(F.data.in_({"lang_ru", "lang_en"}))
async def process_lang_callback(callback: CallbackQuery):
    new_lang = "en" if callback.data == "lang_en" else "ru"
    set_user_lang(callback.from_user.id, new_lang)
    if new_lang == "en":
        confirm_text = "Switched to <b>English 🇬🇧</b>. Let's get to work, bro! 🔥"
        toast_text = "Language set to English"
    else:
        confirm_text = "Переключил на <b>Русский 🇷🇺</b>. Погнали дальше, бро! 🔥"
        toast_text = "Язык переключён на русский"

    await callback.answer(toast_text)
    await callback.message.edit_text(confirm_text, parse_mode="HTML")

@dp.message(F.text)
async def chat_with_ai(message: Message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    history = get_history(user_id)

    history.append({"role": "user", "content": message.text})
    history = history[-MAX_HISTORY:]

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        system_prompt = build_system_prompt(lang)
        messages_payload = [{"role": "system", "content": system_prompt}] + history
        response = groq_client.chat.completions.create(
            model=ACTIVE_MODEL,
            messages=messages_payload,
            temperature=0.5,
            max_tokens=750,
        )
        reply = response.choices[0].message.content

        history.append({"role": "assistant", "content": reply})
        history = history[-MAX_HISTORY:]
        save_history(user_id, history)

        await message.answer(reply, reply_markup=MAIN_MENU)
    except Exception as e:
        await message.answer(f"Ошибка: {e}", reply_markup=MAIN_MENU)

async def main():
    print("Бот запущен на локальной надежной памяти с выбором языка и меню!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
