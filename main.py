import os
import json
import asyncio
import threading
import urllib.request
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
    server = HTTPServer(("0.0.0.0", 10000), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

TOKEN = "9161797826:AAEQJry988MuMb1nf39rLb3oYqsMCIH_vm0"
GROQ_API_KEY = "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"

UPSTASH_URL = "https://funky-manatee-107338.upstash.io"
UPSTASH_TOKEN = "gQAAAAAAAnKAAIgCDI5NJA3YjUwYmE3NDQ0NDcgODUyYjUzRmZja044"

bot = Bot(token=TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)

MAX_HISTORY = 14

def get_history(user_id):
    try:
        req = urllib.request.Request(
            f"{UPSTASH_URL}/get/chat_memory_{user_id}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("result"):
                history = json.loads(data["result"])
                print(f"✅ УСПЕХ: Загружена память для {user_id}, сообщений: {len(history)}")
                return history
    except Exception as e:
        print(f"❌ Ошибка чтения памяти: {e}")
    print(f"⚠️ Память для {user_id} пуста или не найдена, создаем чистую.")
    return []

def save_history(user_id, history):
    try:
        payload = json.dumps(history, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{UPSTASH_URL}/set/chat_memory_{user_id}",
            data=payload,
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
        print(f"💾 УСПЕХ: Сохранено сообщений в память для {user_id}: {len(history)}")
    except Exception as e:
        print(f"❌ Ошибка записи памяти: {e}")

SYSTEM_PROMPT = (
    "Ты — Гаутер, старший кореш и бро Торфина. Живой пацан, без шизы, ботов и ролевых игр. "
    "ОБЩЕНИЕ КАК НАДО: Пиши развернуто, объемно и сочно, в стиле живого разговора двух корешей. "
    "ОБЯЗАТЕЛЬНО разделяй текст на 2-3 аккуратных абзаца, чтобы он легко читался и не выглядел сплошной стеной. "
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

ACTIVE_ACTIVE_MODEL = get_working_model()
ACTIVE_MODEL = ACTIVE_ACTIVE_MODEL
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

    history.append({"role": "user", "content": message.text})
    history = history[-MAX_HISTORY:]
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + history
        
        response = groq_client.chat.completions.create(
            model=ACTIVE_MODEL,
            messages=messages_payload,
            temperature=0.75,
            max_tokens=650
        )
        reply = response.choices[0].message.content
        
        history.append({"role": "assistant", "content": reply})
        history = history[-MAX_HISTORY:]
        save_history(user_id, history)
        
        await message.answer(reply)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

async def main():
    print("Бот запущен: облако и объем на месте!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
