"""Gallery media URLs sent by the browser, read from the gallery of diffus-app, which checks their
signature: not from the workdir, unchecked.

Imports PIL, numpy and requests only, to be shared with ComfyUI. See
docs/2026-11-19-embedded-app-gallery-input-images.md in diffus-app.
"""

from __future__ import annotations

import io
import logging
import os
import re
from typing import Any, Callable
from urllib.parse import urlsplit

import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MEDIA_PATH_PREFIX = "/api/public/gallery/v1/media/"

_REQUEST_TIMEOUT = 15

# Finds a gallery instance as registering images does; GALLERY_CDN_URL is used without one.
_gallery_endpoint_resolver: Callable[[], str] | None = None


# The query of a gallery media URL, its signature, valid for long.
_MEDIA_URL_QUERY = re.compile(rf"({re.escape(MEDIA_PATH_PREFIX)}[^\s'\"?\\]*)\?[^\s'\"\\]*")


def redact_gallery_media_urls(value: Any) -> Any:
    """The value without the signatures of the gallery media URLs in its strings, to be logged or sent
    to the system monitor."""
    if isinstance(value, str):
        return _MEDIA_URL_QUERY.sub(r"\1?…", value)
    if isinstance(value, dict):
        # Keys too: the gallery IDs of the output images are keyed by their URLs.
        return {
            redact_gallery_media_urls(key) if isinstance(key, str) else key: redact_gallery_media_urls(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_gallery_media_urls(item) for item in value]
    return value


def _redact_for_log(value: Any) -> str:
    return redact_gallery_media_urls(str(value))[:200]


def set_gallery_endpoint_resolver(resolver: Callable[[], str] | None) -> None:
    global _gallery_endpoint_resolver
    _gallery_endpoint_resolver = resolver


class InputImageLoadError(Exception):
    """A gallery input image that cannot be read, failing the generation; its message is for the user."""


def is_gallery_media_url(url: Any) -> bool:
    return isinstance(url, str) and urlsplit(url).path.startswith(MEDIA_PATH_PREFIX)


def _get_media_path(url: str) -> str:
    """The path and query of a gallery media URL; its host is not trusted."""

    parts = urlsplit(url)
    if not parts.path.startswith(MEDIA_PATH_PREFIX) or ".." in parts.path.split("/"):
        raise ValueError(f"Not a gallery media URL: {_redact_for_log(url)}")

    return f"{parts.path}?{parts.query}" if parts.query else parts.path


def _get_gallery_endpoint(name: str) -> str:
    if _gallery_endpoint_resolver is None:
        endpoint = os.getenv("GALLERY_CDN_URL")
        if not endpoint:
            logger.error("Neither a gallery endpoint resolver nor GALLERY_CDN_URL is set")
            raise InputImageLoadError(f"Failed to read the {name} from the gallery, please try again later.")
        return endpoint

    try:
        return _gallery_endpoint_resolver()
    except Exception as error:
        # No gallery instance is up.
        logger.exception("Failed to find the gallery")
        raise InputImageLoadError(
            f"Failed to read the {name} from the gallery, please try again later."
        ) from error


# The modes of the color spaces of ICC profiles.
_ICC_MODES = {"RGB": "RGB", "CMYK": "CMYK", "GRAY": "L"}


def _to_srgb(image: Image.Image, mode: str) -> Image.Image:
    """The image in sRGB without its color profile, as the browser draws it on a canvas: sent with the
    profile, it would be converted there to pixels other than those read here."""

    icc_profile = image.info.pop("icc_profile", None)
    if not icc_profile:
        return image.convert(mode)

    try:
        from PIL import ImageCms

        source = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
        source_mode = _ICC_MODES[source.profile.xcolor_space.strip()]
        converted = ImageCms.profileToProfile(image.convert(source_mode), source, ImageCms.createProfile("sRGB"), outputMode="RGB")
    except Exception:
        # Read as is, without its profile, as the browser then shows it.
        logger.exception("Failed to convert the gallery media to sRGB")
        return image.convert(mode)

    if mode == "RGBA":
        converted.putalpha(image.convert("RGBA").getchannel("A"))
    converted.info = image.info
    return converted


def _to_8_bits(image: Image.Image, content: bytes) -> Image.Image:
    """A 16 bits PNG as 8 bits, as the browser shows it: its samples as their high bytes, its transparent
    color (tRNS) compared at 16 bits. Pillow reads a grey one as I;16 (I by older versions), its levels
    clipped once converted, and an RGB one as 8 bits, whose low bytes are read decoding it again."""

    transparency = image.info.get("transparency")
    if image.mode.startswith("I;16") or (image.mode == "I" and image.format == "PNG"):
        samples = np.clip(np.asarray(image, dtype=np.int64), 0, 65535)
        converted = Image.fromarray((samples >> 8).astype(np.uint8), "L")
        transparent = samples == transparency if isinstance(transparency, int) else None
    elif image.format == "PNG" and isinstance(transparency, tuple) and [tile[3] for tile in image.tile] == ["RGB;16B"]:
        low = Image.open(io.BytesIO(content))
        low.tile = [(*tile[:3], "RGB;16L") for tile in low.tile]
        samples = (np.asarray(image, dtype=np.uint16) << 8) | np.asarray(low, dtype=np.uint16)
        converted = image.convert("RGB")
        transparent = (samples == np.array(transparency, dtype=np.uint16)).all(axis=2)
    else:
        return image

    if transparent is not None:
        converted.putalpha(Image.fromarray(np.where(transparent, 0, 255).astype(np.uint8), "L"))
    converted.info = {key: value for key, value in image.info.items() if key != "transparency"}
    return converted


def _has_alpha(image: Image.Image) -> bool:
    # A transparent color (tRNS) makes transparency in any mode.
    return image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info


def load_gallery_media(url: str, name: str = "image") -> Image.Image:
    """Read a gallery media URL sent by the browser from the gallery, as an RGB or RGBA image; the name
    tells the user which image failed."""

    import requests

    try:
        media_path = _get_media_path(url)
    except ValueError as error:
        logger.warning("Refused the gallery media URL: %s", error)
        raise InputImageLoadError(
            f"The link to the {name} is invalid, please select it again."
        ) from error

    gallery_url = f"{_get_gallery_endpoint(name).rstrip('/')}{media_path}"

    try:
        response = requests.get(gallery_url, timeout=_REQUEST_TIMEOUT)
    except Exception as error:
        # Not chained: the error tells the signed URL.
        logger.error("Failed to read the gallery media %s: %s", _redact_for_log(url), _redact_for_log(error))
        raise InputImageLoadError(
            f"Failed to read the {name} from the gallery, please try again later."
        ) from None

    if response.status_code == 404:
        raise InputImageLoadError(
            f"The {name} has been deleted from the gallery, please select it again."
        )

    if response.status_code == 403:
        raise InputImageLoadError(
            f"The link to the {name} is invalid or has expired, please select it again."
        )

    if not response.ok:
        logger.error("Failed to read the gallery media %s: %s %s", _redact_for_log(url), response.status_code, _redact_for_log(response.text))
        raise InputImageLoadError(
            f"Failed to read the {name} from the gallery, please try again later."
        )

    try:
        # Before transposed, which drops the format telling a 16 bits PNG.
        image = _to_8_bits(Image.open(io.BytesIO(response.content)), response.content)
        image = ImageOps.exif_transpose(image) or image
        # RGB unless transparent: RGBA fails where RGB is taken.
        return _to_srgb(image, "RGBA" if _has_alpha(image) else "RGB")
    except Exception as error:
        logger.exception("Failed to decode the gallery media %s", _redact_for_log(url))
        raise InputImageLoadError(f"The {name} in the gallery is not a valid image.") from error
