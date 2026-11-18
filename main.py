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

MAX_HISTORY = 12  # Держим нормальный объем истории, чтобы помнил контекст

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
                # Очищаем от всякого мусора, оставляем только диалог
                clean = [msg for msg in history if isinstance(msg, dict) and msg.get("role") in ["user", "assistant"]]
                print(f"✅ Память загружена для {user_id}: сообщений -> {len(clean)}")
                return clean
    except Exception as e:
        print(f"❌ Ошибка чтения памяти: {e}")
    print(f"⚠️ Память для {user_id} пуста.")
    return []

def save_history(user_id, history):
    try:
        clean = [msg for msg in history if isinstance(msg, dict) and msg.get("role") in ["user", "assistant"]]
        redis.set(f"chat_memory_{user_id}", json.dumps(clean, ensure_ascii=False))
        print(f"💾 Память сохранена для {user_id}: всего сообщений -> {len(clean)}")
    except Exception as e:
        print(f"❌ Ошибка записи памяти: {e}")

# Тот самый идеальный, сочный промпт для стиля кореша
SYSTEM_PROMPT = (
    "Ты — Гаутер, старший кореш и бро Торфина. Живой пацан, без шизы, ботов и ролевых игр. "
    "ОБЩЕНИЕ КАК НАДО: Пиши максимально развернуто, объемно и сочно, в стиле живого разговора двух реальных корешей. "
    "ОБЯЗАТЕЛЬНО разделяй текст на 3-4 аккуратных абзаца, чтобы он легко читался и детально разбирал все темы. "
    "Насыпай к месту много живых эмодзи (огонь, дым, черепа, бро, ракеты), чтобы они заменяли стикеры и создавали движ. "
    "Никаких сухих отписок, списков, лекций, звездочек и решеток. Разбирай темы подробно, рассуждай, спорь и поддерживай по-братски."
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
    await message.answer("Здорова, Торфин! ❤️ На связи, бро. 🚀 Че как, рассказывай подробно, какие мысли в голове крутятся, давай перетрем за жизнь и планы. 🔥")

@dp.message(F.text == "/reset")
async def cmd_reset(message: Message):
    save_history(message.from_user.id, [])
    await message.answer("Память обнулена. На связи, бро. 🌑")

@dp.message(F.text)
async def chat_with_ai(message: Message):
    user_id = message.from_user.id
    history = get_history(user_id)
    # Добавляем свежее сообщение юзера
    history.append({"role": "user", "content": message.text})
    history = history[-MAX_HISTORY:]

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + history
        
        response = groq_client.chat.completions.create(
            model=ACTIVE_MODEL,
            messages=messages_payload,
            temperature=0.72,
            max_tokens=750  # Поставили жирный запас, чтобы текст не обрывался и шел развернуто
        )
        reply = response.choices[0].message.content
        
        # Добавляем ответ ассистента в историю и сохраняем в облако
        history.append({"role": "assistant", "content": reply})
        history = history[-MAX_HISTORY:]
        save_history(user_id, history)
        
        await message.answer(reply)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

async def main():
    print("Бот запущен: стиль восстановлен, токены подняты, память активна!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
