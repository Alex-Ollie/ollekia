import asyncio
import logging
import os
import sys
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any, Mapping
from urllib.parse import quote

import aiofiles
import aiofiles.os
import aiohttp

from ia_wrapper.enums import url_enum

from . import utils
from .enums.auth_enum import AuthType
from .protocols import Client

if TYPE_CHECKING:
    from .data_classes.download_dataclass import DownloadOptions
    from .item import AsyncItem

log = logging.getLogger(__name__)


class AsyncBaseFile:
    """Base class representing a file's metadata."""

    def __init__(
        self,
        item_metadata: Mapping[str, Any],
        name: str,
        file_metadata: Mapping[str, Any] | None = None,
    ):
        if file_metadata is None:
            file_metadata = {}

        if name:
            name = name.strip("/")

        if not file_metadata:
            for f in item_metadata.get("files", []):
                if f.get("name") == name:
                    file_metadata = f
                    break

        self.identifier = item_metadata.get("metadata", {}).get("identifier")
        self.name: str = name

        # Initialize with defaults before setting from metadata
        self.size: int = 0
        self.source: str | None = None
        self.format: str | None = None
        self.md5: str | None = None
        self.sha1: str | None = None
        self.mtime: float = 0.0
        self.crc32: str | None = None

        self.exists = bool(file_metadata)

        assert isinstance(file_metadata, Mapping), (
            "file_metadata must be a mapping type"
        )
        for key, value in file_metadata.items():
            setattr(self, key, value)

        self.metadata = file_metadata

        try:
            self.mtime = float(self.mtime) if self.mtime else 0.0
            self.size = int(self.size) if self.size else 0
        except (ValueError, TypeError):
            self.mtime = 0.0
            self.size = 0


class AsyncFile(AsyncBaseFile):
    def __init__(
        self,
        client: Client,
        item: "AsyncItem",
        name: str,
        file_metadata: Mapping[str, Any] | None = None,
    ):
        super().__init__(item.item_metadata, name, file_metadata)
        self.item = item
        self.client: Client = client
        self.url = f"{url_enum.URLS.BASE_URL.value}{self.identifier}/{quote(name.encode('utf-8'))}"

    def __repr__(self):
        return (
            f"AsyncFile(identifier={self.identifier!r}, "
            f"filename={self.name!r}, "
            f"size={self.size!r}, "
            f"format={self.format!r})"
        )

    async def download(
        self,
        download_options: "DownloadOptions",
    ) -> bool | aiohttp.ClientResponse | None:
        """
        Downloads the file based on the provided options, handling retries,
        checksums, and resuming.
        """
        headers = {}
        file_path = download_options.file_path or self.name

        if download_options.destdir:
            if await aiofiles.os.path.isfile(download_options.destdir):
                raise OSError(f"{download_options.destdir} is not a directory!")
            file_path = os.path.join(download_options.destdir, file_path)

        parent_dir = os.path.dirname(file_path)

        # Check if we should skip...
        if not download_options.return_responses and aiofiles.os.path.exists(file_path):
            if download_options.checksum_archive:
                checksum_archive_filename = "_checksum_archive.txt"
                if not aiofiles.os.path.exists(checksum_archive_filename):
                    async with aiofiles.open(
                        checksum_archive_filename, "w", encoding="utf-8"
                    ) as f:  # pyright: ignore [reportUndefinedVariable]
                        pass
                async with aiofiles.open(
                    checksum_archive_filename, encoding="utf-8"
                ) as f:
                    checksum_archive_data = await f.readlines()
                if file_path in checksum_archive_data:
                    msg = (
                        f"skipping {file_path}, "
                        f"file already exists based on checksum_archive."
                    )
                    log.info(msg)
                    if download_options.verbose:
                        print(f" {msg}", file=sys.stderr)
                    return None
            if download_options.ignore_existing:
                msg = f"skipping {file_path}, file already exists."
                log.info(msg)
                if download_options.verbose:
                    print(f" {msg}", file=sys.stderr)
                return None
            elif download_options.checksum or download_options.checksum_archive:
                async with aiofiles.open(file_path, "rb") as fp:
                    md5_sum = utils.get_md5(fp)
                if md5_sum == self.md5:
                    msg = (
                        f"skipping {file_path}, file already exists based on checksum."
                    )
                    log.info(msg)
                    if download_options.verbose:
                        print(f" {msg}", file=sys.stderr)
                    if download_options.checksum_archive:
                        async with aiofiles.open(
                            download_options.checksum_archive, "a", encoding="utf-8"
                        ) as f:
                            await f.write(f"{file_path}\n")
                    return

        # --- Retry Loop ---
        while True:
            try:
                if parent_dir and not download_options.return_responses:
                    await aiofiles.os.makedirs(parent_dir, exist_ok=True)

                st = None
                if (
                    not download_options.return_responses
                    and await aiofiles.os.path.exists(file_path)
                ):
                    st = await aiofiles.os.stat(file_path)
                    if st.st_size != self.size and not (
                        download_options.checksum or download_options.checksum_archive
                    ):
                        headers = {"Range": f"bytes={st.st_size}-"}

                async with await self.client.get(
                    self.url,
                    timeout=download_options.timeout,
                    auth_type=AuthType.S3,
                    params=download_options.params,
                    headers=headers,
                ) as response:
                    last_mod_header = response.headers.get("Last-Modified")
                    last_mod_mtime = (
                        parsedate_to_datetime(last_mod_header).timestamp()
                        if last_mod_header
                        else self.mtime
                    )
                    response.raise_for_status()

                    if download_options.return_responses:
                        return response

                    write_target = None
                    if download_options.stdout:
                        write_target = sys.stdout.buffer
                    elif download_options.fileobj:
                        write_target = download_options.fileobj
                    else:
                        write_mode = "wb"
                        if "Range" in headers:
                            write_mode = "ab"  # Append if resuming

                        # Open the file asynchronously
                        async with aiofiles.open(file_path, mode=write_mode) as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)

                        # After writing, perform post-download actions
                        if not download_options.no_change_timestamp:
                            await asyncio.to_thread(
                                os.utime, file_path, (last_mod_mtime, last_mod_mtime)
                            )

                        log.info(
                            f"downloaded {self.identifier}/{self.name} to {file_path}"
                        )
                        return True

                    # Handle writing to a pre-existing file-like object (e.g. stdout)
                    async for chunk in response.content.iter_chunked(8192):
                        if asyncio.iscoroutinefunction(write_target.write):
                            await write_target.write(chunk)
                        else:
                            await asyncio.to_thread(write_target.write, chunk)

                break  # Exit while loop on success

            except Exception as exc:
                if download_options.retries > 0:
                    download_options.retries -= 1
                    log.warning(
                        f"Download failed, sleeping and retrying. {download_options.retries} retries left."
                    )
                    await asyncio.sleep(download_options.retries_sleep)
                    continue

                log.error(f"Error downloading file {file_path}: {exc}")
                if download_options.ignore_errors:
                    return False
                else:
                    raise exc

        return True  # Should be unreachable, but good practice


class OnTheFlyFile(AsyncFile):
    def __init__(self, client: Client, item: "AsyncItem", name: str):
        super().__init__(client, item, name)
