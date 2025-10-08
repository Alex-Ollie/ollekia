from typing import Protocol, MutableMapping, Mapping, TYPE_CHECKING
import aiohttp
from pathlib import Path

from .enums.auth_enum import AuthType

if TYPE_CHECKING:
    from .data_classes.search_dataclass import SearchOptions
    from .search import AsyncSearch
    from .item import AsyncItem



class Client(Protocol):

    async def get(self, url: str, params=None, headers: dict | None = None, auth_type: AuthType = AuthType.NO_AUTH, **kwargs) -> aiohttp.ClientResponse:
        ... 

    async def post(self, url: str, params=None, 
                   headers: dict | None = None, auth_type: AuthType = AuthType.NO_AUTH, 
                   post_data: dict[str, str] | None = None, **kwargs) -> aiohttp.ClientResponse:
        ...        
    async def get_item(self,
                       identifier: str,
                       item_metadata: Mapping | None = None,
                       request_kwargs: MutableMapping | None = None) -> 'AsyncItem':
        ...
    async def search_items(self, search_options: 'SearchOptions') -> 'AsyncSearch':
        ...

    async def update_credentials(self, email: str, password: str) ->  Path | None:
        ...

    async def close(self):
        ...
    """Closes the client's session. Should be called on shutdown."""
