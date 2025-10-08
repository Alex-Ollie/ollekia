import asyncio
import configparser
import os
import sys
from pathlib import Path
from typing import Tuple, Optional, Mapping

import aiofiles
import aiofiles.os

from .utils import deep_update


async def parse_config_file(config_file_path: Optional[str] = None) -> Tuple[
    Path, bool, configparser.RawConfigParser]:
    config = configparser.RawConfigParser()
    is_xdg_path = False

    if config_file_path:
        resolved_config_path = Path(config_file_path)
    else:
        candidates = []
        if os.environ.get('IA_CONFIG_FILE'):
            candidates.append(Path(os.environ['IA_CONFIG_FILE']))

        xdg_config_home_str = os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))
        xdg_config_home = Path(xdg_config_home_str)
        xdg_config_file = xdg_config_home / 'internetarchive' / 'ia.ini'

        if not xdg_config_home or not os.path.isabs(xdg_config_home):
            xdg_config_home = os.path.join(os.path.expanduser('~'), '.config')

        xdg_config_home = Path(xdg_config_home_str)
        xdg_config_file = xdg_config_home / 'internetarchive' / 'ia.ini'

        candidates.append(xdg_config_file)
        candidates.append(Path.home() / '.config' / 'ia.ini')
        candidates.append(Path.home() / '.ia')

        for candidate in candidates:
            if await aiofiles.os.path.isfile(candidate):
                resolved_config_path = candidate
                if resolved_config_path == xdg_config_file:
                    is_xdg_path = True
                break
        else:
            default_path_str = os.environ.get('IA_CONFIG_FILE', str(xdg_config_file))
            resolved_config_path = Path(default_path_str)
            if resolved_config_path == xdg_config_file:
                is_xdg_path = True

    resolved_config_str = str(resolved_config_path)

    try:
        if await aiofiles.os.path.exists(resolved_config_str):
            async with aiofiles.open(resolved_config_str, 'r', encoding='utf-8') as f:
                config_content = await f.read()
                config.read_string(config_content)
    except configparser.MissingSectionHeaderError as e:
        print(
            f"Warning: Config file '{resolved_config_path}' is malformed. "
            f"Attempting to proceed with defaults. Error: {e}",
            file=sys.stderr)
    except Exception as e:
        print(
            f"Warning: Could not read config file '{resolved_config_path}'. "
            f"Attempting to proceed with defaults. Error: {e}",
            file=sys.stderr)

    # --- Process config sections (synchronous, in-memory operations) ---
    if not config.has_section('s3'):
        config.add_section('s3')
    config.set('s3', 'access', config.get('s3', 'access', fallback=None))
    config.set('s3', 'secret', config.get('s3', 'secret', fallback=None))

    if not config.has_section('cookies'):
        config.add_section('cookies')
    config.set('cookies', 'logged-in-user', config.get('cookies', 'logged-in-user', fallback=None))
    config.set('cookies', 'logged-in-sig', config.get('cookies', 'logged-in-sig', fallback=None))

    if not config.has_section('general'):
        config.add_section('general')
    secure_value = config.getboolean('general', 'secure', fallback=True)
    config.set('general', 'secure', str(secure_value))
    screenname_value = config.get('general', 'screenname', fallback=None)
    config.set('general', 'screenname', screenname_value if screenname_value is not None else '')

    return resolved_config_path, is_xdg_path, config


async def get_config(config=None, config_file=None) -> dict:
    _config = config or {}
    config_file, is_xdg, config = await parse_config_file(config_file)

    if not await aiofiles.os.path.isfile(config_file):
        return _config

    config_dict = {
        section: {k: v for k, v in config.items(section) if k is not None and v is not None}
        for section in config.sections()
    }

    # Recursive/deep update.
    deep_update(config_dict, _config)

    return {k: v for k, v in config_dict.items() if v is not None}


async def write_config_file(auth_config: Mapping, config_file_path: Optional[str] = None) -> Path:
    resolved_config_path_str, is_xdg, config_parser_obj = await parse_config_file(config_file_path)
    resolved_config_path = Path(resolved_config_path_str)

    s3_section = auth_config.get('s3', {})
    config_parser_obj.set('s3', 'access', s3_section.get('access', ''))
    config_parser_obj.set('s3', 'secret', s3_section.get('secret', ''))

    cookies_section = auth_config.get('cookies', {})
    config_parser_obj.set('cookies', 'logged-in-user', cookies_section.get('logged-in-user', ''))
    config_parser_obj.set('cookies', 'logged-in-sig', cookies_section.get('logged-in-sig', ''))

    config_directory = resolved_config_path.parent
    if is_xdg and not aiofiles.os.path.exists(config_directory):
        try:
            await aiofiles.os.makedirs(config_directory, mode=0o700, exist_ok=True)
        except OSError as e:
            raise IOError(f"Failed to create config directory '{config_directory}': {e}") from e

    try:
        async with aiofiles.open(resolved_config_path.resolve(), 'w') as fh:
            fd = fh.fileno()
            await asyncio.to_thread(os.fchmod, fd, 0o600)
            config_parser_obj.write(fh)

    except OSError as e:
        raise IOError(f"Failed to write config file '{resolved_config_path}': {e}") from e
    except Exception as e:
        raise Exception(f"An unexpected error occurred while writing config file '{resolved_config_path}': {e}") from e

    return resolved_config_path
