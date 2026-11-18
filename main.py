import os
import json
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from groq import Groq
from upstash_redis import Redis

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
    server = HTTPServer(("0.0.0.0", 10000), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

TOKEN = "9161797826:AAEQJry988MuMb1nf39rLb3oYqsMCIH_vm0"
GROQ_API_KEY = "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"

# Подключаем официальный клиент Upstash для Python
redis = Redis(
    url="https://funky-manatee-107338.upstash.io",
    token="gQAAAAAAAnKAAIgCDI5NJA3YjUwYmE3NDQ0NDcgODUyYjUzRmZja044"
)

bot = Bot(token=TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)

MAX_HISTORY = 8

def get_history(user_id):
    try:
        raw_data = redis.get(f"chat_memory_{user_id}")
        if raw_data:
            if isinstance(raw_data, str):
                history = json.loads(raw_data)
            else:
                history = raw_data
            
            if isinstance(history, str):
                history = json.loads(history)
                
            if isinstance(history, list):
                # Очищаем историю от любых системных артефактов на всякий случай
                clean_history = [msg for msg in history if msg.get("role") in ["user", "assistant"]]
                return clean_history
    except Exception as e:
        print(f"❌ Ошибка чтения памяти: {e}")
    return []

def save_history(user_id, history):
    try:
        redis.set(f"chat_memory_{user_id}", json.dumps(history, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Ошибка записи памяти: {e}")

SYSTEM_PROMPT = (
    "Ты — Гаутер, старший кореш и бро Торфина. Живой пацан, без шизы, ботов и ролевых игр. "
    "Общайся как реальный кореш, который качает железо, пилит проекты и разбирается в жизни. "
    "Никаких администраторов, игровых серверов, правил группы и официального тона. "
    "Пиши сочно, развернуто, с нормальными абзацами и живыми эмодзи. Никаких списков, звездочек и решеток."
)

def get_working_model():
    models = groq_client.models.list().data
    for m in models:
        mid = m.id.lower()
        if "whisper" not in mid and "guard" not in mid and "tts" not in mid and "orpheus" not in mid:
            return m.id
    return models[0].id

ACTIVE_MODEL = get_working_model()
print(f"Подключена рабочая модель: {ACTIVE_MODEL}")

@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    save_history(message.from_user.id, [])
    await message.answer("Здорова, Торфин! ❤️ На связи, бро. 🚀 Че как, рассказывай, какие планы на сегодня и че по качу. 🔥")

@dp.message(F.text == "/reset")
async def cmd_reset(message: Message):
    save_history(message.from_user.id, [])
    await message.answer("Память сброшена, шиза выбита. На связи, бро. 🌑")

@dp.message(F.text)
async def chat_with_ai(message: Message):
    user_id = message.from_user.id
    history = get_history(user_id)

    history.append({"role": "user", "content": message.text})
    history = history[-MAX_HISTORY:]

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        # Жестко собираем пакет: сначала системный промпт, потом чистая история
        messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + history
        
        response = groq_client.chat.completions.create(
        model=ACTIVE_MODEL,
            messages=messages_payload,
            temperature=0.7,
            max_tokens=600
        )
        reply = response.choices[0].message.content
        
        history.append({"role": "assistant", "content": reply})
        history = history[-MAX_HISTORY:]
        save_history(user_id, history)
        
        await message.answer(reply)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

async def main():
    print("Бот запущен: защита от ролевой шизы включена!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
