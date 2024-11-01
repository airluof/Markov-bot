# coding: utf-8

import asyncio
from datetime import datetime
import json
import os
import random
import re
import time
import io

import aiofiles
import aiogram
import dateparser
import dotenv
import markovify
from aiogram import Dispatcher, types
from aiogram.types import InputFile
from PIL import Image, ImageDraw, ImageFont
from loguru import logger

from middleware import BotMessagesMiddleware
from mem import populate_base  # Импорт функции для инициализации базы

dotenv.load_dotenv()

BOT = aiogram.Bot(
    os.environ["TOKEN"],
    parse_mode=aiogram.types.ParseMode.HTML
)
DP = Dispatcher(BOT)

USER_BASE = {}

async def onBotStart(dp: Dispatcher) -> None:
    global USER_BASE
    logger.info("Бот запущен!")
    USER_BASE = await load_db()

async def load_db(folder="db"):
    # Загрузка базы данных
    dict_to_return = {}
    for filename in os.listdir(folder):
        if filename.endswith(".jsonc"):
            async with aiofiles.open(os.path.join(folder, filename), 'r', encoding='utf-8') as file:
                contents = await file.read()
                dict_to_return[filename[:-6]] = json.loads(contents)
    return dict_to_return

async def save_db(folder="db"):
    for chat_id, data in USER_BASE.items():
        async with aiofiles.open(os.path.join(folder, f"{chat_id}.jsonc"), 'w', encoding='utf-8') as file:
            await file.write(json.dumps(data, ensure_ascii=False))

DP.middleware.setup(BotMessagesMiddleware(populate_base))

@DP.message_handler(commands=["start"])
async def hello_handler(msg: types.Message):
    await msg.answer("Отлично! 😊\n\nЧто бы я работал, тебе нужно выдать мне права администратора. 🫂")

@DP.chat_join_request_handler()
@DP.message_handler(content_types=["new_chat_members", "group_chat_created", "supergroup_chat_created"])
async def chat_join_handler(msg: types.Message):
    bot_id = (await BOT.get_me()).id
    if not any([i for i in msg.new_chat_members if i.id == bot_id]):
        return
    await msg.answer("<b>Привет! 🙋</b>\n\nСпасибо за то что добавил меня к себе в беседу.\nДля моей работы выдай мне права администратора.")

@DP.message_handler(commands=["stats", "statistics", "stat"])
async def stats_handler(msg: types.Message):
    await msg.answer(f"<b>Статистика ℹ️</b>\n\nВ базе данных этой группы хранится <code>{len(USER_BASE[str(msg.chat.id)]['Messages'])}</code> сообщений.")

async def check_admin(msg: types.Message):
    if not (await BOT.get_chat_member(msg.chat.id, msg.from_user.id)).is_chat_admin():
        await msg.answer("⚠️ Данную команду могут использовать только <b>администраторы чата</b>.")
        return False
    return True

@DP.message_handler(commands=["disable", "turn_off", "turnoff", "off"])
async def disable_handler(msg: types.Message):
    if not await check_admin(msg):
        return

    args = (msg.get_args() or "")
    disabled_seconds = 0 

    parsed = dateparser.parse(args) if args else None
    if parsed:
        disabled_seconds = (parsed.timestamp() - datetime.now().timestamp())
    else:
        disabled_seconds = 7 * 24 * 60 * 60  # по умолчанию 7 дней

    if disabled_seconds < 120:  # минимум 2 минуты
        await msg.answer("Пожалуйста, укажи время, на которое нужно отключить генерацию сообщений.")
        return

    await msg.answer(f"Окей, я отключу генерацию сообщений на <code>{seconds_to_userfriendly_string(disabled_seconds)}</code>.")
    update_record(msg.chat.id, {"OffUntil": int(time.time()) + int(disabled_seconds)})

@DP.message_handler(commands=["enable", "turn_on", "turnon", "on"])
async def enable_handler(msg: types.Message):
    if not await check_admin(msg):
        return

    update_record(msg.chat.id, {"OffUntil": 0})
    await msg.answer("Окей, теперь я снова могу генерировать сообщения! 🙂")

@DP.message_handler()
async def message_handler(msg: types.Message):
    message_text = msg.text or msg.caption
    add_database_message(msg.chat.id, message_text)

    if USER_BASE[str(msg.chat.id)]["OffUntil"] > int(time.time()):
        return

    is_triggered = any([i for i in ["макс", "max", "@maxzens_bot"] if i in message_text.lower()])
    if msg.reply_to_message and not is_triggered:
        is_triggered = msg.reply_to_message.from_user.id == BOT.id

    if random.randint(1, 100) > (50 if is_triggered else 20):
        return

    model = markovify.NewlineText("\n".join(USER_BASE[str(msg.chat.id)]["Messages"]).lower())
    msg_generated = model.make_sentence(tries=10) if (random.randint(0, 2) == 2) else model.make_short_sentence(50, tries=100)

    if not msg_generated and random.randint(0, 1):
        msg_generated = random.choice(USER_BASE[str(msg.chat.id)]["Messages"])

    if msg_generated:
        msg_generated = re.sub(r"@(\w*)", "<i><a href=\"https://t.me/\\1\">@\\1</a></i>", msg_generated)
        await asyncio.sleep(random.uniform(0, 1))
        await msg.bot.send_chat_action(msg.chat.id, "typing")
        await asyncio.sleep(random.uniform(1, 3))

        if random.randint(0, 1):
            await msg.answer(msg_generated, disable_notification=True)
        else:
            await msg.reply(msg_generated, disable_notification=True)

def seconds_to_userfriendly_string(seconds):
    # Функция для преобразования секунд в человекочитаемый формат
    seconds = int(seconds)
    if seconds < 0:
        seconds = -seconds
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days: parts.append(f"{days} дн." if days > 1 else "1 дн.")
    if hours: parts.append(f"{hours} ч." if hours > 1 else "1 ч.")
    if minutes: parts.append(f"{minutes} мин." if minutes > 1 else "1 мин.")
    if seconds: parts.append(f"{seconds} сек." if seconds > 1 else "1 сек.")
    return ", ".join(parts)

def add_database_message(chat_id: int, message_text: str):
    message_text = message_text.strip()
    if not message_text:
        return

    if str(chat_id) not in USER_BASE:
        USER_BASE[str(chat_id)] = {"Messages": [], "OffUntil": 0}

    USER_BASE[str(chat_id)]["Messages"].append(message_text)

def update_record(chat_id: int, new_value: dict):
    if str(chat_id) not in USER_BASE:
        USER_BASE[str(chat_id)] = {}
    USER_BASE[str(chat_id)].update(new_value)

async def bg_saver():
    while True:
        await asyncio.sleep(60)  # Сохранять базу раз в минуту
        await save_db()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    os.makedirs("db", exist_ok=True)

    loop.create_task(bg_saver())
    aiogram.utils.executor.start_polling(
        dispatcher=DP,
        on_startup=onBotStart,
        skip_updates=True,
        loop=loop,
    )
