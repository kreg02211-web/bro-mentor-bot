import os
import io
import json
import base64
import asyncio
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    BotCommand,
    BotCommandScopeChat,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
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
dp = Dispatcher(storage=MemoryStorage())
groq_client = Groq(api_key=GROQ_API_KEY)

MAX_HISTORY = 40
DB_FILE = "chat_memory.json"
WELCOME_REQUESTS = 20
DAILY_REQUESTS = 5
CHANNEL_URL = "https://t.me/bro_mentor_tg"

VALID_MODES = ("support", "bro", "mentor")
DEFAULT_MODE = "bro"

STAR_PACKS = {
    "buy_100": {"requests": 100, "stars": 150, "label": "100 запросов — 150 ⭐️"},
    "buy_200": {"requests": 200, "stars": 250, "label": "200 запросов — 250 ⭐️"},
    "buy_500": {"requests": 500, "stars": 500, "label": "500 запросов — 500 ⭐️"},
}


class OnboardingSurvey(StatesGroup):
    user_name = State()
    bot_name = State()
    interests = State()
    problems = State()


MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🌐 Язык"), KeyboardButton(text="🎭 Режимы")],
        [KeyboardButton(text="🧹 Сброс"), KeyboardButton(text="⚡️ Инфо")],
        [KeyboardButton(text="💳 Запросы"), KeyboardButton(text="🧬 Анкета")],
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

POST_ONBOARDING_MODE_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🤝 Поддержка", callback_data="onboard_mode_support")],
        [InlineKeyboardButton(text="😎 Просто бро", callback_data="onboard_mode_bro")],
        [InlineKeyboardButton(text="🎯 Наставник", callback_data="onboard_mode_mentor")],
    ]
)

BUY_REQUESTS_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="100 🧾 — 150 ⭐️", callback_data="buy_100")],
        [InlineKeyboardButton(text="200 🧾 — 250 ⭐️", callback_data="buy_200")],
        [InlineKeyboardButton(text="500 🧾 — 500 ⭐️", callback_data="buy_500")],
    ]
)


def get_channel_offer_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    if lang == "en":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📢 Join Bro Mentor Channel", url=CHANNEL_URL)],
                [InlineKeyboardButton(text="🔥 Let's chat", callback_data="channel_continue")],
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL)],
            [InlineKeyboardButton(text="🔥 Погнали в чат", callback_data="channel_continue")],
        ]
    )


def get_survey_offer_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    if lang == "en":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🚀 Yes, let's do it", callback_data="survey_yes"),
                    InlineKeyboardButton(text="⏭ No, skip to chat", callback_data="survey_no"),
                ]
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 Да, погнали", callback_data="survey_yes"),
                InlineKeyboardButton(text="⏭ Нет, сразу в чат", callback_data="survey_no"),
            ]
        ]
    )


def get_main_menu(lang: str = "ru") -> ReplyKeyboardMarkup:
    if lang == "en":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🌐 Language"), KeyboardButton(text="🎭 Modes")],
                [KeyboardButton(text="🧹 Reset"), KeyboardButton(text="⚡️ Info")],
                [KeyboardButton(text="💳 Requests"), KeyboardButton(text="🧬 Profile")],
            ],
            resize_keyboard=True,
            input_field_placeholder="Write to bro or pick a button...",
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌐 Язык"), KeyboardButton(text="🎭 Режимы")],
            [KeyboardButton(text="🧹 Сброс"), KeyboardButton(text="⚡️ Инфо")],
            [KeyboardButton(text="💳 Запросы"), KeyboardButton(text="🧬 Анкета")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напиши бро или выбери кнопку...",
    )


async def setup_bot_commands(target_bot: Bot, chat_id: int | None = None, lang: str = "ru"):
    if lang == "en":
        commands = [
            BotCommand(command="start", description="Restart and choose language"),
            BotCommand(command="profile", description="View or retake personal survey"),
            BotCommand(command="lang", description="Change language"),
            BotCommand(command="mode", description="Change chat mode"),
            BotCommand(command="reset", description="Clear recent chat history"),
            BotCommand(command="info", description="Bot status"),
        ]
    else:
        commands = [
            BotCommand(command="start", description="Перезапуск и выбор языка"),
            BotCommand(command="profile", description="Моя анкета / пройти опрос заново"),
            BotCommand(command="lang", description="Сменить язык"),
            BotCommand(command="mode", description="Сменить режим общения"),
            BotCommand(command="reset", description="Очистить историю чата"),
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
def get_today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


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


def sync_daily_quota(record: dict, today_str: str | None = None) -> tuple[dict, bool]:
    today = today_str or get_today_str()
    changed = False

    welcome_left = record.get("welcome_requests", 0)
    if not isinstance(welcome_left, int) or welcome_left < 0:
        welcome_left = 0
        changed = True

    welcome_given = bool(record.get("welcome_bonus_given", False))
    if welcome_left > 0 and not welcome_given:
        welcome_given = True
        changed = True

    daily_left = record.get("daily_requests", 0)
    if not isinstance(daily_left, int) or daily_left < 0:
        daily_left = 0
        changed = True

    last_daily_date = record.get("last_daily_date")
    if not isinstance(last_daily_date, str) or not last_daily_date:
        last_daily_date = None

    # Дневной лимит (5 на день) включается только после того, как потрачены все 20 стартовых бонусных запросов
    if welcome_left == 0 and welcome_given:
        if last_daily_date is None:
            daily_left = DAILY_REQUESTS
            last_daily_date = today
            changed = True
        elif last_daily_date != today:
            daily_left = DAILY_REQUESTS
            last_daily_date = today
            changed = True

    record["welcome_bonus_given"] = welcome_given
    record["welcome_requests"] = welcome_left
    record["daily_requests"] = daily_left
    record["last_daily_date"] = last_daily_date
    return record, changed


def normalize_user_record(raw):
    today = get_today_str()

    if isinstance(raw, list):
        clean = [
            msg for msg in raw
            if isinstance(msg, dict) and msg.get("role") in ["user", "assistant"]
        ]
        rec = {
            "lang": "ru",
            "mode": DEFAULT_MODE,
            "profile": {},
            "welcome_bonus_given": True,
            "welcome_requests": WELCOME_REQUESTS,
            "daily_requests": 0,
            "last_daily_date": None,
            "requests_balance": 0,
            "history": clean,
        }
        rec, _ = sync_daily_quota(rec, today)
        return rec

    if isinstance(raw, dict):
        lang = raw.get("lang", "ru")
        if lang not in ["ru", "en"]:
            lang = "ru"
        mode = raw.get("mode", DEFAULT_MODE)
        if mode not in VALID_MODES:
            mode = DEFAULT_MODE
        profile = raw.get("profile", {})
        if not isinstance(profile, dict):
            profile = {}

        welcome_requests = raw.get("welcome_requests")
        if not isinstance(welcome_requests, int):
            legacy_free = raw.get("free_requests")
            if isinstance(legacy_free, int):
                welcome_requests = max(0, legacy_free)
            else:
                welcome_requests = WELCOME_REQUESTS

        welcome_bonus_given = raw.get("welcome_bonus_given")
        if not isinstance(welcome_bonus_given, bool):
            welcome_bonus_given = welcome_requests < WELCOME_REQUESTS or "free_requests" in raw

        daily_requests = raw.get("daily_requests", 0)
        if not isinstance(daily_requests, int):
            daily_requests = 0

        last_daily_date = raw.get("last_daily_date")
        if not isinstance(last_daily_date, str) or not last_daily_date:
            last_daily_date = None

        requests_balance = raw.get("requests_balance", 0)
        if not isinstance(requests_balance, int):
            requests_balance = 0

        hist = raw.get("history", [])
        clean = [
            msg for msg in hist
            if isinstance(msg, dict) and msg.get("role") in ["user", "assistant"]
        ]

        rec = {
            "lang": lang,
            "mode": mode,
            "profile": profile,
            "welcome_bonus_given": welcome_bonus_given,
            "welcome_requests": welcome_requests,
            "daily_requests": daily_requests,
            "last_daily_date": last_daily_date,
            "requests_balance": requests_balance,
            "history": clean,
        }
        rec, _ = sync_daily_quota(rec, today)
        return rec

    rec = {
        "lang": "ru",
        "mode": DEFAULT_MODE,
        "profile": {},
        "welcome_bonus_given": True,
        "welcome_requests": WELCOME_REQUESTS,
        "daily_requests": 0,
        "last_daily_date": None,
        "requests_balance": 0,
        "history": [],
    }
    rec, _ = sync_daily_quota(rec, today)
    return rec


def get_user_record(user_id):
    db = load_db()
    user_str = str(user_id)
    raw = db.get(user_str)
    rec = normalize_user_record(raw)
    synced, changed = sync_daily_quota(dict(rec), get_today_str())
    if changed and isinstance(raw, dict):
        db[user_str] = synced
        save_db(db)
    return synced


def grant_first_start_bonus_if_needed(user_id) -> dict:
    db = load_db()
    user_str = str(user_id)
    current = normalize_user_record(db.get(user_str))
    if not current.get("welcome_bonus_given", False):
        current["welcome_bonus_given"] = True
        current["welcome_requests"] = WELCOME_REQUESTS
        current["daily_requests"] = 0
        current["last_daily_date"] = None
    current, _ = sync_daily_quota(current, get_today_str())
    db[user_str] = current
    save_db(db)
    return current


def get_total_messages_left(rec: dict) -> int:
    welcome_left = max(0, rec.get("welcome_requests", 0))
    daily_left = max(0, rec.get("daily_requests", 0))
    paid_left = max(0, rec.get("requests_balance", 0))
    if welcome_left > 0:
        return welcome_left + paid_left
    return daily_left + paid_left


def consume_one_message(user_id) -> tuple[bool, int]:
    db = load_db()
    user_str = str(user_id)
    current = normalize_user_record(db.get(user_str))
    current, _ = sync_daily_quota(current, get_today_str())

    welcome_left = current.get("welcome_requests", 0)
    daily_left = current.get("daily_requests", 0)
    paid_left = current.get("requests_balance", 0)

    if welcome_left > 0:
        welcome_left -= 1
        if welcome_left == 0 and current.get("last_daily_date") is None:
            current["last_daily_date"] = get_today_str()
    elif daily_left > 0:
        daily_left -= 1
    elif paid_left > 0:
        paid_left -= 1
    else:
        db[user_str] = current
        save_db(db)
        return False, 0

    current["welcome_requests"] = welcome_left
    current["daily_requests"] = daily_left
    current["requests_balance"] = paid_left
    db[user_str] = current
    save_db(db)
    return True, get_total_messages_left(current)


def append_messages_footer(reply_text: str, left_count: int, lang: str) -> str:
    if lang == "en":
        footer = f"\n\nMessages left: <b>{left_count}</b>"
    else:
        footer = f"\n\nОсталось сообщений: <b>{left_count}</b>"
    return f"{reply_text}{footer}"


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
    current = normalize_user_record(db.get(user_str))
    clean = [
        msg for msg in history
        if isinstance(msg, dict) and msg.get("role") in ["user", "assistant"]
    ]
    current["history"] = clean
    db[user_str] = current
    save_db(db)
    print(f"💾 Память сохранена для {user_id}: всего сообщений -> {len(clean)}")


def save_user_profile(user_id, profile_data: dict):
    db = load_db()
    user_str = str(user_id)
    current = normalize_user_record(db.get(user_str))
    current["profile"] = profile_data
    db[user_str] = current
    save_db(db)
    print(f"🧬 Вечный профиль сохранён для {user_id}: {profile_data}")


def add_user_requests(user_id, amount: int) -> int:
    db = load_db()
    user_str = str(user_id)
    current = normalize_user_record(db.get(user_str))
    new_balance = current.get("requests_balance", 0) + amount
    current["requests_balance"] = new_balance
    db[user_str] = current
    save_db(db)
    print(f"🧾 Баланс запросов для {user_id} пополнен на +{amount}: теперь {new_balance}")
    return new_balance


def get_user_lang(user_id):
    return get_user_record(user_id).get("lang", "ru")


def set_user_lang(user_id, lang):
    if lang not in ["ru", "en"]:
        lang = "ru"
    db = load_db()
    user_str = str(user_id)
    current = normalize_user_record(db.get(user_str))
    current["lang"] = lang
    db[user_str] = current
    save_db(db)
    print(f"🌐 Язык для {user_id} изменён на: {lang}")


def get_user_mode(user_id):
    return get_user_record(user_id).get("mode", DEFAULT_MODE)


def set_user_mode(user_id, mode):
    if mode not in VALID_MODES:
        mode = DEFAULT_MODE
    db = load_db()
    user_str = str(user_id)
    current = normalize_user_record(db.get(user_str))
    current["mode"] = mode
    db[user_str] = current
    save_db(db)
    print(f"🎭 Режим для {user_id} изменён на: {mode}")
def build_system_prompt(lang: str, mode: str = DEFAULT_MODE, profile: dict | None = None) -> str:
    profile = profile or {}
    user_name = profile.get("user_name", "").strip()
    bot_name = profile.get("bot_name", "").strip()
    interests = profile.get("interests", "").strip()
    problems = profile.get("problems", "").strip()

    if lang == "en":
        effective_bot_name = bot_name if bot_name else "Gauter"
        base = (
            f"You are {effective_bot_name}, an older bro and real mentor. Keep it raw, grounded, and natural — "
            "no cringey roleplay or stiff AI tone. STRUCTURE: write strictly 3 paragraphs of about 5-6 lines each, "
            "and at the very bottom add 1 short natural closing side-note line tailored strictly to the specific topic "
            "of the current conversation — NEVER repeat a canned phrase, NEVER write words like 'Conclusion', 'Summary', "
            "'Takeaway', or 'TL;DR', and NEVER use asterisks (**) or markdown formatting. "
            "Use relevant emojis naturally where they fit (fire, weights, skulls, rockets), and avoid lists or headers. "
            "Always reply strictly in English."
        )
        profile_lines = []
        if bot_name:
            profile_lines.append(f"Your name in this chat is '{bot_name}'.")
        if user_name:
            profile_lines.append(
                f"The user wants to be called '{user_name}' — use this name naturally in conversation, "
                "but do not force it into every single sentence."
            )
        if interests or problems:
            profile_lines.append(
                "Background info from the user's profile (keep in memory, NEVER bring up unprompted "
                "on casual greetings or unrelated messages; only mention or use it when relevant to the "
                "topic or when the user asks/brings it up):"
            )
            if interests:
                profile_lines.append(f"Interests/hobbies: {interests}.")
            if problems:
                profile_lines.append(f"Goals/struggles: {problems}.")

        profile_block = (" " + " ".join(profile_lines)) if profile_lines else ""

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
        return base + profile_block + mode_focus.get(mode, mode_focus[DEFAULT_MODE])

    effective_bot_name = bot_name if bot_name else "Гаутер"
    base = (
        f"Ты — {effective_bot_name}, старший кореш и бро. Живой пацан, без шизы, ботов и ролевых игр. "
        "ОБЩЕНИЕ КАК НАДО: Пиши живо и по делу, в стиле разговора двух реальных корешей. "
        "СТРУКТУРА ОТВЕТА: ОБЯЗАТЕЛЬНО делай ровно 3 абзаца примерно по 5-6 строк каждый, "
        "а в самом конце добавляй 1 короткую живую строку-сноску строго по контексту текущего разговора — "
        "каждый раз уникальную и по теме того, что только что обсуждали. "
        "НИКОГДА не пиши слова 'Вывод', 'Итог', 'Резюме' или похожие ярлыки, и НИКОГДА не используй звёздочки (**). "
        "Насыпай к месту живые эмодзи (огонь, дым, черепа, бро, ракеты). "
        "Никаких списков, заголовков, звёздочек и решёток. Отвечай строго на русском языке."
    )
    profile_lines = []
    if bot_name:
        profile_lines.append(f"Твоё имя в этом чате — «{bot_name}».")
    if user_name:
        profile_lines.append(
            f"Пользователя зовут «{user_name}» — обращайся к нему по этому имени естественно, "
            "но не пихай его в каждую фразу насильно."
        )
    if interests or problems:
        profile_lines.append(
            "Фоновая инфа из анкеты пользователя (храни в памяти, НЕ вываливай без повода на "
            "обычное приветствие или левые темы; поднимай и учитывай только когда это реально в тему "
            "разговора или когда пользователь сам спросит/напомнит):"
        )
        if interests:
            profile_lines.append(f"Увлечения: {interests}.")
        if problems:
            profile_lines.append(f"Цели/проблемы: {problems}.")

    profile_block = (" " + " ".join(profile_lines)) if profile_lines else ""

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
    return base + profile_block + mode_focus.get(mode, mode_focus[DEFAULT_MODE])


ACTIVE_MODEL = "openai/gpt-oss-120b"
VISION_MODEL = "qwen/qwen3.8-27b"
print(f"Подключена модель: {ACTIVE_MODEL} | Vision: {VISION_MODEL}")


def get_mode_selection_prompt(lang: str, user_name: str = "") -> str:
    if lang == "en":
        call_name = user_name if user_name else "bro"
        return (
            f"Almost there, {call_name}! 🎭 Pick the mode you want to start in:\n\n"
            f"🤝 <b>Support</b> — calm backup, take the pressure off, talk things through\n"
            f"😎 <b>Just bro</b> — chill real talk, life, training, banter\n"
            f"🎯 <b>Mentor</b> — direct focus, discipline, clear next steps"
        )
    call_name = user_name if user_name else "бро"
    return (
        f"Почти всё, {call_name}! 🎭 Выбери режим, с которого начнём:\n\n"
        f"🤝 <b>Поддержка</b> — выдохнуть, снять груз и поговорить без давления\n"
        f"😎 <b>Просто бро</b> — живой базар за жизнь, движ и идеи на равных\n"
        f"🎯 <b>Наставник</b> — жёсткий фокус, дисциплина и чёткие шаги по делу"
    )


def get_base_welcome_text(lang: str, mode_label: str, user_name: str = "") -> str:
    if lang == "en":
        call_name = user_name if user_name else "bro"
        return (
            f"Yo, {call_name}! ❤️ Locked in. 🚀 Active mode: <b>{mode_label}</b>.\n"
            f"What's good — tell me what's on your mind, training, or plans and let's break it down. 🔥"
        )
    call_name = user_name if user_name else "бро"
    return (
        f"Здорова, {call_name}! ❤️ На связи. 🚀 Выбран режим: <b>{mode_label}</b>.\n"
        f"Че как, рассказывай подробно, какие мысли в голове крутятся, давай перетрем за жизнь и планы. 🔥"
    )


@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    grant_first_start_bonus_if_needed(message.from_user.id)
    save_history(message.from_user.id, [])
    await message.answer(
        "🌐 Выбери язык / Choose language:",
        reply_markup=START_LANG_KEYBOARD,
    )


@dp.callback_query(F.data.in_({"start_lang_ru", "start_lang_en"}))
async def process_start_lang_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = "en" if callback.data == "start_lang_en" else "ru"
    set_user_lang(callback.from_user.id, lang)
    await setup_bot_commands(bot, chat_id=callback.message.chat.id, lang=lang)

    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass

    if lang == "en":
        offer_text = (
            "Yo! Before we dive in — wanna take a quick, chill 4-question survey so our chats feel more personal? 🎯\n\n"
            "You'll tell me what to call you, pick my name, and share your hobbies & struggles. "
            "I'll keep it locked in my memory so I only bring up details when they actually fit the talk. 🔥"
        )
    else:
        offer_text = (
            "Здорова! Слушай, перед тем как залетать в чат — не хочешь пройти быстрый, непринуждённый опрос из 4 вопросов, чтобы общение было ещё кайфовее? 🎯\n\n"
            "Напишешь, как тебя звать, как называть меня, а также свои увлечения и проблемы. "
            "Я сохраню это в памяти навеки, но без лишних вбросов — буду поднимать по делу или когда сам спросишь. 🔥"
        )
    await callback.message.answer(offer_text, reply_markup=get_survey_offer_keyboard(lang))


@dp.callback_query(F.data == "survey_no")
async def process_survey_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    rec = get_user_record(callback.from_user.id)
    lang = rec.get("lang", "ru")
    user_name = (rec.get("profile") or {}).get("user_name", "")

    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        get_mode_selection_prompt(lang, user_name),
        reply_markup=POST_ONBOARDING_MODE_KEYBOARD,
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "survey_yes")
async def process_survey_yes(callback: CallbackQuery, state: FSMContext):
    lang = get_user_lang(callback.from_user.id)
    await state.set_state(OnboardingSurvey.user_name)

    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass

    if lang == "en":
        q1 = "🔥 <b>Question 1/4:</b> How should I call you?"
    else:
        q1 = "🔥 <b>Вопрос 1/4:</b> Как мне тебя называть?"
    await callback.message.answer(q1, parse_mode="HTML")


@dp.message(OnboardingSurvey.user_name, F.text)
async def survey_step_user_name(message: Message, state: FSMContext):
    lang = get_user_lang(message.from_user.id)
    await state.update_data(user_name=message.text.strip())
    await state.set_state(OnboardingSurvey.bot_name)

    if lang == "en":
        q2 = "😎 <b>Question 2/4:</b> How would you like to call me (the bot)?"
    else:
        q2 = "😎 <b>Вопрос 2/4:</b> Как бы ты хотел называть меня (бота)?"
    await message.answer(q2, parse_mode="HTML")


@dp.message(OnboardingSurvey.bot_name, F.text)
async def survey_step_bot_name(message: Message, state: FSMContext):
    lang = get_user_lang(message.from_user.id)
    await state.update_data(bot_name=message.text.strip())
    await state.set_state(OnboardingSurvey.interests)

    if lang == "en":
        q3 = "🚀 <b>Question 3/4:</b> What are your hobbies and interests?"
    else:
        q3 = "🚀 <b>Вопрос 3/4:</b> Какие у тебя увлечения и интересы?"
    await message.answer(q3, parse_mode="HTML")


@dp.message(OnboardingSurvey.interests, F.text)
async def survey_step_interests(message: Message, state: FSMContext):
    lang = get_user_lang(message.from_user.id)
    await state.update_data(interests=message.text.strip())
    await state.set_state(OnboardingSurvey.problems)

    if lang == "en":
        q4 = "🎯 <b>Question 4/4:</b> What problems, challenges, or goals are on your mind right now?"
    else:
        q4 = "🎯 <b>Вопрос 4/4:</b> Какие у тебя сейчас проблемы, затыки или цели?"
    await message.answer(q4, parse_mode="HTML")


@dp.message(OnboardingSurvey.problems, F.text)
async def survey_step_problems(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)

    data = await state.get_data()
    profile_data = {
        "user_name": data.get("user_name", ""),
        "bot_name": data.get("bot_name", ""),
        "interests": data.get("interests", ""),
        "problems": message.text.strip(),
    }
    save_user_profile(user_id, profile_data)
    await state.clear()

    if lang == "en":
        saved_note = (
            f"Got it, <b>{profile_data['user_name']}</b>! 🧬🔥\n"
            f"I've locked your profile in memory — I'll bring up details only when relevant or when you ask."
        )
    else:
        saved_note = (
            f"Принято, <b>{profile_data['user_name']}</b>! 🧬🔥\n"
            f"Сохранил твою анкету в памяти навеки — буду поднимать детали только по делу или когда сам спросишь."
        )
    await message.answer(saved_note, parse_mode="HTML")
    await message.answer(
        get_mode_selection_prompt(lang, profile_data["user_name"]),
        reply_markup=POST_ONBOARDING_MODE_KEYBOARD,
        parse_mode="HTML",
    )


@dp.callback_query(F.data.in_({"onboard_mode_support", "onboard_mode_bro", "onboard_mode_mentor"}))
async def process_onboard_mode_callback(callback: CallbackQuery):
    mode_map = {
        "onboard_mode_support": "support",
        "onboard_mode_bro": "bro",
        "onboard_mode_mentor": "mentor",
    }
    selected_mode = mode_map[callback.data]
    user_id = callback.from_user.id
    set_user_mode(user_id, selected_mode)

    lang = get_user_lang(user_id)
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass

    if lang == "en":
        offer_text = (
            "Mode locked in! 🔥 Before we jump into the chat, subscribe to the channel — "
            "updates, drops, and real talk live there:\n"
            f"{CHANNEL_URL}"
        )
    else:
        offer_text = (
            "Режим включил! 🔥 Перед стартом в чате залетай в канал — там обновы, движ и разборы по делу:\n"
            f"{CHANNEL_URL}"
        )
    await callback.message.answer(offer_text, reply_markup=get_channel_offer_keyboard(lang))


@dp.callback_query(F.data == "channel_continue")
async def process_channel_continue_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    rec = get_user_record(user_id)
    lang = rec.get("lang", "ru")
    mode_label = get_mode_label(rec.get("mode", DEFAULT_MODE), lang)
    user_name = (rec.get("profile") or {}).get("user_name", "")

    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass

    welcome_text = get_base_welcome_text(lang, mode_label, user_name)
    await callback.message.answer(welcome_text, reply_markup=get_main_menu(lang), parse_mode="HTML")
    @dp.message(F.text.in_({"/profile", "🧬 Анкета", "🧬 Profile"}))
    async def cmd_profile(message: Message, state: FSMContext):
        await state.clear()
    rec = get_user_record(message.from_user.id)
    lang = rec.get("lang", "ru")
    profile = rec.get("profile") or {}

    if not profile:
        text = (
            "Анкета ещё не заполнена. Хочешь пройти мини-опрос сейчас? 🎯"
            if lang == "ru"
            else "Profile isn't filled out yet. Wanna take the quick survey now? 🎯"
        )
        await message.answer(text, reply_markup=get_survey_offer_keyboard(lang))
        return

    retake_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Пройти заново" if lang == "ru" else "🔄 Retake survey",
                    callback_data="survey_yes",
                )
            ]
        ]
    )

    if lang == "en":
        text = (
            f"<b>🧬 Your Saved Profile:</b>\n\n"
            f"👤 Name: <b>{profile.get('user_name', '-')}</b>\n"
            f"🤖 Bot name: <b>{profile.get('bot_name', '-')}</b>\n"
            f"🚀 Interests: <b>{profile.get('interests', '-')}</b>\n"
            f"🎯 Problems / Goals: <b>{profile.get('problems', '-')}</b>"
        )
    else:
        text = (
            f"<b>🧬 Твоя анкета:</b>\n\n"
            f"👤 Имя: <b>{profile.get('user_name', '-')}</b>\n"
            f"🤖 Имя бота: <b>{profile.get('bot_name', '-')}</b>\n"
            f"🚀 Увлечения: <b>{profile.get('interests', '-')}</b>\n"
            f"🎯 Проблемы / Цели: <b>{profile.get('problems', '-')}</b>"
        )
    await message.answer(text, reply_markup=retake_kb, parse_mode="HTML")


@dp.message(F.text.in_({"/reset", "🧹 Сброс", "🧹 Reset"}))
async def cmd_reset(message: Message, state: FSMContext):
    await state.clear()
    rec = get_user_record(message.from_user.id)
    lang = rec.get("lang", "ru")
    user_name = (rec.get("profile") or {}).get("user_name", "")
    save_history(message.from_user.id, [])

    if lang == "en":
        call_name = f", {user_name}" if user_name else ", bro"
        text = f"Chat history wiped clean{call_name} (your saved profile stays intact). 🌑"
    else:
        call_name = f", {user_name}" if user_name else ", бро"
        text = f"История чата очищена{call_name} (анкета в памяти сохранена, ничего не забыл). 🌑"
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
    rec = get_user_record(message.from_user.id)
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
    rec = get_user_record(user_id)
    lang = rec.get("lang", "ru")
    mode = rec.get("mode", DEFAULT_MODE)
    history = rec.get("history", [])
    profile = rec.get("profile") or {}
    messages_left = get_total_messages_left(rec)
    lang_label = "English 🇬🇧" if lang == "en" else "Русский 🇷🇺"
    mode_label = get_mode_label(mode, lang)
    msg_count = len(history)
    if lang == "en":
        profile_status = "✅ Saved" if profile else "❌ Not filled"
        text = (
            f"<b>Bro Mentor Status</b> 🔥\n"
            f"Language: <b>{lang_label}</b>\n"
            f"Mode: <b>{mode_label}</b>\n"
            f"Profile memory: <b>{profile_status}</b>\n"
            f"Messages left: <b>{messages_left}</b>\n"
            f"Saved messages in memory: <b>{msg_count}/{MAX_HISTORY}</b>"
        )
    else:
        profile_status = "✅ Сохранена" if profile else "❌ Не заполнена"
        text = (
            f"<b>Статус Bro Mentor</b> 🔥\n"
            f"Язык: <b>{lang_label}</b>\n"
            f"Режим: <b>{mode_label}</b>\n"
            f"Анкета в памяти: <b>{profile_status}</b>\n"
            f"Осталось сообщений: <b>{messages_left}</b>\n"
            f"Сообщений в памяти: <b>{msg_count}/{MAX_HISTORY}</b>"
        )
    await message.answer(text, reply_markup=get_main_menu(lang), parse_mode="HTML")


@dp.message(F.text.in_({"💳 Запросы", "💳 Requests"}))
async def cmd_buy_requests(message: Message):
    rec = get_user_record(message.from_user.id)
    lang = rec.get("lang", "ru")
    messages_left = get_total_messages_left(rec)
    if lang == "en":
        text = (
            f"Messages left: <b>{messages_left}</b>\n"
            f"⭐️ Choose a request pack in Telegram Stars:"
        )
    else:
        text = (
            f"Осталось сообщений: <b>{messages_left}</b>\n"
            f"⭐️ Выбери пакет запросов в Telegram Stars:"
        )
    await message.answer(text, reply_markup=BUY_REQUESTS_KEYBOARD, parse_mode="HTML")


@dp.callback_query(F.data.in_({"buy_100", "buy_200", "buy_500"}))
async def process_buy_requests_callback(callback: CallbackQuery):
    lang = get_user_lang(callback.from_user.id)
    pack = STAR_PACKS[callback.data]
    await callback.answer(f"{pack['stars']} ⭐️")

    if lang == "en":
        title = f"{pack['requests']} Bro Mentor Requests"
        description = f"Top up your balance with {pack['requests']} messages/photo analyses."
        price_label = f"{pack['requests']} requests"
    else:
        title = f"{pack['requests']} запросов Bro Mentor"
        description = f"Пополнение баланса на {pack['requests']} сообщений или разборов фото."
        price_label = f"{pack['requests']} запросов"

    await callback.message.answer_invoice(
        title=title,
        description=description,
        payload=f"pack_{pack['requests']}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=price_label, amount=pack["stars"])],
    )


@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    added_requests = int(payload.split("_")[1])
    user_id = message.from_user.id
    lang = get_user_lang(user_id)

    new_balance = add_user_requests(user_id, added_requests)
    messages_left = get_total_messages_left(get_user_record(user_id))
    print(
        f"💰 Оплата Stars от {user_id}: +{added_requests} запросов "
        f"(платный баланс: {new_balance}, всего доступно: {messages_left}) | ID: {payment.telegram_payment_charge_id}"
    )

    if lang == "en":
        text = (
            f"Payment received! ⭐️🔥 Added <b>+{added_requests} requests</b>.\n"
            f"Messages left: <b>{messages_left}</b>"
        )
    else:
        text = (
            f"Оплата прошла! ⭐️🔥 Начислил <b>+{added_requests} запросов</b>.\n"
            f"Осталось сообщений: <b>{messages_left}</b>"
        )
    await message.answer(text, reply_markup=get_main_menu(lang), parse_mode="HTML")


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
    rec = get_user_record(user_id)
    lang = rec.get("lang", "ru")
    mode = rec.get("mode", DEFAULT_MODE)
    profile = rec.get("profile", {})
    history = list(rec.get("history", []))

    allowed, left_after = consume_one_message(user_id)
    if not allowed:
        no_req_text = (
            "Сообщения закончились! Выбери пакет в звёздах, чтобы продолжить:"
            if lang == "ru"
            else "You're out of messages! Pick a Star pack to keep going:"
        )
        await message.answer(no_req_text, reply_markup=BUY_REQUESTS_KEYBOARD)
        return

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

        system_prompt = build_system_prompt(lang, mode, profile)
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
            max_tokens=850,
        )
        reply = response.choices[0].message.content or ""

        history_note = f"[Фото: {caption}]" if caption else "[Фото без подписи]"
        history.append({"role": "user", "content": history_note})
        history.append({"role": "assistant", "content": reply})
        history = history[-MAX_HISTORY:]
        save_history(user_id, history)

        final_reply = append_messages_footer(reply, left_after, lang)
        await message.answer(final_reply, reply_markup=get_main_menu(lang), parse_mode="HTML")
    except Exception as e:
        await message.answer(f"Ошибка при разборе фото: {e}", reply_markup=get_main_menu(lang))


@dp.message(F.text)
async def chat_with_ai(message: Message):
    user_id = message.from_user.id
    rec = get_user_record(user_id)
    lang = rec.get("lang", "ru")
    mode = rec.get("mode", DEFAULT_MODE)
    profile = rec.get("profile", {})
    history = list(rec.get("history", []))

    allowed, left_after = consume_one_message(user_id)
    if not allowed:
        no_req_text = (
            "Сообщения закончились! Выбери пакет в звёздах, чтобы продолжить:"
            if lang == "ru"
            else "You're out of messages! Pick a Star pack to keep going:"
        )
        await message.answer(no_req_text, reply_markup=BUY_REQUESTS_KEYBOARD)
        return

    history.append({"role": "user", "content": message.text})
    history = history[-MAX_HISTORY:]

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        system_prompt = build_system_prompt(lang, mode, profile)
        messages_payload = [{"role": "system", "content": system_prompt}] + history
        response = groq_client.chat.completions.create(
            model=ACTIVE_MODEL,
            messages=messages_payload,
            temperature=0.5,
            max_tokens=850,
        )
        reply = response.choices[0].message.content or ""

        history.append({"role": "assistant", "content": reply})
        history = history[-MAX_HISTORY:]
        save_history(user_id, history)

        final_reply = append_messages_footer(reply, left_after, lang)
        await message.answer(final_reply, reply_markup=get_main_menu(lang), parse_mode="HTML")
    except Exception as e:
        await message.answer(f"Ошибка: {e}", reply_markup=get_main_menu(lang))


async def main():
    print("Бот запущен на локальной надежной памяти с выбором языка, режимов, фото, анкетой и меню!")
    await setup_bot_commands(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
