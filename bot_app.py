# bot_app.py
import os
import asyncio
import re

import uuid # Для унікальних імен файлів
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message # Inline кнопки поки не використовуємо
from aiogram.exceptions import TelegramAPIError
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from aliexpress_app import create_aliexpress_affiliate_links
from search_goods_by_photo import search_with_selenium
from utils import clean_url
from logger_ import get_logger


logger = get_logger(__name__)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID_STR = os.getenv("TELEGRAM_CHANNEL_ID")
ALIEXPRESS_APP_KEY = os.getenv("ALIEXPRESS_APP_KEY")
ALIEXPRESS_APP_SECRET = os.getenv("ALIEXPRESS_APP_SECRET")
ALIEXPRESS_TRACKING_ID = os.getenv("ALIEXPRESS_TRACKING_ID")

# --- Перевірка та конвертація ID каналу  ---
if not TELEGRAM_CHANNEL_ID_STR:
    logger.error("Помилка: TELEGRAM_CHANNEL_ID не задано у .env файлі!")
    exit()
try:
    TELEGRAM_CHANNEL_ID = int(TELEGRAM_CHANNEL_ID_STR)
except ValueError:
    if TELEGRAM_CHANNEL_ID_STR.startswith('@'):
         TELEGRAM_CHANNEL_ID = TELEGRAM_CHANNEL_ID_STR
    else:
        logger.error(f"Помилка: Неправильний формат TELEGRAM_CHANNEL_ID: {TELEGRAM_CHANNEL_ID_STR}.")
        exit()
# --- Перевірка інших змінних ---
if not all([TELEGRAM_BOT_TOKEN, ALIEXPRESS_APP_KEY, ALIEXPRESS_APP_SECRET, ALIEXPRESS_TRACKING_ID]):
    logger.error("Помилка: Не всі необхідні змінні середовища задані у .env файлі!")
    exit()

# --- Ініціалізація бота та диспетчера ---
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
logger.info("Бот Aiogram запущено.")
dp = Dispatcher()

# --- Обробник команди /start ---
@dp.message(Command(commands=["start"]))
async def start_command(message: Message):
    html_text = """✋Вітаю, ти у чат-боті <a href="https://t.me/AliDealsUA_bot">Знахідки AliExpress UA</a>, який подарує тобі найбільші ЗНИЖКИ на товари з Аліекспрес.

Надішли мені, будь-яке, посилання з Aliexpress, а я згенерую тобі 3 крутих посилання зі знижками: за <strong>МОНЕТИ</strong>, на <strong>СУПЕРЗНИЖКИ</strong> та <strong>ОБМЕЖЕНІ ПРОПОЗИЦІЇ</strong>.

Або 📸 <b>надішли мені фото товару</b>, і я спробую знайти схожі на AliExpress!

😎Що залишиться тобі зробити? Просто перейти за посиланням, які я тобі відправлю, обрати для себе найвигіднішу знижку та зробити замовлення.

‼️Будь ласка, будь уважним, реальну знижку за МОНЕТИ Аліекспрес покаже лише після того, як ти натиснеш чорну кнопку  «купити зараз» та «продовжити».Вдалих тобі покупок🥰

👭<strong>Якщо був корисним, поділись мною з другом або подругою. Дякую</strong>💰"""
    await message.answer(html_text, parse_mode="HTML", disable_web_page_preview=True)

# --- Функція відповіді в канал з посиланнями на товари в розділах зі знижками
async def send_product_to_telegram_channel(bot_instance: Bot, ali_url: str):
    try:
        (coin_affiliate_link, super_discount_affiliate_link,
         limited_discount_affiliate_link, title_product, main_photo) = create_aliexpress_affiliate_links(ali_url)

        caption = f"👇️ Ваші знижки для товару: {title_product} 👇️\n\n"
        caption += f"✨ <strong>З монетними знижками:</strong> ✨\n{coin_affiliate_link}\n\n"
        caption += f"💰 <strong>З суперзнижкою:</strong>\n{super_discount_affiliate_link}\n\n"
        caption += f"💰 <strong>Лімітовані знижки:</strong>\n{limited_discount_affiliate_link}"

        if main_photo:
            await bot_instance.send_photo(
                chat_id=TELEGRAM_CHANNEL_ID,
                photo=main_photo,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
            logger.info(f"Надіслано фото товару '{title_product}' в канал {TELEGRAM_CHANNEL_ID}")
        else:
             await bot_instance.send_message(
                chat_id=TELEGRAM_CHANNEL_ID,
                text=caption,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
             logger.info(f"Надіслано текст про товар '{title_product}' в канал {TELEGRAM_CHANNEL_ID}")

    except TelegramAPIError as e:
        logger.error(f"Помилка API Telegram під час надсилання в канал: {e}")
    except Exception as e:
        logger.error(f"Невідома помилка під час надсилання в канал: {e}")


# --- Обробник фотоповідомлень ---
@dp.message(F.photo)
async def handle_photo_search(message: Message):
    """Обробляє отримане фото для пошуку на AliExpress."""
    photo = message.photo[-1] # Беремо найбільше розширення
    file_id = photo.file_id
    temp_file_path = None # Ініціалізуємо шлях до тимчасового файлу

    # Створюємо тимчасову директорію, якщо її немає
    temp_dir = "temp_images"
    os.makedirs(temp_dir, exist_ok=True)

    try:
        await message.reply("📸 Отримав фото. Починаю пошук схожих товарів на AliExpress... Це може зайняти хвилину-дві.")

        # Завантажуємо фото у тимчасовий файл
        file_info = await bot.get_file(file_id)
        file_ext = os.path.splitext(file_info.file_path)[1] if file_info.file_path else '.jpg' # Беремо розширення
        # Генеруємо унікальне ім'я файлу
        temp_file_name = f"{uuid.uuid4()}{file_ext}"

        # Створюємо відносний шлях
        relative_temp_file_path = os.path.join(temp_dir, temp_file_name)
        # Конвертуємо у АБСОЛЮТНИЙ шлях ***
        absolute_temp_file_path = os.path.abspath(relative_temp_file_path)

        logger.info(f"Завантаження фото у тимчасовий файл: {absolute_temp_file_path}")  # Логуємо абсолютний шлях
        # Завантажуємо файл за абсолютним шляхом
        await bot.download(file=file_id, destination=absolute_temp_file_path)
        logger.info(f"Фото завантажено.")

        # Визначаємо стартову URL для пошуку
        start_url = "https://www.aliexpress.com/"

        # Запускаємо пошук в окремому потоці, щоб не блокувати бота
        loop = asyncio.get_running_loop()
        # ВИПРАВЛЕНО ЛОГУВАННЯ:
        logger.info(f"Запуск search_with_selenium для файлу {absolute_temp_file_path}")
        search_results_data = await loop.run_in_executor(
            None,  # Використовуємо стандартний виконавець
            search_with_selenium,
            start_url,
            absolute_temp_file_path  # Передаємо правильний шлях
        )
        logger.info(f"search_with_selenium завершив роботу.")

        # Обробляємо результати
        if search_results_data and search_results_data.get("results"):
            results = search_results_data["results"]
            response_text = "🔍 Ось що вдалося знайти схожого:\n\n"
            for i, item in enumerate(results, 1):
                # Екрануємо HTML символи в назві
                title = item.get('title', 'Без назви').replace('<', '&lt;').replace('>', '&gt;')
                url = item.get('url', '#')

                photo_url = item.get('photo')
                if photo_url:
                    try:
                        await bot.send_photo(chat_id=message.chat.id, photo=photo_url,
                                             caption=f"{i}. <a href='{url}'>{title}</a>", parse_mode=ParseMode.HTML)
                    except TelegramAPIError as e:
                        logger.error(f"Помилка Telegram API при відправці фото за URL: {e}")
                        response_text += f"{i}. <a href='{url}'>{title}</a>\n  URL фото: {photo_url} (Помилка Telegram)\n\n"
                    except Exception as e:
                        logger.error(f"Невідома помилка при відправці фото за URL: {e}")
                        response_text += f"{i}. <a href='{url}'>{title}</a>\n  URL фото: {photo_url} (Невідома помилка)\n\n"
                else:
                    response_text += f"{i}. <a href='{url}'>{title}</a>\n  Фото не знайдено\n\n"


                # Обмеження довжини повідомлення
                if len(response_text) > 3800:
                     await message.answer(response_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                     response_text = "...\n\n"

            if response_text.strip() and response_text != "...\n\n":
                 await message.answer(response_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

        elif search_results_data is None:
            await message.reply("😕 Виникла помилка під час пошуку на AliExpress. Спробуйте пізніше.")
        else: # search_results_data є, але results порожній
            await message.reply("🤷 На жаль, не вдалося знайти схожих товарів за цим зображенням.")

    except TelegramAPIError as e:
        logger.error(f"Помилка API Telegram під час обробки фото: {e}")
        await message.reply("Помилка Telegram під час обробки запиту.")
    except Exception as e:
        logger.exception(f"Невідома помилка під час обробки фото:")
        await message.reply("Сталася невідома помилка. Спробуйте ще раз.")
    finally:
        # Видаляємо тимчасовий файл, використовуючи АБСОЛЮТНИЙ шлях
        if absolute_temp_file_path and os.path.exists(absolute_temp_file_path):
            try:
                os.remove(absolute_temp_file_path)
                logger.info(f"Тимчасовий файл видалено: {absolute_temp_file_path}")
            except OSError as e:
                logger.error(f"Не вдалося видалити тимчасовий файл {absolute_temp_file_path}: {e}")


# --- Обробник текстових повідомлень (для посилань) ---
@dp.message()
async def handle_message(message: Message):
    # Перевіряємо, чи повідомлення містить текст (на випадок інших типів повідомлень)
    if not message.text:
        await message.reply("Будь ласка, надішліть посилання на товар AliExpress або фотографію товару.")
        return

    # Патерн для стандартних посилань на товар
    aliexpress_url_pattern = re.compile(
        r'(https?://)?([\w.-]+\.)?aliexpress\.com/(item/|p/|store/product/|af/|i/)\d+(\.html|\?)?', re.IGNORECASE) # Розширено патерн
    # Патерн для коротких посилань a.aliexpress.com
    short_url_pattern = re.compile(r'https?://a\.aliexpress\.com/_[\w\d]+', re.IGNORECASE)


    if aliexpress_url_pattern.search(message.text) or short_url_pattern.search(message.text):
        original_url = message.text
        logger.info(f"Отримано посилання: {original_url}")
        # Очистка URL (використовуємо синхронну версію)
        url_to_process = clean_url(original_url)
        logger.info(f"Очищене посилання для API: {url_to_process}")
        await message.reply("⏳ Шукаю Ваш товар у розділах зі знижками... Це може зайняти кілька секунд.")
        await send_product_to_telegram_channel(bot, url_to_process)
    else:
        await message.reply("Це не схоже на посилання AliExpress. Будь ласка, надішліть коректне посилання на товар або фотографію.")

# --- Запуск бота ---
async def main():
    await bot.delete_webhook(drop_pending_updates=True) # Важливо при переході з вебхуків на полінг
    logger.info("Запуск бота в режимі polling...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())