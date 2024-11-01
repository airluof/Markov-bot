from aiogram import types
from aiogram.types import InputFile
from PIL import Image, ImageDraw, ImageFont
import io

@DP.message_handler(commands=["mem"])
async def generate_mem(msg: types.Message):
    # Получаем последние сообщения из базы
    messages = USER_BASE[str(msg.chat.id)]["Messages"][-5:]  # последние 5 сообщений

    if not messages:
        await msg.answer("Недостаточно сообщений для создания мема.")
        return

    # Создаем текст для мема
    meme_text = "\n".join(messages)  # Соединяем сообщения с переносами

    # Генерация мема
    width, height = 800, 400
    image = Image.new('RGB', (width, height), color=(73, 109, 137))
    draw = ImageDraw.Draw(image)

    # Укажите путь к шрифту или используйте встроенный
    font = ImageFont.load_default()  # Для простоты используем стандартный шрифт

    # Рассчитываем размер текста и центрируем его
    text_width, text_height = draw.textsize(meme_text, font=font)
    text_x = (width - text_width) / 2
    text_y = (height - text_height) / 2

    # Добавляем текст на изображение
    draw.text((text_x, text_y), meme_text, font=font, fill=(255, 255, 255))

    # Сохраняем мем в буфер
    byte_io = io.BytesIO()
    image.save(byte_io, 'JPEG')
    byte_io.seek(0)

    # Отправляем мем в чат
    await msg.answer_photo(photo=InputFile(byte_io, filename='meme.jpg'))
