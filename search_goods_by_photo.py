import time
import random
from typing import Optional, Dict, List, Any

import undetected_chromedriver as uc
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
    options.add_argument("--lang=uk-UA,uk,en-US,en")
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

        logger.info(f"Крок 2: Перехід на сторінку {page_url}...")
        driver.get(page_url)
        logger.info(f"Крок 2: Сторінку {page_url} завантажено.")

        wait = WebDriverWait(driver, 5)

        button_xpath = "//div[contains(@class, 'picture-search-btn')]"
        logger.info(f"Крок 3: Очікування кнопки пошуку за зображенням: {button_xpath}")
        button = wait.until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
        logger.info("Крок 3: Кнопку знайдено, виконується клік...")
        button.click()
        time.sleep(random.uniform(0.3, 1.5))

        file_input_xpath = "//input[@type='file' and contains(@accept, '.jpg')]"
        logger.info(f"Крок 4: Очікування input[type='file']: {file_input_xpath}")
        wait.until(EC.presence_of_element_located((By.XPATH, file_input_xpath)))
        time.sleep(0.5)
        file_input = driver.find_element(By.XPATH, file_input_xpath)

        logger.info(f"Крок 5: Надсилання шляху до файлу: {image_path}")
        file_input.send_keys(image_path)
        logger.info("Крок 5: Файл успішно передано у input.")

        time.sleep(random.uniform(2, 3))

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

                # price_text = "Ціна не знайдена"
                # try:
                #     price_element = element.find_element(By.CSS_SELECTOR, price_selector)
                #     price_text = price_element.text.strip().replace('\n', ' ')
                #     if not price_text:
                #         price_text = price_element.get_attribute('innerText').strip().replace('\n', ' ')
                # except Exception:
                #     pass

                cleaned_href = clean_url(href)
                results_data.append({"url": cleaned_href, "title": title_text, "photo": photo})
                count += 1

            except Exception as el_err:
                logger.warning(f"Помилка обробки елемента: {el_err}")
                continue

        if results_data:
            total_time = time.time() - start_time
            # print(results_data)
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