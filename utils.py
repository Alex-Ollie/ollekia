import hashlib
import os
from collections.abc import Mapping

async def get_md5(async_file_object ) -> str:
    m = hashlib.md5()
    while True:
        chunk = await async_file_object.read(8192)
        if not chunk:
            break
        m.update(chunk)
    await async_file_object.seek(0, os.SEEK_SET)
    return m.hexdigest()


def parse_dict_cookies(value: str) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for item in value.split(';'):
        item = item.strip()
        if not item:
            continue
        if '=' not in item:
            result[item] = None
            continue
        name, value = item.split('=', 1)
        result[name] = value

    if 'domain' not in result:
        result['domain'] = '.archive.org'
    if 'path' not in result:
        result['path'] = '/'

    return result


def deep_update(d: dict, u: Mapping) -> dict:
    for k, v in u.items():
        if isinstance(v, Mapping):
            r = deep_update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d
