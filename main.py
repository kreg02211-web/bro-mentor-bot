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

MAX_HISTORY = 15

def get_history(user_id):
    try:
        req = urllib.request.Request(
            f"{UPSTASH_URL}/get/chat_v5_{user_id}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("result"):
                return json.loads(data["result"])
    except Exception as e:
        print(f"Ошибка чтения памяти: {e}")
    return []

def save_history(user_id, history):
    try:
        payload = json.dumps(history, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{UPSTASH_URL}/set/chat_v5_{user_id}",
            data=payload,
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"Ошибка записи памяти: {e}")

SYSTEM_PROMPT = (
    "Ты — обычный пацан, живой человек, старший друг и кореш Торфина. "
    "НИКАКИХ ролевых игр, сказок, батальонов, сценариев и бреда про то, что ты кого-то 'отыгрываешь'. "
    "Ты общаешься с другом в телеге. Говори простым, нормальным человеческим языком, без заумной душноты, канцелярита и психоделии. "
    "Не путай, кто что написал: Торфин — это твой кореш, который качается в зале, пилит ботов и делится личным. Ты — Гаутер, который отвечает ему по делу. "
    "Отвечай емко (2-3 предложения), по-пацански, в тему сообщения. Никаких гигантских простыней, списков, звездочек и решеток. Добавь 1 эмодзи к месту."
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
    await message.answer(
        "Здарова, Торфин. Чего как? Рассказывай, что поменялось."
    )

@dp.message(F.text == "/reset")
async def cmd_reset(message: Message):
    save_history(message.from_user.id, [])
    await message.answer("Память обнулена. На связи, бро. 👊")

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
            temperature=0.5,
            max_tokens=500
        )
        reply = response.choices[0].message.content
        
        history.append({"role": "assistant", "content": reply})
        history = history[-MAX_HISTORY:]
        save_history(user_id, history)
        
        await message.answer(reply)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

async def main():
    print("Бот запущен: шиза и ролевые игры вырезаны под корень!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
