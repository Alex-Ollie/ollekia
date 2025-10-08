import logging
from typing import Any, AsyncGenerator, Generator
from urllib.parse import quote_plus, urlencode

import aiohttp

from .data_classes.search_dataclass import SearchOptions
from .enums.auth_enum import AuthType
from .enums.url_enum import URLS
from .item import AsyncItem
from .protocols import Client

logger = logging.getLogger(__name__)


class AsyncSearch:
    def __init__(self, client, search_options: SearchOptions):
        self.client: Client = client
        self._iterator = None
        self._search = None
        self.search_options = search_options
        self.search_options.dsl_fts = False if not self.search_options.dsl_fts else True
        self._num_found = None

        if self.search_options.dsl_fts or self.search_options.fts:
            self.search_options.fts = True
        else:
            self.search_options.fts = False

        if self.search_options.fts and not self.search_options.dsl_fts:
            self.search_options.query = f"!L {self.search_options.query}"

        self._num_found = None

        default_params = {"q": self.search_options.query}
        if "page" not in self.search_options.params:
            if "rows" in self.search_options.params:
                self.search_options.params["page"] = 1
            else:
                default_params["count"] = str(10000)
        else:
            default_params["output"] = "json"

        if "index" in self.search_options.params:
            self.search_options.params["scope"] = self.search_options.params["index"]
            del self.search_options.params["index"]

        final_params = default_params.copy()
        final_params.update(self.search_options.params)
        self.search_options.params = final_params

        # Set timeout.
        if "timeout" not in self.search_options.request_kwargs:
            self.search_options.request_kwargs["timeout"] = 300

    async def _advanced_search(self):
        if "identifier" not in self.search_options.fields:
            self.search_options.fields.append("identifier")

        for key, value in enumerate(self.search_options.fields):
            self.search_options.params[f"fl[{key}]"] = value

        for i, field in enumerate(self.search_options.sorts):
            self.search_options.params[f"sort[{i}]"] = field

        self.search_options.params["output"] = "json"

        try:
            response = await self.client.get(
                URLS.ADVANCED_SEARCH_URL.value,
                params=self.search_options.params,
                **self.search_options.request_kwargs,
            )
            response_json = await response.json()
            num_found = int(response_json.get("response", {}).get("numFound", 0))

            if not self._num_found:
                self._num_found = num_found

            for doc in response_json.get("response", {}).get("docs", []):
                yield doc

        except aiohttp.ClientResponseError as e:
            logger.error(
                f"HTTP Error during advanced search for {self.search_options.query}: Status {e.status} - {e.message}"
            )
            # raise InternetArchiveSearchError(f"HTTP error during advanced search: {e.status} - {e.message}") from e
        except aiohttp.ClientError as e:
            logger.error(
                3,
                f"Network error during advanced search for {self.search_options.query}: {e}",
            )
            # raise InternetArchiveSearchError(f"Network error during advanced search: {e}") from e
        except Exception as e:
            logger.exception(
                f"An unexpected error occurred during advanced search for {self.search_options.query}. Error: {e} "
            )
            # raise InternetArchiveSearchError(f"Unexpected error during advanced search: {e}") from e

    async def _scrape(self) -> AsyncGenerator[Any, None]:  # Make async generator
        if self.search_options.fields:
            self.search_options.params["fields"] = ",".join(self.search_options.fields)

        if self.search_options.sorts:
            self.search_options.params["sorts"] = ",".join(self.search_options.sorts)
        # self.search_options.params["total_only"] = "true"

        # if "fields" in self.search_options.params:
        #     del self.search_options.params["fields"]
        # if "sorts" in self.search_options.params:
        #     del self.search_options.params["sorts"]
        # i = 0
        # num_found = None

        # url = f"{URLS.SCRAPE_URL.value}?q={self.search_options.encoded_search}"
        print("new code")
        while True:
            try:
                response = await self.client.post(
                    url=URLS.SCRAPE_URL.value,
                    auth_type=AuthType.S3,
                    params=self.search_options.params,
                    **self.search_options.request_kwargs,
                )

                json_response = await response.json()

                if json_response.get("error"):
                    error_msg = json_response.get("error", "Unknown scrape API error.")
                    logger.error(
                        f"Scrape API returned error: {error_msg} for query: {self.search_options.query}"
                    )
                    yield json_response
                    # raise InternetArchiveSearchError(f"Scrape API error: {error_msg}", api_response=json_response)

                self._num_found = json_response.get("total", 0)

                for item in json_response["items"]:
                    yield item

            except aiohttp.ClientResponseError as e:
                logger.error(
                    f"HTTP Error during scrape for {self.search_options.query}: Status {e.status} - {e.message}"
                )
                # raise InternetArchiveSearchError(f"HTTP error during scrape: {e.status} - {e.message}") from e
                break
            except aiohttp.ClientError as e:
                logger.error(
                    f"Network error during scrape for {self.search_options.query}: {e}"
                )
                # raise InternetArchiveSearchError(f"Network error during scrape: {e}") from e
                # except InternetArchiveSearchError: # Catch custom error from _handle_scrape_error
                break
            except Exception as e:
                logger.exception(
                    f"An unexpected error occurred during scrape for {self.search_options.query}. error: {e}"
                )
                # raise InternetArchiveSearchError(f"Unexpected error during scrape: {e}") from e
                break

    async def _full_text_search(self):  # This is an async generator
        data = {
            "q": self.search_options.query,
            "size": "10000",
            "from": "0",
            "scroll": "true",
        }

        if "scope" in self.search_options.params:
            data["scope"] = self.search_options.params["scope"]

        if "size" in self.search_options.params:
            data["scroll"] = str(False)
            data["size"] = self.search_options.params["size"]

        while True:
            try:
                # Use self.client.post, which handles auth_type='s3' and raise_for_status()
                response = await self.client.post(
                    URLS.FTS_URL.value,
                    json=data,  # Pass JSON payload directly
                    auth_type=AuthType.S3,  # Assuming FTS API uses S3Auth
                    **self.search_options.request_kwargs,
                )

                json_response = await response.json()

                if json_response.get("error"):
                    error_msg = json_response.get("error", "Unknown FTS API error.")
                    logger.error(
                        f"Full text search API returned error: {error_msg} for query: {self.search_options.query}"
                    )
                    # raise InternetArchiveSearchError(f"FTS API error: {error_msg}", api_response=json_response)

                scroll_id = json_response.get("_scroll_id")
                hits = json_response.get("hits", {}).get("hits")

                if not hits:
                    return
                yield hits

                if not hits or data["scroll"] is False:
                    break

                data["scroll_id"] = scroll_id

            # --- Error Handling ---
            except aiohttp.ClientResponseError as e:
                logger.error(
                    f"HTTP Error during full text search for {self.search_options.query}: Status {e.status} - {e.message}"
                )
                # raise InternetArchiveSearchError(f"HTTP error during FTS: {e.status} - {e.message}") from e
            except aiohttp.ClientError as e:
                logger.error(
                    f"Network error during full text search for {self.search_options.query}: {e}"
                )
                # raise InternetArchiveSearchError(f"Network error during FTS: {e}") from e
            # except InternetArchiveSearchError:  # Catch custom error if raised internally
            # raise
            except Exception as e:
                logger.exception(
                    f"An unexpected error occurred during full text search for {self.search_options.query}. error: {e}"
                )
                # raise InternetArchiveSearchError(f"Unexpected error during FTS: {e}") from e

    async def _make_results_generator(self) -> AsyncGenerator:
        if self.search_options.fts:
            async for result in self._full_text_search():
                yield result
        elif "user_aggs" in self.search_options.params:
            async for result in self._user_aggs():
                yield result
        elif "page" in self.search_options.params:
            async for result in self._advanced_search():
                yield result
        else:
            async for result in self._scrape():
                yield result

    async def _user_aggs(self):
        """Experimental support for user aggregations."""
        del self.search_options.params["count"]
        self.search_options.params["rows"] = "1"
        self.search_options.params["output"] = "json"
        response = await self.client.get(
            URLS.ADVANCED_SEARCH_URL.value,
            params=self.search_options.params,
            auth=AuthType.S3,
            **self.search_options.request_kwargs,
        )

        response_json = await response.json()

        if response_json.get("error"):
            logger.error(
                "JSON decoding error. Please check the response format or the parameters used."
            )
            # raise error
        async for agg in (
            response_json.get("response", {}).get("aggregations", {}).items()
        ):
            yield {agg[0]: agg[1]}

    # @property
    # async def num_found(self) -> int:
    #     if not self._num_found:
    #         if not self.search_options.fts and "page" in self.search_options.params:
    #             params = self.search_options.params.copy()
    #             params["output"] = "json"

    #             response = await self.client.get(
    #                 URLS.ADVANCED_SEARCH_URL.value,
    #                 params=params,
    #                 auth=AuthType.S3,
    #                 **self.search_options.request_kwargs,
    #             )

    #             response_json = await response.json()

    #             num_found = int(response_json.get("response", {}).get("numFound", 0))

    #             if not self._num_found:
    #                 self._num_found = num_found

    #         elif not self.search_options.fts:
    #             params = self.search_options.params.copy()
    #             params["total_only"] = "true"
    #             response = await self.client.post(
    #                 url=URLS.SCRAPE_URL.value,
    #                 params=params,
    #                 auth=AuthType.S3,
    #                 **self.search_options.request_kwargs,
    #             )

    #             response_json = await response.json()

    #             # self._handle_scrape_error(response_json)
    #             self._num_found = response_json.get("total")

    #         else:
    #             self.search_options.params["q"] = self.search_options.query

    #             response = await self.client.get(
    #                 URLS.FTS_URL.value,
    #                 params=self.search_options.params,
    #                 auth=AuthType.S3,
    #                 **self.search_options.request_kwargs,
    #             )
    #             response_json = await response.json()
    #             self._num_found = response_json.get("hits", {}).get("total")

    #     return self._num_found

    # def _handle_scrape_error(self, json):
    # TOoDO - create some custom errors

    async def _get_item_from_search_result(self, search_result: dict) -> AsyncItem:
        return await self.client.get_item(search_result["identifier"], None, None)

    async def iter_as_results(self):  # Return type hint
        return AsyncSearchIterator(self, self._make_results_generator())

    async def iter_as_items(self):
        async def async_map():
            async for result in self._make_results_generator():
                yield await self._get_item_from_search_result(result)

        return AsyncSearchIterator(self, async_map())


class AsyncSearchIterator:
    def __init__(self, search: AsyncSearch, iterator: AsyncGenerator[Any]):
        self.search = search
        self.iterator = iterator

    def __len__(self):
        return self.search._num_found

    def __repr__(self):
        return f"{self.__class__.__name__}({self.search!r}, {self.iterator!r})"

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await anext(self.iterator)
