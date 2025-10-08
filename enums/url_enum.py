from enum import Enum


class URLS(Enum):
    """
    URL Enums
    """

    BASE_HOST = ".archive.org"
    BASE_URL = "https://archive.org/"
    S3_BASE = "https://s3.us.archive.org/"
    METADATA_API_BASE = "https://archive.org/metadata/"
    SCRAPE_URL = "https://archive.org/services/search/v1/scrape"
    ADVANCED_SEARCH_URL = "https://archive.org/advancedsearch.php"
    FTS_URL = "https://be-api.us.archive.org/ia-pub-fts-api"
    GET_USER_URL = "https://archive.org/services/user.php"
    AUTH_SERVICE_URL = "https://archive.org/services/xauthn/"
    SEARCH_SERVICE_URL = "https://archive.org/services/search/v1/"
