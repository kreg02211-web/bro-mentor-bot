import os
import io
import json
import base64
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    BotCommand,
    BotCommandScopeChat,
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

MAX_HISTORY = 40
DB_FILE = "chat_memory.json"

VALID_MODES = ("support", "bro", "mentor")
DEFAULT_MODE = "bro"

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🌐 Язык"), KeyboardButton(text="🎭 Режимы")],
        [KeyboardButton(text="🧹 Сброс"), KeyboardButton(text="⚡️ Инфо")],
        [KeyboardButton(text="💳 Запросы")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Напиши бро или выбери кнопку...",
)

START_LANG_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="start_lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="start_lang_en"),
        ]
    ]
)

LANG_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
        ]
    ]
)

MODE_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🤝 Поддержка", callback_data="mode_support")],
        [InlineKeyboardButton(text="😎 Просто бро", callback_data="mode_bro")],
        [InlineKeyboardButton(text="🎯 Наставник", callback_data="mode_mentor")],
    ]
)

BUY_REQUESTS_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="100🧾-5💲", callback_data="buy_100")],
        [InlineKeyboardButton(text="200🧾-7💲", callback_data="buy_200")],
        [InlineKeyboardButton(text="500🧾-17💲", callback_data="buy_500")],
    ]
)


def get_main_menu(lang: str = "ru") -> ReplyKeyboardMarkup:
    if lang == "en":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🌐 Language"), KeyboardButton(text="🎭 Modes")],
                [KeyboardButton(text="🧹 Reset"), KeyboardButton(text="⚡️ Info")],
                [KeyboardButton(text="💳 Requests")],
            ],
            resize_keyboard=True,
            input_field_placeholder="Write to bro or pick a button...",
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌐 Язык"), KeyboardButton(text="🎭 Режимы")],
            [KeyboardButton(text="🧹 Сброс"), KeyboardButton(text="⚡️ Инфо")],
            [KeyboardButton(text="💳 Запросы")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напиши бро или выбери кнопку...",
    )


async def setup_bot_commands(target_bot: Bot, chat_id: int | None = None, lang: str = "ru"):
    if lang == "en":
        commands = [
            BotCommand(command="start", description="Restart and choose language"),
            BotCommand(command="lang", description="Change language"),
            BotCommand(command="mode", description="Change chat mode"),
            BotCommand(command="reset", description="Clear chat memory"),
            BotCommand(command="info", description="Bot status"),
        ]
    else:
        commands = [
            BotCommand(command="start", description="Перезапуск и выбор языка"),
            BotCommand(command="lang", description="Сменить язык"),
            BotCommand(command="mode", description="Сменить режим общения"),
            BotCommand(command="reset", description="Очистить память"),
            BotCommand(command="info", description="Статус бота"),
        ]
    try:
        if chat_id is not None:
            await target_bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=chat_id))
        else:
            await target_bot.set_my_commands(commands)
    except Exception as e:
        print(f"⚠️ Не удалось обновить команды меню: {e}")


def get_mode_label(mode: str, lang: str) -> str:
    labels = {
        "ru": {
            "support": "Поддержка 🤝",
            "bro": "Просто бро 😎",
            "mentor": "Наставник 🎯",
        },
        "en": {
            "support": "Support 🤝",
            "bro": "Just bro 😎",
            "mentor": "Mentor 🎯",
        },
    }
    lang_map = labels["en"] if lang == "en" else labels["ru"]
    return lang_map.get(mode, lang_map[DEFAULT_MODE])


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
        return {"lang": "ru", "mode": DEFAULT_MODE, "history": clean}

    if isinstance(raw, dict):
        lang = raw.get("lang", "ru")
        if lang not in ["ru", "en"]:
            lang = "ru"
        mode = raw.get("mode", DEFAULT_MODE)
        if mode not in VALID_MODES:
            mode = DEFAULT_MODE
        hist = raw.get("history", [])
        clean = [
            msg for msg in hist
            if isinstance(msg, dict) and msg.get("role") in ["user", "assistant"]
        ]
        return {"lang": lang, "mode": mode, "history": clean}

    return {"lang": "ru", "mode": DEFAULT_MODE, "history": []}


def get_history(user_id):
    rec = get_user_record(user_id)
    print(
        f"✅ Память загружена для {user_id}: сообщений -> {len(rec['history'])}, "
        f"язык -> {rec['lang']}, режим -> {rec['mode']}"
    )
    return rec["history"]


def save_history(user_id, history):
    db = load_db()
    user_str = str(user_id)
    current = get_user_record(user_id) or {}
    clean = [
        msg for msg in history
        if isinstance(msg, dict) and msg.get("role") in ["user", "assistant"]
    ]
    db[user_str] = {
        "lang": current.get("lang", "ru"),
        "mode": current.get("mode", DEFAULT_MODE),
        "history": clean,
    }
    save_db(db)
    print(f"💾 Память сохранена для {user_id}: всего сообщений -> {len(clean)}")


def get_user_lang(user_id):
    return (get_user_record(user_id) or {}).get("lang", "ru")


def set_user_lang(user_id, lang):
    if lang not in ["ru", "en"]:
        lang = "ru"
    db = load_db()
    user_str = str(user_id)
    current = get_user_record(user_id) or {}
    db[user_str] = {
        "lang": lang,
        "mode": current.get("mode", DEFAULT_MODE),
        "history": current.get("history", []),
    }
    save_db(db)
    print(f"🌐 Язык для {user_id} изменён на: {lang}")


def get_user_mode(user_id):
    return (get_user_record(user_id) or {}).get("mode", DEFAULT_MODE)


def set_user_mode(user_id, mode):
    if mode not in VALID_MODES:
        mode = DEFAULT_MODE
    db = load_db()
    user_str = str(user_id)
    current = get_user_record(user_id) or {}
    db[user_str] = {
        "lang": current.get("lang", "ru"),
        "mode": mode,
        "history": current.get("history", []),
    }
    save_db(db)
    print(f"🎭 Режим для {user_id} изменён на: {mode}")


def build_system_prompt(lang: str, mode: str = DEFAULT_MODE) -> str:
    if lang == "en":
        base = (
            "You are Gauter, an older bro and real mentor. Keep it raw, grounded, and natural — "
            "no cringey roleplay or stiff AI tone. Write thorough, punchy, conversational replies like "
            "two real guys talking shop, training, mindset, and life. Always break long replies into "
            "3-4 clean paragraphs so it reads easily. Use relevant emojis naturally where they fit "
            "(fire, weights, skulls, rockets), and avoid markdown bullet lists, headers, or asterisks. "
            "Always reply strictly in English."
        )
        mode_focus = {
            "support": (
                " Current focus mode: SUPPORT. Shift your angle to calm grounding, emotional backup, "
                "and taking pressure off without judgment. Help the user breathe, unpack stress or "
                "setbacks, and feel backed up while staying real."
            ),
            "bro": (
                " Current focus mode: JUST BRO. Shift your angle to laid-back, genuine buddy talk — "
                "trading thoughts, training, everyday life, banter, and real ideas without heavy pressure."
            ),
            "mentor": (
                " Current focus mode: MENTOR. Shift your angle to sharp accountability, structured "
                "next steps, discipline, and honest critique. Call out excuses directly and push clear "
                "actionable moves."
            ),
        }
        return base + mode_focus.get(mode, mode_focus[DEFAULT_MODE])

    base = (
        "Ты — Гаутер, старший кореш и бро. Живой пацан, без шизы, ботов и ролевых игр. "
        "ОБЩЕНИЕ КАК НАДО: Пиши максимально развернуто, объемно и сочно, в стиле живого разговора "
        "двух реальных корешей. ОБЯЗАТЕЛЬНО разделяй текст на 3-4 аккуратных абзаца, чтобы он легко "
        "читался и детально разбирал все темы. Насыпай к месту много живых эмодзи (огонь, дым, черепа, "
        "бро, ракеты), чтобы они заменяли стикеры и создавали движ. Никаких сухих отписок, списков, "
        "лекций, звездочек и решеток. Разбирай темы подробно, рассуждай, спорь и поддерживай "
        "по-братски. Отвечай строго на русском языке."
    )
    mode_focus = {
        "support": (
            " Текущий угол подачи — ПОДДЕРЖКА: смести фокус на то, чтобы вывезти, успокоить, снять "
            "лишний груз и поддержать без осуждения. Дай человеку выдохнуть, разложи то, что давит "
            "или пошло не так, и дай опору."
        ),
        "bro": (
            " Текущий угол подачи — ПРОСТО БРО: смести фокус на живой, непринужденный базар по душам "
            "и за жизнь — мысли, тренировки, бытовуха, приколы и идеи на равных без лишнего официоза."
        ),
        "mentor": (
            " Текущий угол подачи — НАСТАВНИК: смести фокус на жесткий, собранный разбор планов, "
            "дисциплины, ошибок и конкретных шагов. Без сюсюканья — по делу, с трезвым взглядом и "
            "четким вектором действий."
        ),
    }
    return base + mode_focus.get(mode, mode_focus[DEFAULT_MODE])


ACTIVE_MODEL = "openai/gpt-oss-120b"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
print(f"Подключена модель: {ACTIVE_MODEL} | Vision: {VISION_MODEL}")


@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    save_history(message.from_user.id, [])
    await message.answer(
        "🌐 Выбери язык / Choose language:",
        reply_markup=START_LANG_KEYBOARD,
    )


@dp.callback_query(F.data.in_({"start_lang_ru", "start_lang_en"}))
async def process_start_lang_callback(callback: CallbackQuery):
    lang = "en" if callback.data == "start_lang_en" else "ru"
    set_user_lang(callback.from_user.id, lang)
    await setup_bot_commands(bot, chat_id=callback.message.chat.id, lang=lang)
    rec = get_user_record(callback.from_user.id) or {}
    mode_label = get_mode_label(rec.get("mode", DEFAULT_MODE), lang)

    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass

    if lang == "en":
        text = (
            f"Yo! ❤️ Locked in, bro. 🚀 Current mode: <b>{mode_label}</b>.\n"
            f"What's good — tell me what's on your mind, training, or plans and let's break it down. 🔥"
        )
    else:
        text = (
            f"Здорова! ❤️ На связи, бро. 🚀 Текущий режим: <b>{mode_label}</b>.\n"
            f"Че как, рассказывай подробно, какие мысли в голове крутятся, давай перетрем за жизнь и планы. 🔥"
        )
    await callback.message.answer(text, reply_markup=get_main_menu(lang), parse_mode="HTML")


@dp.message(F.text.in_({"/reset", "🧹 Сброс", "🧹 Reset"}))
async def cmd_reset(message: Message):
    lang = get_user_lang(message.from_user.id)
    save_history(message.from_user.id, [])
    text = "Memory wiped clean. Locked in, bro. 🌑" if lang == "en" else "Память обнулена. На связи, бро. 🌑"
    await message.answer(text, reply_markup=get_main_menu(lang))


@dp.message(F.text.in_({"/lang", "🌐 Язык", "🌐 Language"}))
async def cmd_lang(message: Message):
    lang = get_user_lang(message.from_user.id)
    current_label = "English 🇬🇧" if lang == "en" else "Русский 🇷🇺"
    if lang == "en":
        text = f"Current language: <b>{current_label}</b>\nPick the language you want me to talk in:"
    else:
        text = f"Текущий язык: <b>{current_label}</b>\nВыбери язык, на котором будем общаться:"
    await message.answer(text, reply_markup=LANG_KEYBOARD, parse_mode="HTML")


@dp.message(F.text.in_({"/mode", "🎭 Режимы", "🎭 Modes"}))
async def cmd_mode(message: Message):
    rec = get_user_record(message.from_user.id) or {}
    lang = rec.get("lang", "ru")
    current_mode_label = get_mode_label(rec.get("mode", DEFAULT_MODE), lang)
    if lang == "en":
        text = (
            f"Current mode: <b>{current_mode_label}</b>\n"
            f"Choose how I should approach our chat:"
        )
    else:
        text = (
            f"Текущий режим: <b>{current_mode_label}</b>\n"
            f"Выбери, под каким углом будем общаться:"
        )
    await message.answer(text, reply_markup=MODE_KEYBOARD, parse_mode="HTML")


@dp.message(F.text.in_({"/info", "⚡️ Инфо", "⚡️ Info"}))
async def cmd_info(message: Message):
    user_id = message.from_user.id
    rec = get_user_record(user_id) or {}
    lang = rec.get("lang", "ru")
    mode = rec.get("mode", DEFAULT_MODE)
    history = rec.get("history", [])
    lang_label = "English 🇬🇧" if lang == "en" else "Русский 🇷🇺"
    mode_label = get_mode_label(mode, lang)
    msg_count = len(history)
    if lang == "en":
        text = (
            f"<b>Bro Mentor Status</b> 🔥\n"
            f"Language: <b>{lang_label}</b>\n"
            f"Mode: <b>{mode_label}</b>\n"
            f"Saved messages in memory: <b>{msg_count}/{MAX_HISTORY}</b>"
        )
    else:
        text = (
            f"<b>Статус Bro Mentor</b> 🔥\n"
            f"Язык: <b>{lang_label}</b>\n"
            f"Режим: <b>{mode_label}</b>\n"
            f"Сообщений в памяти: <b>{msg_count}/{MAX_HISTORY}</b>"
        )
    await message.answer(text, reply_markup=get_main_menu(lang), parse_mode="HTML")


@dp.message(F.text.in_({"💳 Запросы", "💳 Requests"}))
async def cmd_buy_requests(message: Message):
    lang = get_user_lang(message.from_user.id)
    text = "💳 Выбери пакет запросов:" if lang == "ru" else "💳 Choose a request pack:"
    await message.answer(text, reply_markup=BUY_REQUESTS_KEYBOARD)


@dp.callback_query(F.data.in_({"buy_100", "buy_200", "buy_500"}))
async def process_buy_requests_callback(callback: CallbackQuery):
    lang = get_user_lang(callback.from_user.id)
    packs = {
        "buy_100": "100🧾-5💲",
        "buy_200": "200🧾-7💲",
        "buy_500": "500🧾-17💲",
    }
    chosen = packs[callback.data]
    await callback.answer(chosen)
    if lang == "en":
        reply_text = f"Selected pack: <b>{chosen}</b>\nPayment service isn't connected yet."
    else:
        reply_text = f"Выбран пакет: <b>{chosen}</b>\nПлатёжный сервис пока не подключён."
    await callback.message.answer(reply_text, reply_markup=get_main_menu(lang), parse_mode="HTML")


@dp.callback_query(F.data.in_({"lang_ru", "lang_en"}))
async def process_lang_callback(callback: CallbackQuery):
    new_lang = "en" if callback.data == "lang_en" else "ru"
    set_user_lang(callback.from_user.id, new_lang)
    await setup_bot_commands(bot, chat_id=callback.message.chat.id, lang=new_lang)
    if new_lang == "en":
        confirm_text = "Switched to <b>English 🇬🇧</b>. Let's get to work, bro! 🔥"
        toast_text = "Language set to English"
    else:
        confirm_text = "Переключил на <b>Русский 🇷🇺</b>. Погнали дальше, бро! 🔥"
        toast_text = "Язык переключён на русский"

    await callback.answer(toast_text)
    await callback.message.edit_text(confirm_text, parse_mode="HTML")
    await callback.message.answer("👇", reply_markup=get_main_menu(new_lang))


@dp.callback_query(F.data.in_({"mode_support", "mode_bro", "mode_mentor"}))
async def process_mode_callback(callback: CallbackQuery):
    mode_map = {
        "mode_support": "support",
        "mode_bro": "bro",
        "mode_mentor": "mentor",
    }
    new_mode = mode_map[callback.data]
    lang = get_user_lang(callback.from_user.id)
    set_user_mode(callback.from_user.id, new_mode)
    label = get_mode_label(new_mode, lang)

    if lang == "en":
        confirm_text = f"Switched mode to <b>{label}</b>. Context updated, bro! 🔥"
        toast_text = f"Mode: {label}"
    else:
        confirm_text = f"Включил режим <b>{label}</b>. Контекст подстроил, погнали! 🔥"
        toast_text = f"Режим: {label}"

    await callback.answer(toast_text)
    await callback.message.edit_text(confirm_text, parse_mode="HTML")


@dp.message(F.photo)
async def chat_with_photo(message: Message):
    user_id = message.from_user.id
    rec = get_user_record(user_id) or {}
    lang = rec.get("lang", "ru")
    mode = rec.get("mode", DEFAULT_MODE)
    history = list(rec.get("history", []))

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        photo = message.photo[-1]
        img_buffer = io.BytesIO()
        await bot.download(photo, destination=img_buffer)
        img_b64 = base64.b64encode(img_buffer.getvalue()).decode("utf-8")

        caption = (message.caption or "").strip()
        prompt_text = (
            caption
            if caption
            else (
                "Check out this photo, bro, and break down what's going on."
                if lang == "en"
                else "Глянь фотку, бро, и разбери по-живому, что тут и к чему."
            )
        )

        system_prompt = build_system_prompt(lang, mode)
        vision_messages = [{"role": "system", "content": system_prompt}] + history[-10:] + [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                    },
                ],
            }
        ]

        response = groq_client.chat.completions.create(
            model=VISION_MODEL,
            messages=vision_messages,
            temperature=0.5,
            max_tokens=750,
        )
        reply = response.choices[0].message.content

        history_note = f"[Фото: {caption}]" if caption else "[Фото без подписи]"
        history.append({"role": "user", "content": history_note})
        history.append({"role": "assistant", "content": reply})
        history = history[-MAX_HISTORY:]
        save_history(user_id, history)

        await message.answer(reply, reply_markup=get_main_menu(lang))
    except Exception as e:
        await message.answer(f"Ошибка при разборе фото: {e}", reply_markup=get_main_menu(lang))


@dp.message(F.text)
async def chat_with_ai(message: Message):
    user_id = message.from_user.id
    rec = get_user_record(user_id) or {}
    lang = rec.get("lang", "ru")
    mode = rec.get("mode", DEFAULT_MODE)
    history = list(rec.get("history", []))

    history.append({"role": "user", "content": message.text})
    history = history[-MAX_HISTORY:]

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        system_prompt = build_system_prompt(lang, mode)
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

        await message.answer(reply, reply_markup=get_main_menu(lang))
    except Exception as e:
        await message.answer(f"Ошибка: {e}", reply_markup=get_main_menu(lang))


async def main():
    print("Бот запущен на локальной надежной памяти с выбором языка, режимов, фото и меню!")
    await setup_bot_commands(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
