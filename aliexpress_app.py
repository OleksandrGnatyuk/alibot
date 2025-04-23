import os

from aliexpress_api import AliexpressApi, models
from dotenv import load_dotenv


load_dotenv()

ALIEXPRESS_APP_KEY = os.getenv("ALIEXPRESS_APP_KEY")
ALIEXPRESS_APP_SECRET = os.getenv("ALIEXPRESS_APP_SECRET")
ALIEXPRESS_TRACKING_ID = os.getenv("ALIEXPRESS_TRACKING_ID")


def create_aliexpress_affiliate_links(url):
    aliexpress = AliexpressApi(ALIEXPRESS_APP_KEY, ALIEXPRESS_APP_SECRET,
                               models.Language.EN, models.Currency.EUR, ALIEXPRESS_TRACKING_ID)

    products = aliexpress.get_products_details(url)
    title_product = products[0].product_title
    main_photo = products[0].product_main_image_url

    coin_affiliate_link = aliexpress.get_affiliate_links(url + '?sourceType=620')[0].promotion_link
    super_discount_affiliate_link = aliexpress.get_affiliate_links(url + '?sourceType=562')[0].promotion_link
    limited_discount_affiliate_link = aliexpress.get_affiliate_links(url + '?sourceType=621')[0].promotion_link

    # list_sourceType = [620, 561, 562, 570, 580, 504, 680, 591, 621, 560, 563, 610]

    return coin_affiliate_link, super_discount_affiliate_link, limited_discount_affiliate_link, title_product, main_photo


if __name__ == '__main__':
    test_url = 'https://www.aliexpress.com/item/32678087225.html'
    print(create_aliexpress_affiliate_links(test_url))