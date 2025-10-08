from enum import Enum

#UNTESTED

class DownloadStatus(Enum):
    """
    Represents the status of a file download.
    """
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"