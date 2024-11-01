# coding: utf-8

import asyncio
from datetime import datetime
import json
import os
import random
import re
import time
from typing import cast
import io

import aiofiles
import aiogram
import dateparser
import dotenv
import markovify
from aiogram import Dispatcher
from aiogram.types import Message as MessageType, InputFile
from PIL import Image, ImageDraw, ImageFont
from loguru import logger

from middleware import BotMessagesMiddleware

dotenv.load_dotenv()

BOT = aiogram.Bot(
    os.environ["TOKEN"],
    parse_mode=aiogram.types.ParseMode.HTML
)
DP = Dispatcher(BOT)

USER_BASE = {}

@DP.message_handler(commands=["start"])
async def hello_handler(msg: MessageType):
    await msg.answer("Отлично! 😊\n\nЧто бы я работал, тебе нужно выдать мне права администратора. 🫂\nПосле выдачи я сумею работать как положено 👀")

@DP.chat_join_request_handler()
@DP.message_handler(content_types=["new_chat_members", "group_chat_created", "supergroup_chat_created"])
async def chat_join_handler(msg: MessageType):
    bot_id = (await BOT.get_me()).id
    if not any([i for i in msg.new_chat_members if i.id == bot_id]):
        return
    await msg.answer("<b>Привет! 🙋</b>\n\nСпасибо за то что добавил меня к себе в беседу.\nДля моей работы выдай мне права администратора.")

@DP.message_handler(commands=["stats", "statistics", "stat"])
async def stats_handler(msg: MessageType):
    await msg.answer(f"<b>Статистика ℹ️</b>\n\nВ базе данных этой группы хранится <code>{len(USER_BASE[str(msg.chat.id)]['Messages'])}</code> сообщений.")

async def check_admin(msg: MessageType):
    if not (await BOT.get_chat_member(msg.chat.id, msg.from_user.id)).is_chat_admin():
        await msg.answer("⚠️ Данную команду могут использовать только <b>администраторы чата</b>.")
        return False
    return True

@DP.message_handler(commands=["disable", "turn_off", "turnoff", "off"])
async def disable_handler(msg: MessageType):
    if not await check_admin(msg):
        return

    args = (msg.get_args() or "")
    disabled_seconds = 0 

    parsed = None
    if args:
        parsed = dateparser.parse(args)
    else:
        disabled_seconds = 7 * 24 * 60 * 60

    if parsed:
        disabled_seconds = (datetime.now().timestamp() - parsed.timestamp())

    if disabled_seconds < 2 * 60:
        await msg.answer(f"Пожалуйста, укажи время на которое нужно выключить генерацию сообщений. Указанное тобою значение (<code>{seconds_to_userfriendly_string(disabled_seconds)}</code>) уж слишком мало.\n\nПример: <code>/disable 5 часов</code>")
        return

    await msg.answer(f"Окей, я отключу генерацию сообщений в этой беседе на <code>{seconds_to_userfriendly_string(disabled_seconds)}</code>.\n\nℹ️ Администраторы могут меня включить, прописав команду /enable.")
    update_record(
        msg.chat.id,
        {
            "OffUntil": int(time.time()) + int(disabled_seconds)
        }
    )

@DP.message_handler(commands=["enable", "turn_on", "turnon", "on"])
async def enable_handler(msg: MessageType):
    if not await check_admin(msg):
        return

    await msg.answer(
        "Окей, теперь я снова могу генерировать сообщения! 🙂"
        if USER_BASE[str(msg.chat.id)]["OffUntil"] else
        "Дятел! Я и так включён, так как не был отключён администраторами беседы до этого."
    )

    update_record(
        msg.chat.id,
        {
            "OffUntil": 0
        }
    )

@DP.message_handler()
async def message_handler(msg: MessageType):
    message_text = msg.text or msg.caption
    add_database_message(
        msg.chat.id,
        message_text
    )

    if USER_BASE[str(msg.chat.id)]["OffUntil"] > int(time.time()) and USER_BASE[str(msg.chat.id)]["OffUntil"]:
        return

    is_triggered = any([i for i in ["макс", "max", "@maxzens_bot"] if i in message_text.lower()])

    if msg.reply_to_message and not is_triggered:
        is_triggered = msg.reply_to_message.from_user.id == BOT.id

    if random.randint(1, 100) > (80 if is_triggered else 8):
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
            await msg.answer(msg_generated, disable_notification=True, allow_sending_without_reply=True, disable_web_page_preview=True)
        else:
            await msg.reply(msg_generated, disable_notification=True, allow_sending_without_reply=True, disable_web_page_preview=True)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    os.makedirs("db", exist_ok=True)

    DP.middleware.setup(
        BotMessagesMiddleware(populate_base)
    )

    loop.create_task(bg_saver())
    aiogram.utils.executor.start_polling(
        dispatcher=DP,
        on_startup=onBotStart,
        skip_updates=True,
        loop=loop,
    )
