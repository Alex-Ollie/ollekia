import logging
from typing import MutableMapping
from pathlib import Path

from .protocols import Client
from .client import InternetArchiveClient
from .data_classes.download_dataclass import DownloadOptions
from .data_classes.search_dataclass import SearchOptions
from .file import AsyncFile
from .item import AsyncItem
from .search import AsyncSearch
from .enums.auth_enum import AuthType
from .enums.url_enum import URLS


logger = logging.getLogger(__name__)


class WrapperAPI:

    def __init__(self):
        self.client : Client = InternetArchiveClient()

    async def close(self):
        """Closes the client's session. Should be called on shutdown."""
        await self.client.close()


    async def get_item(
            self,
            identifier: str,
            item_metadata: MutableMapping | None = None,
            request_kwargs: MutableMapping | None = None,
    ) -> AsyncItem:
        return await self.client.get_item(identifier,  item_metadata,request_kwargs=request_kwargs)

    async def get_files(
            self,
            identifier: str,
            files: AsyncFile | list[AsyncFile] | None = None,
            formats: str | list[str] | None = None,
            glob_pattern: str | None = None,
            exclude_pattern: str | None = None,
            on_the_fly: bool = False,
            **get_item_kwargs,
    ):
        item = await self.get_item(identifier, **get_item_kwargs)
        return item.get_files(files, formats, glob_pattern, exclude_pattern, on_the_fly)

    async def download(
            self,
            identifier: str,
            download_options: DownloadOptions,
            **get_item_kwargs):

        item = await self.get_item(identifier, **get_item_kwargs)
        req_res = await item.download(download_options)

        return req_res

    async def search_items(
            self,
            search_options: SearchOptions,
    ) -> AsyncSearch:
        return await self.client.search_items(search_options)

    async def update_credentials(
            self,
            username: str = "",
            password: str = ""
    ) -> Path | None:
        config_file_path = await self.client.update_credentials(username, password)
        if config_file_path is not None:
            return config_file_path
        else:
            raise ValueError("Failed to update credentials, config file path is None.")

    async def get_username(self) -> str:
        url = URLS.S3_BASE.value
        parameters = {"check_auth": 1}
        response = await self.client.get(url, params=parameters, auth_type=AuthType.S3, timeout=10)
        response.raise_for_status()
        response_json = await response.json()
        return response_json.get("username", "")

    async def get_user_info(self) -> dict[str, str]:
        url = URLS.S3_BASE.value
        params = {"check_auth": 1}

        response = await self.client.get(url, params=params, auth_type=AuthType.S3, timeout=10)
        response.raise_for_status()
        response_json = await response.json()

        if response_json.get("error"):
            error_message = response_json.get("error")
            logger.warning(f"Authentication error: {error_message}")
            raise PermissionError(f"Authentication failed: {error_message}")
        else:
            return response_json
