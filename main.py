import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from groq import Groq

BOT_TOKEN = "9161797826:AAEQJry988MuMb1nf39rLb3oYqsMCIH_vm0"
GROQ_API_KEY = "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"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = (
    "Ты — крутой старший бро и ментор. Общайся прямо, без воды, "
    "поддерживай, давай честную базу, пинай развиваться и идти к целям. Общайся на ты."
)

def get_working_model():
    models = groq_client.models.list().data
    for m in models:
        mid = m.id.lower()
        if "whisper" not in mid and "guard" not in mid and "tts" not in mid:
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
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

async def main():
    print("Новый ИИ-бро запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
