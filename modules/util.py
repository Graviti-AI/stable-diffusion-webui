import hashlib
import os
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import Request

from modules import shared
from modules.paths_internal import script_path


def natural_sort_key(s, regex=re.compile('([0-9]+)')):
    return [int(text) if text.isdigit() else text.lower() for text in regex.split(s)]


def listfiles(dirname):
    filenames = [os.path.join(dirname, x) for x in sorted(os.listdir(dirname), key=natural_sort_key) if not x.startswith(".")]
    return [file for file in filenames if os.path.isfile(file)]


def html_path(filename):
    return os.path.join(script_path, "html", filename)

def list_extension_html(dirpath, filename):
    path = os.path.join(script_path, dirpath, filename)
    if os.path.exists(path):
        with open(path, encoding="utf8") as file:
            return file.read()
    return ""


def html(filename):
    path = html_path(filename)

    if os.path.exists(path):
        with open(path, encoding="utf8") as file:
            return file.read()

    return ""


def walk_files(path, allowed_extensions=None):
    if not os.path.exists(path):
        return

    if allowed_extensions is not None:
        allowed_extensions = set(allowed_extensions)

    items = list(os.walk(path, followlinks=True))
    items = sorted(items, key=lambda x: natural_sort_key(x[0]))

    for root, _, files in items:
        for filename in sorted(files, key=natural_sort_key):
            if allowed_extensions is not None:
                _, ext = os.path.splitext(filename)
                if ext not in allowed_extensions:
                    continue

            if not shared.opts.list_hidden_files and ("/." in root or "\\." in root):
                continue

            yield os.path.join(root, filename)


def ldm_print(*args, **kwargs):
    if shared.opts.hide_ldm_prints:
        return

    print(*args, **kwargs)


_SHARE_ID_PREFIX = "af_"
_SHARE_ID_LENGTH = 10


def get_share_url(url: str, request: Request) -> str:
    user_id = request.headers["user-id"]
    sha256 = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    full_share_id = f"{_SHARE_ID_PREFIX}{sha256[:_SHARE_ID_LENGTH]}"

    return add_params_to_url(
        url,
        {
            "utm_source": full_share_id,
            "utm_medium": full_share_id,
            "utm_campaign": full_share_id,
        },
    )


def add_params_to_url(url: str, params: dict[str, str | None]) -> str:
    parts = list(urlparse(url))

    query = dict(parse_qsl(parts[4]))
    for key, value in params.items():
        if key not in query and value is not None:
            query[key] = value

    parts[4] = urlencode(query)

    return urlunparse(parts)
