import asyncio
import functools
import locale
import logging
import platform
import pprint
import sys
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Mapping, MutableMapping
from urllib.parse import unquote

import aiohttp

from .config import get_config, write_config_file
from .data_classes.search_dataclass import SearchOptions
from .enums.auth_enum import AuthType
from .enums.url_enum import URLS
from .item import AsyncItem
from .protocols import Client
from .search import AsyncSearch
from .utils import parse_dict_cookies

logger = logging.getLogger(__name__)


def client_initialized(
    func,
):  # Decorator to ensure the InternetArchiveClient is initialized before calling the function.
    @functools.wraps(func)
    async def wrapper(self: "InternetArchiveClient", *args, **kwargs):
        # The initialization check is now neatly tucked away here
        await self._ensure_initialized()
        return await func(self, *args, **kwargs)

    return wrapper


class InternetArchiveClient(Client):
    def __init__(self):
        """Initializes the client state synchronously."""
        self._config = {}
        self._session: aiohttp.ClientSession | None = None  # type: aiohttp.ClientSession

        self._user_email = None
        self._screenname = None
        self._secret_key = ""
        self._access_key = ""

        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def _ensure_initialized(self):
        """
        Performs the one-time asynchronous setup for the client.
        This is concurrency-safe.
        """
        if not self._initialized:
            async with self._init_lock:
                if not self._initialized:
                    logger.debug("Performing one-time client initialization...")

                    self._config = await get_config()
                    self._set_core()
                    self._session = aiohttp.ClientSession(
                        headers={
                            "User-Agent": self._get_user_agent_string(),
                            "Accept": "*/*",
                            "Accept-Encoding": "gzip, deflate",
                        },
                        timeout=aiohttp.ClientTimeout(total=300),
                    )
                    self._set_cookies()
                    self._initialized = True

                    logger.debug("Client initialized successfully.")

    """

    PRIVATE METHODS
    
    """

    def _get_user_agent_string(self) -> str:
        uname = platform.uname()
        lang = ""
        try:
            locale_code = locale.getlocale()[0]
            if locale_code:
                lang = locale_code[:2]
        except Exception:
            pass

        py_version = "{}.{}.{}".format(*sys.version_info)
        version = "5.4.1"

        return (
            f"internetarchive/{version} "
            f"({uname[0]} {uname[-1]}; N; {lang}; {self._access_key}) "
            f"Python/{py_version}"
        )

    def _get_s3_auth_headers(self) -> dict:
        return {"Authorization": f"LOW {self._access_key}:{self._secret_key}"}

    def _update_cookies(self, raw_cookie: dict[str, str]):
        for ck, cv in raw_cookie.items():
            raw_cookie_str = f"{ck}={cv}"
            parsed_cookie_dict = parse_dict_cookies(raw_cookie_str)

            cookie_value = parsed_cookie_dict.get(ck)
            if cookie_value is not None:
                single_cookie_header = SimpleCookie()
                single_cookie_header[ck] = cookie_value

                if "expires" in parsed_cookie_dict:
                    single_cookie_header[ck]["expires"] = parsed_cookie_dict["expires"]
                if "path" in parsed_cookie_dict:
                    single_cookie_header[ck]["path"] = parsed_cookie_dict["path"]
                if "domain" in parsed_cookie_dict:
                    single_cookie_header[ck]["domain"] = parsed_cookie_dict["domain"]
                if "Max-Age" in parsed_cookie_dict:
                    single_cookie_header[ck]["max-age"] = parsed_cookie_dict["Max-Age"]
                if "HttpOnly" in parsed_cookie_dict:
                    single_cookie_header[ck]["httponly"] = True

                assert self._session is not None
                self._session.cookie_jar.update_cookies(single_cookie_header)
                logger.debug(f"Updated cookie {ck} in session.")

    def _set_core(self):
        self.secure: bool = self._config.get("general", {}).get("secure", True)
        self.base_host: str = self._config.get("general", {}).get("host", "archive.org")
        # This logic ensures self.base_host always includes 'archive.org' if not present
        if "archive.org" not in self.base_host:
            self.base_host += ".archive.org"
        self.protocol = "https:"

        user_email_raw = self._config.get("cookies", {}).get("logged-in-user")
        self.user_email: str = (
            unquote(user_email_raw.split(";")[0]) if user_email_raw else ""
        )

        self._access_key: str = self._config.get("s3", {}).get("access")
        self._secret_key: str = self._config.get("s3", {}).get("secret")
        self.screenname: str = self._config.get("general", {}).get("screenname", "")
        self.logging_level: str = (
            self._config.get("logging", {}).get("level", "DEBUG").upper()
        )

    def _set_cookies(self):
        self._update_cookies(self._config.get("cookies", {}))

    """

    PUBLIC METHODS

    """

    @client_initialized
    async def get(
        self,
        url: str,
        params=None,
        headers: dict | None = None,
        auth_type: AuthType = AuthType.NO_AUTH,
        **kwargs,
    ) -> aiohttp.ClientResponse:
        try:
            assert self._session is not None

            request_headers = headers.copy() if headers else {}
            auth_obj = None

            if auth_type == AuthType.S3 and self._access_key:
                auth_obj = aiohttp.BasicAuth(self._access_key, self._secret_key)

            resp = await self._session.get(
                url,
                params=params,
                auth=auth_obj,  # Pass the auth object only when it's not None
                headers=request_headers,
                **kwargs,
            )
            resp.raise_for_status()
            return resp

        except aiohttp.ClientResponseError as e:
            logger.error(
                f"HTTP Error GET {url}: Status {e.status}, Message: {e.message}"
            )
            raise
        except aiohttp.ClientError as e:
            logger.error(f"Network/Client Error GET {url}: {e}")
            raise

    @client_initialized
    async def post(
        self,
        url: str,
        params=None,
        headers: dict | None = None,
        auth_type: AuthType = AuthType.NO_AUTH,
        post_data: dict[str, str] | None = None,
        **kwargs,
    ) -> aiohttp.ClientResponse:
        try:
            assert self._session is not None
            request_headers = headers.copy() if headers else {}

            if (
                auth_type == AuthType.S3
                and self._access_key
                and "Authorization" not in request_headers
            ):
                request_headers.update(self._get_s3_auth_headers())
                request_headers["Content-Type"] = "application/x-www-form-urlencoded"

            resp = await self._session.post(
                url,
                data=None,
                params=params,
                headers=request_headers,
                **kwargs,
            )
            resp.raise_for_status()
            return resp

        except aiohttp.ClientResponseError as e:
            logger.error(
                f"HTTP Error POST {url}: Status {e.status}, Message: {e.message}"
            )
            raise
        except aiohttp.ClientError as e:
            logger.error(f"Network/Client Error POST {url}: {e}")
            raise

    @client_initialized
    async def s3_is_overloaded(self, identifier, **kwargs) -> bool:
        req_kwargs = kwargs or {}

        if not self._access_key:
            logger.warning(
                "s3_is_overloaded called without access_key set on client. Authentication may fail."
            )

        params = {
            "check_limit": 1,
            "accesskey": self._access_key,
            "bucket": identifier,
        }

        if "timeout" not in req_kwargs:
            req_kwargs["timeout"] = 12

        try:
            response = await self.get(
                URLS.S3_BASE.value, params=params, auth_type=AuthType.S3, **req_kwargs
            )
            response_json = await response.json()

            if "over_limit" not in response_json:
                logger.warning(
                    f"Unexpected JSON response from s3_is_overloaded: {response_json}"
                )
                return True

            return response_json["over_limit"] != 0

        except aiohttp.ContentTypeError:
            logger.error(
                f"s3_is_overloaded received non-JSON response from {URLS.S3_BASE.value}. Assuming overloaded."
            )
            return True
        except aiohttp.ClientResponseError as e:
            logger.error(
                f"HTTP Error checking s3_is_overloaded for {URLS.S3_BASE.value}: Status {e.status} - {e.message}"
            )
            return True
        except aiohttp.ClientError as e:
            logger.error(
                f"Network error checking s3_is_overloaded for {URLS.S3_BASE.value}: {e}. Assuming overloaded."
            )
            return True
        except Exception as e:
            logger.exception(
                f"An unexpected error occurred in s3_is_overloaded for {URLS.S3_BASE.value}. Exception: {e}"
            )
            raise

    @client_initialized
    async def whoami(self) -> str:
        params = {"op": "whoami"}
        request_kwargs = {}

        try:
            response = await self.get(
                URLS.GET_USER_URL.value,
                params=params,
                auth_type=AuthType.S3,
                **request_kwargs,
            )
            response_json = await response.json()

            return response_json

        except Exception as exc:
            error_msg = (
                f"Error retrieving metadata from {URLS.METADATA_API_BASE.value}, {exc}"
            )
            logger.error(error_msg)
            raise type(exc)(error_msg)

    @client_initialized
    async def get_metadata(
        self, identifier, request_kwargs: MutableMapping | None = None
    ):
        request_kwargs = request_kwargs or {}
        url = f"{URLS.METADATA_API_BASE.value}{identifier}"

        if "timeout" not in request_kwargs:
            request_kwargs["timeout"] = 12

        try:
            async with await self.get(
                url, params={}, auth_type=AuthType.NO_AUTH, **request_kwargs
            ) as resp:
                response_json = await resp.json()
                return response_json
        except Exception as exc:
            error_msg = (
                f"Error retrieving metadata from {URLS.METADATA_API_BASE.value}, {exc}"
            )
            logger.error(error_msg)
            raise type(exc)(error_msg)

    @client_initialized
    async def search_items(self, search_options: SearchOptions) -> AsyncSearch:
        return AsyncSearch(self, search_options)

    @client_initialized
    async def get_item(
        self,
        identifier: str,
        item_metadata: Mapping | None = None,
        request_kwargs: MutableMapping | None = None,
    ) -> AsyncItem:
        request_kwargs = request_kwargs or {}

        if not item_metadata:
            item_metadata = await self.get_metadata(identifier, request_kwargs)

        assert item_metadata is not None, (
            f"Metadata for item {identifier} cannot be None."
        )

        return AsyncItem(self, identifier, item_metadata)

    @client_initialized
    async def check_auth(self) -> dict[str, str]:
        params = {"check_auth": 1}

        async with await self.get(
            URLS.S3_BASE.value, params=params, auth_type=AuthType.S3
        ) as resp:
            json = await resp.json()
            if json.get("error"):
                logger.warning("auth error")
            return json

    @client_initialized
    async def update_credentials(self, email: str, password: str) -> Path | None:
        params = {"op": "login"}
        post_data = {"email": email, "password": password}

        logger.info(f"Attempting login to {URLS.AUTH_SERVICE_URL.value} for {email}...")

        try:
            async with await self.post(
                URLS.AUTH_SERVICE_URL.value,
                params=params,
                auth_type=AuthType.S3,
                data=post_data,
                timeout=12,
            ) as response:
                json_response = await response.json()

            if not json_response.get("success"):
                error_message = json_response.get(
                    "error", "Unknown authentication error."
                )
                reason_detail = json_response.get("values", {}).get("reason")
                if reason_detail:
                    logger.warning(
                        f"Authentication failed for {email}: {reason_detail}  with error: {error_message}"
                    )

                """
                # Raise custom AuthError
                raise InternetArchiveAuthError(
                    message=error_message,
                    email=email,
                    host=self.base_host,
                    api_response=json_response
                )
                """

            s3_data = json_response.get("values", {}).get("s3", {})
            self._access_key = s3_data.get("access")
            self._secret_key = s3_data.get("secret")

            new_cookies_raw = json_response.get("values", {}).get("cookies", {})

            self._update_cookies(new_cookies_raw)

            self._screenname = json_response.get("values", {}).get("screenname")
            self._user_email = unquote(
                new_cookies_raw.get("logged-in-user", "").split(";")[0]
            )

            logger.info(
                f"Successfully authenticated as {self._screenname} (email: {self._user_email})."
            )

            auth_config_to_write = {
                "s3": {
                    "access": self._access_key,
                    "secret": self._secret_key,
                },
                "cookies": new_cookies_raw,
                "general": {
                    "screenname": self._screenname,
                },
            }

            try:
                written_file_path = await write_config_file(auth_config_to_write)
                logger.info(f"Authentication config written to {written_file_path}")
            except IOError as e:
                logger.error(f"Failed to write config file after successful login: {e}")
                raise  # raise exception
            except Exception as e:
                logger.exception(
                    f"An unexpected error occurred while writing config file. Error: {e}"
                )
                raise  # raise exception

            return written_file_path

        except aiohttp.ClientResponseError as e:
            logger.log(
                logging.ERROR, f"HTTP Error during login: {e.status} - {e.message}"
            )
            # raise InternetArchiveHTTPError(
            #     message=f"HTTP Error during login: {e.status} - {e.message}",
            #     status_code=e.status, url=login_url, api_response=getattr(e, 'json', None)
            # ) from e
        # except aiohttp.ClientError as e:
        #     # raise InternetArchiveNetworkError(
        #     #     message=f"Network Error during login: {e}", url=login_url
        #     # ) from e
        # except Exception as e #InternetArchiveAuthError:
        #     raise
        # #except Exception as e:
        #     logger.exception(f"An unexpected error occurred during login.")
        #     #raise InternetArchiveError(f"Unexpected error during login: {e}") from e

    @client_initialized
    def set_file_logger(
        self,
        log_level: str,
    ) -> None:
        """Convenience function to quickly configure any level of
        logging to a file.

        :param log_level: A log level as specified in the `logging` module.

        :param path: Path to the log file. The file will be created if it doesn't already
                     exist.

        :param logger_name: The name of the logger.
        """
        _log_level = {
            "CRITICAL": 50,
            "ERROR": 40,
            "WARNING": 30,
            "INFO": 20,
            "DEBUG": 10,
            "NOTSET": 0,
        }

        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        _log = logging.getLogger(self.__class__.__name__)
        _log.setLevel(_log_level.get(log_level.upper(), logging.DEBUG))

    @client_initialized
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("Client session closed.")
