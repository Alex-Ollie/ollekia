#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2024 Internet Archive
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
internetarchive.item
~~~~~~~~~~~~~~~~~~~~

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""

import os
import sys
from copy import deepcopy
from fnmatch import fnmatch
from functools import total_ordering
from logging import getLogger
from typing import Mapping
from typing import Set


from .enums.url_enum import URLS
from .protocols import Client
from .data_classes.download_dataclass import DownloadOptions
from .file import AsyncFile


log = getLogger(__name__)


@total_ordering
class AsyncBaseItem:
    EXCLUDED_ITEM_METADATA_KEYS = ('workable_servers', 'server')

    def __init__(
            self,
            identifier: str | None = None,
            item_metadata: Mapping | None = None,
    ):
        # Default attributes.
        self.identifier = identifier
        self.item_metadata = item_metadata or {}
        self.exists = False

        # Archive.org metadata attributes.
        self.metadata: dict = {}
        self.files: list[dict] = []
        self.created = None
        self.d1 = None
        self.d2 = None
        self.dir = None
        self.files_count = None
        self.item_size = None
        self.server = None
        self.is_dark = None

        # Load item.
        self.load()

    def __repr__(self) -> str:
        notloaded = ', item_metadata={}' if not self.exists else ''
        return f'{self.__class__.__name__}(identifier={self.identifier!r}{notloaded})'

    def load(self, item_metadata: Mapping | None = None) -> None:
        if item_metadata:
            self.item_metadata = item_metadata

        self.exists = bool(self.item_metadata)

        for key in self.item_metadata:
            setattr(self, key, self.item_metadata[key])

        if not self.identifier:
            self.identifier = self.metadata.get('identifier')

    def __eq__(self, other) -> bool:
        return (self.item_metadata == other.item_metadata
                or (self.item_metadata.keys() == other.item_metadata.keys()
                    and all(self.item_metadata[x] == other.item_metadata[x]
                            for x in self.item_metadata
                            if x not in self.EXCLUDED_ITEM_METADATA_KEYS)))

    def __le__(self, other) -> bool:
        return self.identifier <= other.identifier

class AsyncItem(AsyncBaseItem):

    def __init__(
            self,
            client,
            identifier: str,
            item_metadata: Mapping | None = None,
    ):
        self.client : Client = client
        super().__init__(identifier, item_metadata)

        self.urls = AsyncItem.URLs(self)

        if self.metadata.get('title'):
            details = self.urls.details
            self.wikilink = f'* [{details} {self.identifier}] -- {self.metadata["title"]}'

    class URLs:
        _BASE_PATHS: Set[str] = {
            'details', 'metadata', 'download', 'history',
            'edit', 'editxml', 'manage'
        }

        def __init__(self, itm_obj):
            self._itm_obj = itm_obj
            self._url_cache = {}
            self._valid_paths = self._BASE_PATHS.copy()


        def __getattr__(self, name: str) -> str:
            if name in self._url_cache:
                return self._url_cache[name]

            if name not in self._valid_paths:
                raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

            if name in self._BASE_PATHS:
                url = (f'{URLS.BASE_URL.value}/{self._itm_obj.identifier}/{name}')

            self._url_cache[name] = url  # pyright: ignore [reportPossiblyUnboundVariable]
            return url  # pyright: ignore [reportPossiblyUnboundVariable]

        def __dir__(self):
            return sorted(list(super().__dir__()) + list(self._valid_paths))

        def __str__(self) -> str:
            return f"URLs ({', '.join(sorted(self._valid_paths))}) for {self._itm_obj.identifier}"

    def get_file(self, file_name: str, file_metadata: Mapping | None = None) -> AsyncFile:
        return AsyncFile(self.client, self, file_name, file_metadata)

    async def get_files(self,
                        files: AsyncFile | list[AsyncFile] | None = None,
                        formats: str | list[str] | None = None,
                        glob_pattern: str | list[str] | None = None,
                        exclude_pattern: str | list[str] | None = None,
                        on_the_fly: bool = False):
        files = files or []
        formats = formats or []
        exclude_pattern = exclude_pattern or ''
        on_the_fly = bool(on_the_fly)

        input_file_names = []
        if isinstance(files, (list, tuple, set)):
            for f_item in files:
                if isinstance(f_item, str):
                    input_file_names.append(f_item)
                elif isinstance(f_item, AsyncFile):  # Or AsyncFile
                    input_file_names.append(f_item.name)
        elif isinstance(files, str):
            input_file_names.append(files)

        if not isinstance(formats, (list, tuple, set)):
            formats = [formats]

        item_files = deepcopy(self.files)

        if on_the_fly:
            # ... (logic to append otf_files to item_files) ...
            otf_files = [
                ('EPUB', f'{self.identifier}.epub'),
                ('MOBI', f'{self.identifier}.mobi'),
                ('DAISY', f'{self.identifier}_daisy.zip'),
                ('MARCXML', f'{self.identifier}_archive_marc.xml'),
            ]
            for format_name, file_name in otf_files:
                item_files.append({'name': file_name, 'format': format_name, 'otf': True})

        for f_metadata in item_files:
            file_name = f_metadata.get('name', '')
            file_format = f_metadata.get('format', '')
            should_yield = False

            if not any([input_file_names, formats, glob_pattern]):
                should_yield = True
            elif file_name in input_file_names:
                should_yield = True
            elif file_format in formats:
                should_yield = True
            elif glob_pattern:
                patterns = glob_pattern.split('|') if isinstance(glob_pattern, str) else glob_pattern
                exclude_patterns = exclude_pattern.split('|') if isinstance(exclude_pattern, str) else exclude_pattern

                if any(fnmatch(file_name, p) for p in patterns):
                    if not any(fnmatch(file_name, e) for e in exclude_patterns):
                        should_yield = True
            if should_yield:
                yield self.get_file(file_name, file_metadata=f_metadata)

    async def download(self, download_options: DownloadOptions):
        if download_options.source and not isinstance(download_options.source, list):
            download_options.source = [download_options.source]

        if download_options.exclude_source and not isinstance(download_options.exclude_source, list):
            download_options.exclude_source = [download_options.exclude_source]

        if download_options.stdout:
            download_options.fileobj = sys.stdout.buffer
            download_options.verbose = False

        else:
            download_options.fileobj = None

        if not download_options.dry_run:
            if download_options.item_index and download_options.verbose:
                print(f'{self.identifier} ({download_options.item_index}):', file=sys.stderr)
            elif download_options.item_index is None and download_options.verbose:
                print(f'{self.identifier}:', file=sys.stderr)

        if self.metadata == {}:
            msg = f'skipping {self.identifier}, item does not exist.'
            log.warning(msg)
            if download_options.verbose:
                print(f' {msg}', file=sys.stderr)
            return []

        if download_options.files:
            files = self.get_files(
                files=download_options.files, 
                on_the_fly=download_options.on_the_fly
            )
        elif download_options.formats:
            files = self.get_files(
                formats=download_options.formats, 
                on_the_fly=download_options.on_the_fly
            )
        elif download_options.glob_pattern:
            files = self.get_files(
                glob_pattern=download_options.glob_pattern,
                exclude_pattern=download_options.exclude_pattern,
                on_the_fly=download_options.on_the_fly
            )
        else:
            files = self.get_files(on_the_fly=download_options.on_the_fly)

        if download_options.stdout:
            files = list(files)  # type: ignore

        errors = []
        downloaded = 0
        responses = []
        file_count = 0

        for file in files:  # type: ignore
            if download_options.ignore_history_dir:
                if file.name.startswith('history/'):
                    continue

            if download_options.source and not any(file.source == x for x in download_options.source):
                continue
            
            if download_options.exclude_source and any(file.source == x for x in download_options.exclude_source):
                continue
            
            file_count += 1
            
            if download_options.no_directory:
                path = file.name
            else:
                path = os.path.join(str(self.identifier), file.name)

            if download_options.dry_run:
                print(file.url)
                continue
            
            if download_options.stdout and file_count < len(files):  # type: ignore
                download_options.ors = True
            else:
                download_options.ors = False
            
            resp = await file.download(path, download_options, None)

            if download_options.return_responses:
                responses.append(resp)

            if resp is False:
                errors.append(file.name)
            else:
                downloaded += 1

        if file_count == 0:
            msg = f'skipping {self.identifier}, no matching files found.'
            log.info(msg)
            if download_options.verbose:
                print(f' {msg}', file=sys.stderr)
            return []

        return responses if download_options.return_responses else errors


