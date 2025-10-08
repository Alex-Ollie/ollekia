from dataclasses import dataclass, field
from pathlib import Path  # For destdir
from typing import Optional, Tuple, Union, IO, Dict, TYPE_CHECKING

from aiofiles.threadpool.binary import AsyncBufferedReader, AsyncBufferedIOBase  # For type hints

if TYPE_CHECKING:
    from ..file import AsyncFile


@dataclass
class DownloadOptions:
    """
    Configuration options for downloading a file from Internet Archive.
    """

    destdir: Optional[Path] = None
    file_path: str = field(default_factory=str)
    source: Optional[str | list[str]] = None
    exclude_source: Optional[str | list[str]] = None
    verbose: bool = False
    ignore_existing: bool = False
    ignore_errors: bool = False  #
    stdout: bool = False
    checksum: bool = False
    checksum_archive: bool = False
    retries: int = 2
    timeout: Union[float, Tuple[int, float]] = 12.0

    # Advanced options
    no_directory: bool = False
    no_change_timestamp: bool = False
    return_responses: bool = False
    fileobj: Optional[IO[bytes]] | AsyncBufferedReader | AsyncBufferedIOBase = None
    params: Optional[Dict[str, str]] = None
    chunk_size: Optional[int] = None
    retries_sleep: int = 3
    retrying: bool = False
    dry_run: bool = False
    item_index: Optional[int] = None
    files: 'AsyncFile | list[AsyncFile] | None' = None
    formats: str | list[str] | None = None
    ors = False
    glob_pattern: str | None = None
    exclude_pattern: str | None = None
    on_the_fly: bool = False
    ignore_history_dir: bool = False

    def __post_init__(self):
        if self.file_path is None and self.destdir is None and not self.stdout and not self.return_responses:
            pass
