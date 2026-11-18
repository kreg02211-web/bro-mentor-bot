import os
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
    server = HTTPServer(("0.0.0.0", 10000), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

TOKEN = "9161797826:AAEQJry988MuMb1nf39rLb3oYqsMCIH_vm0"
GROQ_API_KEY = "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"

bot = Bot(token=TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = (
    "Ты — нормальный старший кореш и бро, надежный ментор. Общайся по-простому, тепло и на расслабоне, но строго по делу. "
    "СЛЕДИ ЗА КОНТЕКСТОМ: если собеседник пишет о проблемах, усталости, деньгах, целях или грусти — никаких неуместных смешков, угара и слова 'Ахах'. "
    "Всерьез оценивай ситуацию, врубай эмпатию и пиши сдержанно, поддерживающе и уважительно. Смеяться и шутить можно только на откровенный прикол или позитив. "
    "СТРУКТУРА ОТВЕТА ДЛЯ СЕРЬЕЗНЫХ ТЕМ: делай ответ на 3 коротких абзаца. Первый — чисто человеческая поддержка и понимание. Второй — короткий разбор сути проблемы без воды. Третий — дельный совет или вектор движения. "
    "Обязательно добавляй к месту живые эмодзи (1-2 штуки на абзац), чтобы текст не казался сухим. "
    "НИКАКИХ лекций, нравоучений, списков, маркеров и длинных полотен текста. "
    "НИКАКИХ звездочек (**), решеток (#), списков и форматирования. Только чистый текст, разбитый на абзацы."
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
    await message.answer(
        "На эту кнопку редко жмут от хорошей жизни… 🌑\n\n"
        "Что же привело тебя ко мне в этот раз? Рассказывай, что давит или не дает покоя, будем разбираться."
    )

@dp.message(F.text)
async def chat_with_ai(message: Message):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        response = groq_client.chat.completions.create(
            model=ACTIVE_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ],
            temperature=0.6,
            max_tokens=700
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

async def main():
    print("Бот запущен, стартовый вайб обновлен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
