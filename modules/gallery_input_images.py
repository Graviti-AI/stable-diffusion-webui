"""Input images of a generation taken from the gallery, as Create/Edit Image of diffus-app does.

A canvas filled from the gallery holds a reference to the gallery image or upload. When generating, the
image is read again from the gallery, which checks the signature of its URL, and used and recorded only
if it is still the image the browser sent.

Imports PIL, numpy and requests only, to be shared with ComfyUI. See
docs/2026-11-19-embedded-app-gallery-input-images.md in diffus-app.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Callable
from urllib.parse import urlsplit

import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

INPUT_IMAGE_TYPES = ("IMAGE", "UPLOAD")

MEDIA_PATH_PREFIX = "/api/public/gallery/v1/media/"

_REQUEST_TIMEOUT = 15

_INPUT_IMAGES_KEY = "_gallery_input_images"

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


@dataclass
class InputImageRef:
    """A gallery image (IMAGE, an int id) or upload (UPLOAD, a str id), as diffus-app returns it."""

    type: str
    id: int | str
    url: str
    width: int | None = None
    height: int | None = None

    @classmethod
    def parse(cls, value: Any) -> InputImageRef | None:
        if not value:
            return None

        try:
            data = json.loads(value) if isinstance(value, str) else dict(value)

            ref_type = data["type"]
            if ref_type not in INPUT_IMAGE_TYPES:
                raise ValueError(f"Unknown input image type: {ref_type}")

            return cls(
                type=ref_type,
                id=int(data["id"]) if ref_type == "IMAGE" else str(data["id"]),
                url=str(data["url"]),
                width=data.get("width"),
                height=data.get("height"),
            )
        except Exception as error:
            logger.warning("Invalid gallery input image reference %s: %s", _redact_for_log(value), _redact_for_log(repr(error)))
            return None

    def dumps(self) -> str:
        """The reference as a canvas holds it."""
        return json.dumps(asdict(self))

    def to_gallery_input_image(self, label: str) -> dict[str, Any]:
        return {"label": label, "id": self.id, "type": self.type}


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


def has_scribbles(foreground: Image.Image | None) -> bool:
    """Whether anything is drawn on the foreground of a canvas, erased strokes not counting."""

    if foreground is None or foreground.mode != "RGBA":
        return False

    return bool(np.asarray(foreground.getchannel("A")).any())


def _squeeze_single_channel(array: np.ndarray) -> np.ndarray:
    """A single channel as (H, W, 1), which ControlNet takes, as the grey (H, W) it is."""
    return array[..., 0] if array.ndim == 3 and array.shape[2] == 1 else array


def _to_rgba_array(image: Image.Image | np.ndarray) -> np.ndarray:
    if isinstance(image, Image.Image):
        return np.asarray(image.convert("RGBA"))

    array = _squeeze_single_channel(np.asarray(image))
    if array.ndim == 2:
        array = np.stack([array] * 3, axis=2)
    if array.shape[2] == 3:
        array = np.concatenate([array, np.full(array.shape[:2] + (1,), 255, dtype=array.dtype)], axis=2)
    return array


def is_same_image(a: Image.Image | np.ndarray, b: Image.Image | np.ndarray) -> bool:
    """Whether two images are the same, however the browser encoded them: ForgeCanvas writes its image
    back re-encoded, rounding translucent pixels, compared premultiplied; opaque ones exactly."""

    x, y = _to_rgba_array(a), _to_rgba_array(b)
    if x.shape != y.shape:
        return False

    # By rows, bounding the memory of a large image.
    for row in range(0, x.shape[0], 256):
        xs = x[row:row + 256].astype(np.int32)
        ys = y[row:row + 256].astype(np.int32)
        alpha_x, alpha_y = xs[..., 3:], ys[..., 3:]
        if np.abs(alpha_x - alpha_y).max() > 2:
            return False

        opaque = (alpha_x == 255) & (alpha_y == 255)
        difference = np.abs(xs[..., :3] * alpha_x - ys[..., :3] * alpha_y)
        if (difference > np.where(opaque, 0, 2 * 255)).any():
            return False

    return True


def resolve_input_image(
    processing: Any,
    label: str,
    name: str,
    ref: InputImageRef | None,
    sent_image: Image.Image | np.ndarray | None,
) -> Image.Image | None:
    """The gallery image of the input, recorded as the input. None without a reference, or when the image
    sent is another one (the canvas changed another way), which is then used unrecorded.

    Raises InputImageLoadError when the image cannot be read, even if it is not the one sent: that is
    known only once read.
    """

    forget_input_image(processing, label)

    if ref is None or sent_image is None:
        return None

    image = load_gallery_media(ref.url, name)

    if not is_same_image(image, sent_image):
        logger.warning(
            "The %s of %s is not used, as it is not the image sent: %s %s", name, label, ref.type, ref.id
        )
        return None

    record_input_image(processing, label, ref)
    return image


def _get_input_images(processing: Any) -> dict[str, InputImageRef]:
    inputs = getattr(processing, _INPUT_IMAGES_KEY, None)
    if inputs is None:
        inputs = {}
        setattr(processing, _INPUT_IMAGES_KEY, inputs)
    return inputs


def record_input_image(processing: Any, label: str, ref: InputImageRef) -> None:
    _get_input_images(processing)[label] = ref


def forget_input_image(processing: Any, label: str) -> None:
    _get_input_images(processing).pop(label, None)


def copy_input_images(source: Any, target: Any) -> None:
    """Record the inputs of one processing on another, which registers the images (extras)."""
    _get_input_images(target).update(_get_input_images(source))


def get_register_fields(processing: Any) -> dict[str, Any]:
    """The `input_images` of the request registering an image of the generation."""

    inputs = getattr(processing, _INPUT_IMAGES_KEY, None)
    if not inputs:
        return {}

    return {"input_images": [ref.to_gallery_input_image(label) for label, ref in inputs.items()]}


# The input of extras, a single image.
EXTRAS_LABEL = "extras"

# The img2img canvases by mode (inpaint upload is no canvas) and the labels of their inputs, as
# javascript/galleryInputImage.js maps them.
IMG2IMG_CANVASES = ("img2img_image", "img2img_sketch", "img2maskimg", "inpaint_sketch")
IMG2IMG_LABELS = ("img2img", "sketch", "inpaint", "inpaint sketch")

# The modes whose init image is the background composited with the foreground.
_SKETCH_MODES = (1, 3)

_IMG2IMG_REFS_KEY = "gallery_input_refs"


def set_img2img_refs(processing: Any, refs: tuple[Any, ...]) -> None:
    """Keep the references of the img2img canvases, in the order of IMG2IMG_CANVASES."""
    setattr(processing, _IMG2IMG_REFS_KEY, tuple(refs))


def apply_img2img_input_image(processing: Any, mode: int, foreground: Image.Image | None) -> None:
    """Take the init image from the gallery when the canvas of the mode holds a reference, unless it is
    drawn over (sketch).

    Raises InputImageLoadError when the image cannot be read.
    """

    refs = getattr(processing, _IMG2IMG_REFS_KEY, None) or ()
    if not 0 <= mode < min(len(IMG2IMG_CANVASES), len(refs)):
        return

    label = IMG2IMG_LABELS[mode]
    ref = InputImageRef.parse(refs[mode])
    init_images = getattr(processing, "init_images", None)
    sent_image = init_images[0] if init_images else None

    if mode in _SKETCH_MODES and has_scribbles(foreground):
        # Drawn over, it is used unrecorded.
        return

    image = resolve_input_image(processing, label, f"{label} image", ref, sent_image)
    if image is not None:
        processing.init_images[0] = image
