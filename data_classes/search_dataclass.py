from dataclasses import dataclass, field
from typing import Any

"""Search for items on Archive.org.

:param max_retries:
:param request_kwargs:
:param sorts:
:param query: The Archive.org search query to yield results for. Refer to
              https://archive.org/advancedsearch.php#raw for help formatting your
              query.

:param fields: The metadata fields to return in the search results.

:param params: The URL parameters to send with each request sent to the
               Archive.org Advancedsearch Api.

:param full_text_search: Beta support for querying the archive.org
                         Full Text Search API [default: False].

:param dsl_fts: Beta support for querying the archive.org Full Text
                Search API in dsl (i.e. do not prepend ``!L `` to the
                ``full_text_search`` query [default: False].

:returns: A :class:`Search` object, yielding search results.
"""


@dataclass
class SearchOptions:
    query: str = ""
    fields: list[str] = field(default_factory=list)
    sorts: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    request_kwargs: dict[str, Any] = field(default_factory=dict)
    fts: bool = False
    dsl_fts: bool = False
