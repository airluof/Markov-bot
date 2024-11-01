from aiogram import types
from aiogram.types import InputFile
from PIL import Image, ImageDraw, ImageFont
import io

@DP.message_handler(commands=["mem"])
async def generate_mem(msg: types.Message):
    messages = USER_BASE[str(msg.chat.id)]["Messages"][-10:]  # Измените 5 на 10

    if not messages:
        await msg.answer("Недостаточно сообщений для создания мема.")
        return

    meme_text = "\n".join(messages)
    width, height = 800, 400
    image = Image.new('RGB', (width, height), color=(73, 109, 137))
    draw = ImageDraw.Draw(image)

    font = ImageFont.load_default()
    text_width, text_height = draw.textsize(meme_text, font=font)
    text_x = (width - text_width) / 2
    text_y = (height - text_height) / 2
    draw.text((text_x, text_y), meme_text, font=font, fill=(255, 255, 255))

    byte_io = io.BytesIO()
    image.save(byte_io, 'JPEG')
    byte_io.seek(0)

    await msg.answer_photo(photo=InputFile(byte_io, filename='meme.jpg'))
