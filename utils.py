from urllib.parse import urlparse, urlunparse


def clean_url(url):
    """Очищує URL від параметрів запиту."""
    try:
        # Розбираємо URL на компоненти
        parsed_url = urlparse(url)
        # Збираємо URL без параметрів (query) та фрагмента (fragment)
        clean_url_str = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
        return clean_url_str
    except Exception:
        return url
