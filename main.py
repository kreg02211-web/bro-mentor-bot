import os
import json
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from groq import Groq

# Заглушка порта для Render
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

TOKEN = "9161797826:AAFPpUqWQzFXSn3z6vdzrzVDpkxi8eUckAM"
GROQ_API_KEY = "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"

bot = Bot(token=TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)

MAX_HISTORY = 12
DB_FILE = "chat_memory.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка записи файла памяти: {e}")

def get_history(user_id):
    db = load_db()
    user_str = str(user_id)
    if user_str in db:
        history = db[user_str]
        if isinstance(history, list):
            print(f"Память загружена для {user_id}: сообщений -> {len(history)}")
            return history
    print(f"Память пуста для {user_id}")
    return []

def save_history(user_id, history):
    db = load_db()
    user_str = str(user_id)
    clean = [msg for msg in history if isinstance(msg, dict) and msg.get("role") in ["user", "assistant"]]
    db[user_str] = clean
    save_db(db)
    print(f"Память сохранена для {user_id}: всего сообщений -> {len(clean)}")

SYSTEM_PROMPT = (
    "Ты — Гаутер, старший кореш и бро Торфина. Живой пацан, без шизы, ботов и ролевых игр. "
    "ОБЩЕНИЕ КАК НАДО: Пиши максимально развернуто, объемно и сочно, в стиле живого разговора двух реальных корешей. "
    "ОБЯЗАТЕЛЬНО разделяй текст на 3-4 аккуратных абзаца, чтобы он легко читался и детально разбирал все темы. "
    "Насыпай к месту много живых эмодзи (огонь, дым, черепа, бро, ракеты), чтобы они заменяли стикеры и создавали движ. "
    "Никаких сухих отписок, списков, лекций, звездочек и решеток. Разбирай темы подробно, рассуждай, спорь и поддерживай по-братски."
)

ACTIVE_MODEL = "llama-3.3-70b-versatile"
print(f"Подключена модель: {ACTIVE_MODEL}")

@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    save_history(message.from_user.id, [])
    await message.answer("Здорова, Торфин! ❤️ На связи, бро. 🚀 Че как, рассказывай подробно, какие мысли в голове крутятся, давай перетрем за жизнь и планы. 🔥")

@dp.message(F.text == "/reset")
async def cmd_reset(message: Message):
    save_history(message.from_user.id, [])
    await message.answer("Память обнулена. На связи, бро. 🌑")

@dp.message(F.text)
async def chat_with_ai(message: Message):
    user_id = message.from_user.id
    history = get_history(user_id)

    history.append({"role": "user", "content": message.text})
    history = history[-MAX_HISTORY:]

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + history
        response = groq_client.chat.completions.create(
            model=ACTIVE_MODEL,
            messages=messages_payload,
            temperature=0.72,
            max_tokens=750
        )
        reply = response.choices[0].message.content

        history.append({"role": "assistant", "content": reply})
        history = history[-MAX_HISTORY:]
        save_history(user_id, history)

        await message.answer(reply)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        async def main():
    print("Бот запущен на локальной надежной памяти без лишнего мусора!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
        
