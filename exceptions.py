class InternetArchiveError(Exception):
    """Base exception for all errors in the Internet Archive wrapper."""
    pass

# ... (Auth and Config errors) ...

class InternetArchiveAPIError(InternetArchiveError):
    def __init__(self, message, api_response=None, url=None):
        super().__init__(message)
        self.api_response = api_response # Store the raw JSON response
        self.url = url

class InternetArchiveHTTPError(InternetArchiveAPIError): # Inherit from APIError if HTTP errors are also API-related
    def __init__(self, message, status_code=None, api_response=None, url=None):
        super().__init__(message, api_response=api_response, url=url)
        self.status_code = status_code

class InternetArchiveNetworkError(InternetArchiveError):
    def __init__(self, message, url=None):
        super().__init__(message)
        self.url = url

class InternetArchiveSearchError(InternetArchiveAPIError): # Your specific search error
    """Exception raised for errors during Internet Archive search operations."""
    # It already has api_response and url from InternetArchiveAPIError
    pass

class InternetArchiveDownloadError(InternetArchiveAPIError):
    """Exception raised for errors during file download operations."""
    # Could add file_url, dest_path etc.
    pass