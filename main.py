import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from groq import Groq

# Заглушка порта для Render
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_server():
    server = HTTPServer(("0.0.0.0", 10000), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()
BOT_TOKEN = "9161797826:AAEQJry988MuMb1nf39rLb3oYqsMCIH_vm0"
GROQ_API_KEY = "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"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = (
    "Ты — нормальный старший кореш и бро. Общайся по-простому, мягко и на расслабоне, как в братском разговоре. "
    "Обязательно добавляй к месту живые эмодзи, чтобы текст не казался сухим. "
    "Никаких лекций, нравоучений, списков и длинных текстов. Отвечай кратко, емко и по сути. "
    "Никаких звездочек (**), решеток (#). Только живой человеческий язык и теплый вайб."
)

@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer("Здарова! 🤝 На связи. Че как, рассказывай, какие мысли?")

@dp.message(F.text)
async def chat_with_ai(message: Message):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        response = groq_client.chat.completions.create(
            model=ACTIVE_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text},
            ],
            temperature=0.7,
            max_tokens=600,
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
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
@dp.message(F.text)
async def chat_with_ai(message: Message):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        response = groq_client.chat.completions.create(
            model=ACTIVE_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text},
            ],
            temperature=0.7,
            max_tokens=600,
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

async def main():
    print("Бот запущен и готов к работе без лишней духоты!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
