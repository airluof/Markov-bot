# coding: utf-8

import asyncio
from datetime import datetime
import json
import os
import random
import re
import time
from typing import cast
from PIL import Image, ImageDraw, ImageFont

import aiofiles
import aiogram
import dateparser
import dotenv
import markovify
from aiogram import Dispatcher
from aiogram.types import Message as MessageType
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
    await msg.answer("Отлично! 😊\n\nЧто бы я работал, тебе нужно выдать мне права администратора. 🫂\nПосле выдачи я смогу работать как положено 👀")

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
    parsed = dateparser.parse(args) if args else None
    if parsed:
        disabled_seconds = (datetime.now().timestamp() - parsed.timestamp())
    else:
        disabled_seconds = 7 * 24 * 60 * 60

    if disabled_seconds < 2 * 60:
        await msg.answer(f"Пожалуйста, укажи время на которое нужно выключить генерацию сообщений. Указанное тобою значение (<code>{seconds_to_userfriendly_string(disabled_seconds)}</code>) уж слишком мало.\n\nПример: <code>/disable 5 часов</code>")
        return

    await msg.answer(f"Окей, я отключу генерацию сообщений в этой беседе на <code>{seconds_to_userfriendly_string(disabled_seconds)}</code>.\n\nℹ️ Администраторы могут меня включить, прописав команду /enable.")
    update_record(msg.chat.id, {"OffUntil": int(time.time()) + int(disabled_seconds)})

@DP.message_handler(commands=["enable", "turn_on", "turnon", "on"])
async def enable_handler(msg: MessageType):
    if not await check_admin(msg):
        return

    await msg.answer(
        "Окей, теперь я снова могу генерировать сообщения! 🙂"
        if USER_BASE[str(msg.chat.id)]["OffUntil"] else
        "Я и так включён, так как не был отключён администраторами беседы до этого."
    )
    update_record(msg.chat.id, {"OffUntil": 0})

async def onBotStart(dp: aiogram.Dispatcher) -> None:
    global USER_BASE
    logger.info("Привет, мир!")
    USER_BASE = await load_db()

async def bg_saver():
    while True:
        await asyncio.sleep(1)
        try:
            await save_db()
        except Exception as error:
            logger.error(f"Ошибка при сохранении базы в файл: {error}")

def seconds_to_userfriendly_string(seconds, max=2):
    seconds = int(seconds)
    if seconds < 0: seconds = -seconds
    string = []
    values = [60, 3600, 86400, 604800]
    stringslocal = [["неделя","недели","недель"],["день","дня","дней"],["час","часа","часов"],["минута","минуты","минут"]]
    
    for value, local in zip(values, stringslocal):
        if seconds >= value:
            count = seconds // value
            seconds %= value
            string.append(f"{count} {local[1 if count % 10 == 1 and count % 100 != 11 else 2 if 2 <= count % 10 <= 4 and not (10 <= count % 100 <= 20) else 0]}")
    
    return ", ".join(string) if string else "0 секунд"

async def save_db(only_chat_id: int | str | None = None, folder="db"):
    filenames_to_save = [str(only_chat_id)] if only_chat_id else list(USER_BASE)
    for key in filenames_to_save:
        dict_to_save = USER_BASE[key].copy()
        if dict_to_save["OffUntil"] <= int(time.time()):
            dict_to_save["OffUntil"] = 0
            USER_BASE[key]["OffUntil"] = 0
        if not dict_to_save["_isUpdated"]:
            continue
        dict_to_save.pop("_isUpdated")
        USER_BASE[key]["_isUpdated"] = False
        async with aiofiles.open(os.path.join(folder, key + ".jsonc"), "w", encoding="utf-8") as file:
            await file.write(json.dumps(dict_to_save, ensure_ascii=False))

async def load_db(only_chat_id: int | str | None = None, folder="db"):
    dict_to_return = {}
    filenames_to_open = [str(only_chat_id)] if only_chat_id else [os.path.splitext(i)[0] for i in os.listdir(folder)]
    for filename in filenames_to_open:
        path = os.path.join(folder, filename + ".jsonc")
        async with aiofiles.open(path, "r", encoding="utf-8") as file:
            contents = await file.read()
            dict_to_return[filename] = {**json.loads(contents), "_isUpdated": False}
    return dict_to_return

def populate_base(chat_id: int | str):
    if str(chat_id) in USER_BASE:
        return
    USER_BASE[str(chat_id)] = {
        "_isUpdated": False,
        "ID": chat_id,
        "Messages": [],
        "Attachments": [],
        "OffUntil": 0
    }

def update_record(chat_id: int | str, new_value: dict):
    USER_BASE[str(chat_id)].update({**new_value, "_isUpdated": True})	

def add_database_message(chat_id: int | str, message_text: str):
    message_text = message_text.strip()
    if not message_text:
        return
    new_messages = USER_BASE[str(chat_id)]["Messages"]
    new_messages.append(message_text)
    update_record(chat_id, {"Messages": new_messages})

def get_random_meme_image():
    memes_folder = 'memes'
    memes = os.listdir(memes_folder)
    selected_meme = random.choice(memes)
    return os.path.join(memes_folder, selected_meme)

def create_meme(image_path, text):
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("arial.ttf", size=20)
    text_position = (10, 10)  # Позиция текста
    draw.text(text_position, text, font=font, fill="white")
    output_path = "output_meme.png"
    image.save(output_path)
    return output_path

@DP.message_handler()
async def message_handler(msg: MessageType):
    message_text = msg.text or msg.caption
    add_database_message(msg.chat.id, message_text)

    if USER_BASE[str(msg.chat.id)]["OffUntil"] > int(time.time()):
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
        img_path = get_random_meme_image()
        meme_image_path = create_meme(img_path, msg_generated)

        with open(meme_image_path, 'rb') as photo:
            await msg.answer_photo(photo)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(bg_saver())
    loop.run_until_complete(onBotStart(DP))
    from aiogram import executor
    executor.start_polling(DP)
