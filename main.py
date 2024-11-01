# coding: utf-8

import asyncio
import os
import random
import re
from datetime import datetime
from typing import cast

import aiogram
import dotenv
import markovify
from aiogram import Dispatcher
from aiogram.types import Message as MessageType
from loguru import logger
from PIL import Image, ImageDraw, ImageFont

dotenv.load_dotenv()

BOT = aiogram.Bot(
    os.environ["TOKEN"],
    parse_mode=aiogram.types.ParseMode.HTML
)
DP = Dispatcher(BOT)

# База сообщений в памяти
USER_BASE = {}

@DP.message_handler(commands=["start"])
async def hello_handler(msg: MessageType):
    # Из-за Middleware, эта команда будет работать только в беседах.
    await msg.answer("Отлично! 😊\n\nДля работы бота дайте ему права администратора.")

@DP.chat_join_request_handler()
@DP.message_handler(content_types=["new_chat_members", "group_chat_created", "supergroup_chat_created"])
async def chat_join_handler(msg: MessageType):
    """
    Вызывается, когда бота добавляют в чат.
    """
    bot_id = (await BOT.get_me()).id
    if not any([i for i in msg.new_chat_members if i.id == bot_id]):
        return

    await msg.answer("<b>Привет! 🙋</b>\n\nСпасибо за добавление меня в чат.")

@DP.message_handler(commands=["stats", "statistics", "stat"])
async def stats_handler(msg: MessageType):
    """
    Команда статистики.
    """
    chat_id = str(msg.chat.id)
    await msg.answer(
        f"<b>Статистика ℹ️</b>\n\nВ памяти этой группы хранится <code>{len(USER_BASE.get(chat_id, {}).get('Messages', []))}</code> сообщений."
    )

async def check_admin(msg: MessageType):
    """
    Проверяет наличие прав администратора в группе.
    """
    if not (await BOT.get_chat_member(msg.chat.id, msg.from_user.id)).is_chat_admin():
        await msg.answer("⚠️ Эту команду могут использовать только администраторы чата.")
        return False
    return True

@DP.message_handler(commands=["disable", "off"])
async def disable_handler(msg: MessageType):
    """
    Отключает генерацию сообщений бота.
    """
    if not await check_admin(msg):
        return

    USER_BASE[str(msg.chat.id)]["OffUntil"] = datetime.now().timestamp() + 7 * 24 * 60 * 60
    await msg.answer("Окей, я отключу генерацию сообщений в этой беседе на неделю.")

@DP.message_handler(commands=["enable", "on"])
async def enable_handler(msg: MessageType):
    """
    Включает генерацию сообщений бота.
    """
    if not await check_admin(msg):
        return

    USER_BASE[str(msg.chat.id)]["OffUntil"] = 0
    await msg.answer("Теперь я снова могу генерировать сообщения! 🙂")

def populate_base(chat_id: int | str):
    """
    Добавляет пустую запись в базу данных, если она отсутствует.
    """
    if str(chat_id) not in USER_BASE:
        USER_BASE[str(chat_id)] = {"Messages": [], "OffUntil": 0}

def add_database_message(chat_id: int | str, message_text: str):
    """
    Добавляет текст сообщения в базу.
    """
    message_text = message_text.strip()
    if message_text:
        USER_BASE[str(chat_id)]["Messages"].append(message_text)

async def generate_meme(text: str) -> str:
    """
    Создает изображение с текстом мем.
    """
    image = Image.open("memes/meme_template.jpg")  # Путь к шаблону мема
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("arial.ttf", 24)  # Путь к шрифту

    text_position = (20, 20)  # Позиция текста
    draw.text(text_position, text, fill="white", font=font)

    meme_path = f"memes/generated_meme_{random.randint(1000, 9999)}.jpg"
    image.save(meme_path)

    return meme_path

@DP.message_handler()
async def message_handler(msg: MessageType):
    """
    Обрабатывает любое новое сообщение.
    """
    chat_id = str(msg.chat.id)
    message_text = msg.text or msg.caption
    populate_base(chat_id)
    add_database_message(chat_id, message_text)

    if USER_BASE[chat_id]["OffUntil"] > datetime.now().timestamp():
        return

    is_triggered = any([i for i in ["макс", "max", "@maxzens_bot"] if i in message_text.lower()])
    if msg.reply_to_message and not is_triggered:
        is_triggered = msg.reply_to_message.from_user.id == BOT.id

    if random.randint(1, 100) > (80 if is_triggered else 8):
        return

    model = markovify.NewlineText("\n".join(USER_BASE[chat_id]["Messages"]).lower())
    msg_generated = model.make_sentence(tries=10) or random.choice(USER_BASE[chat_id]["Messages"])

    if msg_generated:
        msg_generated = re.sub(r"@(\w*)", "<i><a href=\"https://t.me/\\1\">@\\1</a></i>", msg_generated)
        meme_path = await generate_meme(msg_generated)

        await asyncio.sleep(random.uniform(1, 2))
        await msg.bot.send_chat_action(msg.chat.id, "upload_photo")
        await asyncio.sleep(random.uniform(1, 2))
        await msg.answer_photo(open(meme_path, "rb"))

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    os.makedirs("memes", exist_ok=True)  # Убедимся, что папка для мемов существует
    aiogram.utils.executor.start_polling(
        dispatcher=DP,
        on_startup=lambda dp: logger.info("Бот запущен!"),
        skip_updates=True,
        loop=loop,
    )
