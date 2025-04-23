import time
import random
from typing import Optional, Dict, List, Any

import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from logger_ import get_logger
logger = get_logger(__name__)

try:
    from utils import clean_url
except ImportError:
    logger.error("Не вдалося імпортувати clean_url з utils")
    def clean_url(url): return url


start_url = "https://www.aliexpress.com/"

SearchResult = Dict[str, Any]

def search_with_selenium(page_url: str, image_path: str) -> Optional[SearchResult]:
    results_data: List[Dict[str, str]] = []
    driver = None
    start_time = time.time()

    options = uc.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-extensions")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=en-US,en,uk-UA,uk")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")

    try:
        logger.info("Крок 1: Ініціалізація undetected_chromedriver...")
        driver = uc.Chrome(options=options, use_subprocess=True)
        logger.info("Крок 1: undetected_chromedriver ініціалізовано.")

        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                try { window.chrome = { runtime: {} }; } catch(e) {}
                try { Object.defineProperty(navigator, 'languages', { get: () => ['uk-UA', 'uk', 'en-US', 'en'] }); } catch(e) {}
                try { Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] }); } catch(e) {}
            """
        })
        # ================================

        # --- Крок 1.5: Перехід на сторінку для встановлення cookies ---
        # Переходимо на головну, щоб мати правильний домен для cookies
        logger.info(f"Крок 1.5: Перехід на {page_url} для встановлення cookies...")
        driver.get(page_url)
        logger.info(f"Крок 1.5: Сторінку {page_url} завантажено.")
        time.sleep(random.uniform(1, 2))  # Невелика пауза

        # --- Крок 1.6: Встановлення Cookies ---
        # УВАГА: Імена та значення cookie 'aep_usuc_f' можуть потребувати точного налаштування!
        # Значення 'aep_usuc_f' потрібно перевірити у браузері
        # після ручного налаштування мови/валюти/регіону на сайті.
        cookies_to_set = [
            {'name': 'intl_locale', 'value': 'en_US', 'domain': '.aliexpress.com', 'path': '/'},
            {'name': 'aep_usuc_f', 'value': 'isfm=y&site=glo&c_tp=USD&region=US&b_locale=en_US', 'domain': '.aliexpress.com',
             'path': '/'}
            # Можливо, знадобляться інші cookies, наприклад, пов'язані з країною доставки

        ]
        logger.info("Крок 1.6: Встановлення кукі для мови (en_US) та валюти (USD)...")
        for cookie in cookies_to_set:
            try:
                # Іноді краще видалити існуючий cookie перед додаванням
                driver.delete_cookie(cookie['name'])
                driver.add_cookie(cookie)
                logger.info(f"Встановлено кукі: {cookie['name']}={cookie['value']}")
            except Exception as cookie_err:
                logger.warning(f"Не вдалося встановити кукі {cookie['name']}: {cookie_err}")

        # --- Крок 1.7: Перезавантаження сторінки ---
        logger.info("Крок 1.7: Перезавантаження сторінки для застосування кукі...")
        driver.refresh()
        # Додаємо очікування після перезавантаження, наприклад, на видимість тіла сторінки
        try:
            WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.TAG_NAME, "body")))
            logger.info("Крок 1.7: Сторінку перезавантажено та тіло сторінки видиме.")
        except TimeoutException:
            logger.warning("Крок 1.7: Сторінка не завантажилася повністю після перезавантаження та встановлення кукі.")
            # Продовжуємо виконання, але це може спричинити проблеми далі
        time.sleep(random.uniform(1, 2))  # Додаткова пауза

        # ---------------------------------

        logger.info(f"Крок 2: Перехід на сторінку {page_url}...")
        driver.get(page_url)
        logger.info(f"Крок 2: Сторінку {page_url} завантажено.")

        wait = WebDriverWait(driver, 10)

        button_xpath = "//div[contains(@class, 'picture-search-btn')]"
        logger.info(f"Крок 3: Очікування кнопки пошуку за зображенням: {button_xpath}")
        button = wait.until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
        logger.info("Крок 3: Кнопку знайдено, виконується клік...")
        button.click()
        time.sleep(random.uniform(0.5, 1.5))

        file_input_xpath = "//input[@type='file' and contains(@accept, '.jpg')]"
        logger.info(f"Крок 4: Очікування input[type='file']: {file_input_xpath}")
        wait.until(EC.presence_of_element_located((By.XPATH, file_input_xpath)))
        time.sleep(0.5)
        file_input = driver.find_element(By.XPATH, file_input_xpath)

        logger.info(f"Крок 5: Надсилання шляху до файлу: {image_path}")
        file_input.send_keys(image_path)
        logger.info("Крок 5: Файл успішно передано у input.")

        time.sleep(random.uniform(3, 4))

        results_container_selector = "#card-list a.search-card-item"
        results_present = EC.presence_of_element_located((By.CSS_SELECTOR, results_container_selector))
        url_changed = lambda d: d.current_url != page_url and not d.current_url.endswith('aliexpress.com/')

        logger.info(f"Крок 6: Очікування завантаження результатів або зміни URL...")
        WebDriverWait(driver, 75).until(EC.any_of(results_present, url_changed))
        new_url = driver.current_url
        logger.info(f"Крок 6: Поточна URL: {new_url}")
        time.sleep(random.uniform(1, 2))

        logger.info("Крок 7: Пошук елементів результатів...")
        elements = driver.find_elements(By.CSS_SELECTOR, results_container_selector)
        logger.info(f"Крок 7: Знайдено {len(elements)} потенційних елементів.")

        count = 0
        title_selector = "h3[class='kc_j0']"
        photo_selector = "img.kc_cs"

        suffix_to_remove = "_.avif"

        for element in elements:
            try:
                href = element.get_attribute("href")
                if href and href.startswith("//"):
                    href = "https:" + href
                elif not href or not href.startswith("http"):
                    continue

                title_text = "Назва не знайдена"
                price_text = "Ціна не знайдена"  # Значення за замовчуванням
                photo = ""
                try:
                    title_element = element.find_element(By.CSS_SELECTOR, title_selector)
                    title_text = title_element.text.strip() if title_element else title_text
                    photo_element = element.find_element(By.CSS_SELECTOR, photo_selector)
                    photo = photo_element.get_attribute("src")
                    if photo.endswith(suffix_to_remove):
                        photo = photo[:-len(suffix_to_remove)]
                    else:
                        photo = photo

                    if photo and photo.startswith("//"):
                        photo = start_url + href

                except Exception:
                    pass


                price_container_selector = "div.kc_k1"  # Селектор для контейнера ціни

                try:
                    # Знаходимо контейнер div.kc_k1 відносно поточного елемента 'element'
                    price_container = element.find_element(By.CSS_SELECTOR, price_container_selector)

                    # Знаходимо ВСІ елементи span всередині контейнера ціни
                    price_spans = price_container.find_elements(By.TAG_NAME, "span")

                    # Витягуємо текст з кожного span (якщо він не порожній)
                    price_parts = [span.text.strip() for span in price_spans if span.text.strip()]

                    # Збираємо ціну, якщо знайшли частини
                    if len(price_parts) >= 2:  # Потрібна принаймні валюта та ціле число
                        # Формат: Валюта + пробіл + Решта (ціле + роздільник + дробове)
                        currency_symbol = price_parts[0]
                        numeric_part = "".join(price_parts[1:])  # Поєднуємо другу та наступні частини
                        price_text = f"{currency_symbol} {numeric_part}"
                    elif price_parts:  # Якщо є хоча б одна частина (наприклад, тільки ціна без валюти)
                        price_text = price_parts[0]
                    # Якщо price_parts порожній, price_text залишиться "Ціна не знайдена"

                    logger.debug(f"Знайдено частини ціни: {price_parts} -> Результат: {price_text}")

                except Exception as price_err:
                    # Логуємо, якщо не вдалося знайти контейнер ціни або виникла інша помилка
                    logger.warning(
                        f"Не вдалося знайти/обробити ціну за селектором {price_container_selector}. Помилка: {price_err}")
                    # price_text залишається "Ціна не знайдена"


                cleaned_href = clean_url(href)
                results_data.append({"url": cleaned_href, "title": title_text, "photo": photo, "price": price_text})
                count += 1

            except Exception as el_err:
                logger.warning(f"Помилка обробки елемента: {el_err}")
                continue

        if results_data:
            total_time = time.time() - start_time
            print(results_data)
            logger.info(f"Крок 8: Повернення результатів. Загальний час: {total_time:.2f} сек.")
            return {"current_url": new_url, "results": results_data}
        else:
            logger.warning("Крок 8: Результати не знайдено.")
            return None

    except Exception as e:
        logger.exception(f"Критична помилка Selenium: {e}")
        return None

    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Браузер закрито.")
            except Exception as q_err:
                logger.error(f"Помилка при закритті браузера: {q_err}")
        end_time = time.time()
        logger.info(f"Загальний час функції: {end_time - start_time:.2f} сек.")